"""
src/reviewer.py
---------------
Reviewer model: generate patch + deterministic/semantic verification.
"""
import logging
import shutil
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple

from openai import OpenAI

from src.config import PricingConfig, Settings
from src.models import UsageRecord, IterationRecord, RetrievalResult
from src.utils import clean_llm_text, safe_json_parse, count_tokens_approx, read_file, write_file, now_iso

logger = logging.getLogger("closed_loop.reviewer")

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "review_output"
STATE_FILE = ROOT / "STATE.md"
SKILL_FILE = ROOT / "code_review_skill.md"

OUTPUT_DIR.mkdir(exist_ok=True)


def write_state(message: str) -> None:
    with STATE_FILE.open("a", encoding="utf-8") as f:
        f.write(f"- {now_iso()} {message}\n")


def append_lesson(lesson: str) -> None:
    with SKILL_FILE.open("a", encoding="utf-8") as f:
        f.write(f"- {lesson}\n")


def ensure_skill_file() -> None:
    if SKILL_FILE.exists():
        return
    SKILL_FILE.write_text(
        "# code_review_skill.md\n\n"
        "## Goal\nFix Python syntax and logic bugs safely before any patch is deployed.\n\n"
        "## Rules\n"
        "- Preserve function names and signatures unless refactoring is explicitly allowed.\n"
        "- Output only complete Python code.\n"
        "- No markdown fences.\n"
        "- Prefer the smallest safe fix.\n"
        "- Never claim success before local verification passes.\n"
        "- Treat compiler errors as hard blockers.\n"
        "- Use exact failure messages to improve the next attempt.\n"
        "- Avoid unrelated changes.\n\n"
        "## Verification checklist\n"
        "- The patch compiles with Python compile().\n"
        "- The file contains valid Python syntax.\n"
        "- There are no markdown fences or explanations mixed into the patch.\n"
        "- Deployment happens only after verification passes.\n\n"
        "## Lessons learned\n"
        "- Missing colons in except blocks are common and must be checked explicitly.\n"
        "- Deterministic local checks are more reliable than self-reported AI confidence.\n",
        encoding="utf-8",
    )


def ensure_demo_target(target: Path) -> None:
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "def divide(a, b):\n"
        "    try:\n"
        "        return a / b\n"
        "    except ZeroDivisionError\n"
        "        return None\n",
        encoding="utf-8",
    )


class CodeReviewer:
    """
    Handles patch generation and two-stage verification.
    Maker model generates; checker model verifies semantics.
    """

    def __init__(self, client: OpenAI, pricing: PricingConfig, settings: Settings, target_file: Path):
        self.client = client
        self.pricing = pricing
        self.settings = settings
        self.target_file = target_file
        self.usage_records: List[UsageRecord] = []
        self.iteration_records: List[IterationRecord] = []
        self._call_counter = 0

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            (prompt_tokens / 1000.0) * self.pricing.input_cost_per_1k
            + (completion_tokens / 1000.0) * self.pricing.output_cost_per_1k
        )

    def call_model(
        self, model: str, stage: str, system: str, user: str, temperature: float = 0.1
    ) -> str:
        started = time.time()
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        elapsed = time.time() - started
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        else:
            prompt_tokens = count_tokens_approx(system + user)
            completion_tokens = count_tokens_approx(content)
        cost = self._estimate_cost(prompt_tokens, completion_tokens)
        self._call_counter += 1
        record = UsageRecord(
            model=model,
            stage=stage,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=cost,
            call_num=self._call_counter,
        )
        self.usage_records.append(record)
        logger.info(
            "[%s] %.2fs | prompt=%d | completion=%d | cost=$%.4f",
            stage, elapsed, prompt_tokens, completion_tokens, cost,
        )
        return content

    def verify_patch_deterministic(self, patch_code: str) -> Tuple[bool, str]:
        cleaned = clean_llm_text(patch_code)
        if not cleaned.strip():
            return False, "Patch is empty."
        if "```" in patch_code:
            return False, "Patch contains markdown fences."
        try:
            compile(cleaned, str(self.target_file), "exec")
        except SyntaxError as e:
            return False, f"SyntaxError on line {e.lineno}: {e.msg}"
        return True, "Deterministic compile gate passed."

    def verify_patch_semantic(
        self, original_code: str, patch_code: str, context_snippets: List[str] = None
    ) -> Tuple[bool, str]:
        context_block = ""
        if context_snippets:
            context_block = "\n\nRelevant context from codebase:\n" + "\n---\n".join(context_snippets[:3])
        system = (
            "You are an independent Python code review checker. You did NOT write the patch. "
            "Evaluate whether the patch fixes the issue without changing unrelated behavior. "
            'Respond ONLY with valid JSON: {"verdict":"PASS" or "FAIL","reason":"short explanation"}'
        )
        user = (
            f"Original code:\n{original_code}\n\nCandidate patch:\n{clean_llm_text(patch_code)}"
            f"{context_block}\n\nCheck for correctness, minimality, and no unrelated changes."
        )
        raw = self.call_model(
            self.settings.checker_model, "VERIFY_SEMANTIC", system, user, temperature=0.0
        )
        parsed, error = safe_json_parse(raw)
        if error:
            return False, f"Semantic checker returned invalid JSON: {error}"
        verdict = str(parsed.get("verdict", "FAIL")).upper()
        reason = parsed.get("reason", "No reason provided.")
        return verdict == "PASS", reason

    def generate_patch(
        self,
        source_code: str,
        skill: str,
        failure_reason: str = "",
        context_snippets: List[str] = None,
    ) -> str:
        context_block = ""
        if context_snippets:
            context_block = "\n\nRelevant prior examples and patterns:\n" + "\n---\n".join(context_snippets[:5])
        system = (
            "You are a senior Python code fixer in an enterprise CI pipeline. "
            "Return ONLY the full corrected Python file. No markdown fences. No prose."
        )
        user = (
            f"Skill manual:\n{skill}\n\nTarget file: {self.target_file}\n\n"
            f"Buggy source code:\n{source_code}{context_block}"
        )
        if failure_reason:
            user += f"\n\nPrevious verification failure:\n{failure_reason}\nFix that exact issue."
        return self.call_model(
            self.settings.maker_model, "GENERATE_PATCH", system, user, temperature=0.1
        )
