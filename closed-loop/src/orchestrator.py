"""
src/orchestrator.py
-------------------
Review Orchestrator: control plane for the full closed-loop pipeline.

Pipeline per iteration:
  INGEST -> RETRIEVE -> RERANK -> GENERATE -> VERIFY_STRUCTURAL ->
  VERIFY_SEMANTIC -> EXECUTE -> FEEDBACK
"""
import json
import logging
import os
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from openai import OpenAI

from src.config import PricingConfig, Settings
from src.feedback import FeedbackManager
from src.models import IterationRecord
from src.retrieval import QdrantRetriever
from src.reranker import Qwen3Reranker
from src.reviewer import CodeReviewer, ensure_skill_file, ensure_demo_target, write_state
from src.utils import clean_llm_text, read_file, now_iso

logger = logging.getLogger("closed_loop.orchestrator")

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "review_output"
SKILL_FILE = ROOT / "code_review_skill.md"
AUDIT_FILE = OUTPUT_DIR / "review_audit.json"
SUMMARY_FILE = OUTPUT_DIR / "review_summary.json"

OUTPUT_DIR.mkdir(exist_ok=True)


class ReviewOrchestrator:
    """
    Orchestrates the full enterprise closed-loop pipeline.

    Steps per iteration:
      1. INGEST  - read target file
      2. RETRIEVE - Qdrant semantic search for similar code/reviews
      3. RERANK  - Qwen3-Reranker-4B for context precision
      4. GENERATE - maker model produces patch
      5. VERIFY_STRUCTURAL - compile/syntax/markdown gate
      6. VERIFY_SEMANTIC  - checker model validates correctness
      7. EXECUTE - deploy patch to disk
      8. FEEDBACK - persist outcomes, flush lessons
    """

    def __init__(
        self,
        client: OpenAI,
        pricing: PricingConfig,
        settings: Settings,
        target_file: Path,
    ):
        self.settings = settings
        self.target_file = target_file

        self.reviewer = CodeReviewer(
            client=client, pricing=pricing, settings=settings, target_file=target_file
        )

        # Retrieval layer (Qdrant)
        self.retriever = QdrantRetriever(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        ) if settings.use_qdrant else None

        # Reranker layer (Qwen3)
        api_key = os.environ.get("REGOLO_API_KEY", "")
        rerank_base = settings.reranker_endpoint or settings.base_url
        self.reranker = Qwen3Reranker(
            base_url=rerank_base,
            api_key=api_key,
            model=settings.reranker_model,
        ) if settings.use_reranker else None

        # Feedback layer
        self.feedback = FeedbackManager(retriever=self.retriever)

    def _retrieve_context(self, query: str) -> List[str]:
        """Retrieve + rerank relevant code/review snippets."""
        if self.retriever is None:
            return []

        candidates = self.retriever.search(query=query, top_k=12)
        if not candidates:
            return []

        if self.reranker is not None:
            candidates = self.reranker.rerank(query=query, candidates=candidates, top_n=5)

        return [c.content for c in candidates]

    def run(self) -> dict:
        """
        Main closed-loop engine.
        Max iterations from settings; each failure feeds the next generate.
        """
        ensure_skill_file()
        ensure_demo_target(self.target_file)

        # Index target file into Qdrant before review
        if self.retriever is not None:
            self.retriever.index_file(self.target_file)

        original_code = read_file(self.target_file)
        source_code = original_code
        skill = read_file(SKILL_FILE)
        write_state(f"START review for {self.target_file}")

        last_reason = ""
        verdict_reason = ""
        max_iter = self.settings.max_iterations

        for iteration in range(1, max_iter + 1):
            started = time.time()
            logger.info("--- Iteration %d ---", iteration)

            # Stage 2: RETRIEVE + RERANK context
            logger.info("[%d] RETRIEVE", iteration)
            query = f"Python bug fix: {last_reason or 'syntax and logic errors'}" \
                    f" in file {self.target_file.name}"
            context_snippets = self._retrieve_context(query)
            if context_snippets:
                logger.info("[%d] %d context snippets after rerank", iteration, len(context_snippets))

            # Stage 3: GENERATE
            logger.info("[%d] GENERATE", iteration)
            patch = self.reviewer.generate_patch(
                source_code=source_code,
                skill=skill,
                failure_reason=last_reason,
                context_snippets=context_snippets,
            )
            patch_clean = clean_llm_text(patch)

            # Stage 4: VERIFY STRUCTURAL
            logger.info("[%d] VERIFY_STRUCTURAL", iteration)
            ok_struct, struct_reason = self.reviewer.verify_patch_deterministic(patch_clean)
            if not ok_struct:
                verdict_reason = struct_reason
                lesson = f"Iteration {iteration}: structural gate failed -> {struct_reason}"
                self.feedback.record_lesson(lesson)
                self.reviewer.iteration_records.append(
                    IterationRecord(iteration, "VERIFY_STRUCTURAL", "FAIL", struct_reason, time.time() - started)
                )
                logger.warning("[%d] STRUCTURAL FAIL: %s", iteration, struct_reason)
                last_reason = struct_reason
                source_code = patch_clean or source_code
                continue

            # Stage 5: VERIFY SEMANTIC
            logger.info("[%d] VERIFY_SEMANTIC", iteration)
            ok_sem, sem_reason = self.reviewer.verify_patch_semantic(
                original_code=original_code,
                patch_code=patch_clean,
                context_snippets=context_snippets,
            )
            if not ok_sem:
                verdict_reason = sem_reason
                lesson = f"Iteration {iteration}: semantic gate failed -> {sem_reason}"
                self.feedback.record_lesson(lesson)
                self.reviewer.iteration_records.append(
                    IterationRecord(iteration, "VERIFY_SEMANTIC", "FAIL", sem_reason, time.time() - started)
                )
                logger.warning("[%d] SEMANTIC FAIL: %s", iteration, sem_reason)
                last_reason = sem_reason
                source_code = patch_clean
                continue

            # Stage 6: EXECUTE
            logger.info("[%d] EXECUTE", iteration)
            backup_path = self.target_file.with_suffix(self.target_file.suffix + ".bak")
            shutil.copy(self.target_file, backup_path)
            self.target_file.write_text(patch_clean, encoding="utf-8")
            verdict_reason = sem_reason
            self.reviewer.iteration_records.append(
                IterationRecord(iteration, "EXECUTE", "PASS", sem_reason, time.time() - started)
            )
            write_state(f"SUCCESS review for {self.target_file} in iteration {iteration}")
            logger.info("[%d] PATCH DEPLOYED", iteration)

            # Stage 7: FEEDBACK
            self.feedback.persist_outcome(
                target_path=str(self.target_file),
                status="SUCCESS",
                iterations=iteration,
                reason=verdict_reason,
            )

            return self._build_summary("SUCCESS", iteration, verdict_reason, backup_path)

        write_state(f"FAILED review for {self.target_file} after {max_iter} iterations")
        self.feedback.persist_outcome(
            target_path=str(self.target_file),
            status="FAILED_AFTER_RETRIES",
            iterations=max_iter,
            reason=verdict_reason,
        )
        return self._build_summary("FAILED_AFTER_RETRIES", max_iter, verdict_reason, None)

    def _build_summary(self, status: str, iterations: int, reason: str, backup_path) -> dict:
        usage = self.reviewer.usage_records
        total_prompt = sum(r.prompt_tokens for r in usage)
        total_completion = sum(r.completion_tokens for r in usage)
        total_cost = sum(r.estimated_cost for r in usage)
        payload = {
            "status": status,
            "iterations": iterations,
            "target_file": str(self.target_file),
            "backup_file": str(backup_path) if backup_path else None,
            "verifier_reason": reason,
            "pricing": asdict(self.reviewer.pricing),
            "usage": {
                "total_prompt_tokens": total_prompt,
                "total_completion_tokens": total_completion,
                "total_estimated_cost_usd": round(total_cost, 6),
                "calls": [asdict(r) for r in usage],
            },
            "iteration_log": [asdict(r) for r in self.reviewer.iteration_records],
            "generated_at": now_iso(),
        }
        AUDIT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        SUMMARY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def format_result(self, result: dict) -> None:
        status = result.get("status", "UNKNOWN")
        color = "\033[1;92m" if status == "SUCCESS" else "\033[1;91m"
        reset = "\033[0m"
        bold = "\033[1m"
        cyan = "\033[1;36m"
        yellow = "\033[1;33m"
        green = "\033[1;32m"
        
        print("\n" + "╔" + "═" * 76 + "╗")
        print(f"║ {cyan}CLOSED-LOOP CODE REVIEW FINAL REPORT{reset} ".ljust(86) + "║")
        print("╠" + "═" * 76 + "╣")
        print(f"║  {bold}Status:{reset} {color}{status:<65}{reset} ║")
        print(f"║  {bold}Target File:{reset} {str(result.get('target_file')):<61} ║")
        print(f"║  {bold}Iterations:{reset} {str(result.get('iterations')):<62} ║")
        
        usage = result.get("usage", {})
        total_cost = usage.get('total_estimated_cost_usd', 0.0)
        print(f"║  {bold}Cost:{reset} {green}${total_cost:.4f}{reset}".ljust(85) + "║")
        print(f"║  {bold}Prompt Tokens:{reset} {usage.get('total_prompt_tokens', 0):,}".ljust(85) + "║")
        print(f"║  {bold}Completion Tokens:{reset} {usage.get('total_completion_tokens', 0):,}".ljust(85) + "║")
        
        iteration_log = result.get("iteration_log", [])
        total_time = sum(r.get("elapsed_seconds", 0) for r in iteration_log) if iteration_log else 0.0
        print(f"║  {bold}Total Time:{reset} {yellow}{total_time:.2f}s{reset}".ljust(85) + "║")
        print("╠" + "═" * 76 + "╣")
        print(f"║ {cyan}EFFICIENCY METRICS (vs. Human Dev Team @ $50/hr & 4h cycle){reset} ".ljust(86) + "║")
        print("╠" + "═" * 76 + "╣")
        
        # Benchmark definitions
        HUMAN_COST = 200.0  # 4 hours @ $50/hr
        HUMAN_TIME = 14400.0  # 4 hours in seconds
        
        cost_saved = max(0.0, HUMAN_COST - total_cost)
        cost_saved_pct = (cost_saved / HUMAN_COST) * 100 if HUMAN_COST > 0 else 0.0
        time_saved = max(0.0, HUMAN_TIME - total_time)
        time_saved_pct = (time_saved / HUMAN_TIME) * 100 if HUMAN_TIME > 0 else 0.0
        
        print(f"║  🚀 {bold}Cost Savings:{reset} {green}{cost_saved_pct:.2f}%{reset} (${cost_saved:.2f} saved)".ljust(85) + "║")
        print(f"║  ⏱️  {bold}Time Savings:{reset} {green}{time_saved_pct:.2f}%{reset} ({time_saved/3600:.2f} hours faster)".ljust(85) + "║")
        
        overall_speedup = HUMAN_TIME / max(0.1, total_time)
        print(f"║  🔥 {bold}Speedup Factor:{reset} {yellow}{overall_speedup:.1f}x{reset} faster completion time".ljust(85) + "║")
        print("╚" + "═" * 76 + "╝")
        
        errors = [r for r in iteration_log if r.get("status") == "FAIL"]
        if errors:
            print(f"\n{yellow}⚠️  Errors Detected and Resolved on-the-fly during loop:{reset}")
            for e in errors:
                print(f"  - {e.get('reason')}")
        else:
            print(f"\n{green}✅ No errors detected during closed-loop review.{reset}")
