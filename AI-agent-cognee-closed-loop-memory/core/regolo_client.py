"""Regolo.ai OpenAI-Compatible Client with Brick Semantic Routing & Zero Data Retention.
Provides real European Sovereign LLM inference and dynamic complexity-based model routing.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

import config

logger = logging.getLogger(__name__)

# Official Model Pricing from Regolo.ai catalog (EUR per 1M tokens)
MODEL_PRICING = {
    "brick-complexity-pro": {"input": 0.10, "output": 0.40},
    "GLM-5.2": {"input": 0.60, "output": 1.80},
    "glm5.2": {"input": 0.60, "output": 1.80},
    "gpt-oss-20b": {"input": 0.10, "output": 0.42},
    "qwen3-coder-next": {"input": 0.50, "output": 2.00},
    "qwen3.5-122b": {"input": 1.00, "output": 4.20},
    "Llama-3.3-70B-Instruct": {"input": 0.60, "output": 2.70},
    "gpt-oss-120b": {"input": 1.00, "output": 4.20},
    "Qwen3-Embedding-8B": {"input": 0.05, "output": 0.00},
    "Qwen3-Reranker-4B": {"input": 0.10, "output": 0.10},
}


class BrickRouter:
    """Dynamic Semantic Meta-Router powered by Regolo's brick-complexity-pro model."""

    @staticmethod
    def evaluate_task(
        prompt: str,
        client: Optional[OpenAI] = None,
        context_type: str = "general",
    ) -> Tuple[str, float, str]:
        """Score complexity and route sub-agents to optimal open-weight models on Regolo.ai.

        Returns:
            Tuple of (chosen_model, complexity_score, routing_rationale)
        """
        score = 5.0
        rationale = "Default routing evaluation."

        # If live OpenAI client is provided or can be created, query brick-complexity-pro
        live_client = client
        if not live_client and config.REGOLO_API_KEY:
            try:
                live_client = OpenAI(
                    api_key=config.REGOLO_API_KEY,
                    base_url=config.REGOLO_BASE_URL,
                )
            except Exception:
                live_client = None

        if live_client:
            try:
                eval_prompt = (
                    f"Evaluate software engineering task complexity on a scale from 1.0 to 10.0.\n"
                    f"Task: {prompt[:300]}\n"
                    f"Context Type: {context_type}\n"
                    f"Return strictly in this format: SCORE: <number between 1.0 and 10.0> | RATIONALE: <brief reasoning>"
                )

                res = live_client.chat.completions.create(
                    model=config.MODEL_BRICK_ROUTER,
                    messages=[{"role": "user", "content": eval_prompt}],
                    max_tokens=60,
                    temperature=0.1,
                )
                raw_text = res.choices[0].message.content or ""

                score_match = re.search(r"(\d+(?:\.\d+)?)", raw_text)
                if score_match:
                    score = float(score_match.group(1))
                    rationale = raw_text.strip()
            except Exception as e:
                logger.debug(f"Brick router live call note: {e}")

        # If live call did not produce score, use heuristic determination
        if score == 5.0 and rationale == "Default routing evaluation.":
            lower_p = prompt.lower()
            if "adr" in lower_p or "causality" in lower_p or "security" in lower_p or context_type == "reasoning":
                score = 8.8
                rationale = "High architectural complexity / multi-session causality -> Reasoning Frontier."
            elif "def " in lower_p or "class " in lower_p or "patch" in lower_p or "sql" in lower_p or context_type == "coder":
                score = 6.2
                rationale = "Code generation / AST security pattern -> Code Specialist."
            else:
                score = 3.0
                rationale = "Structured entity extraction & triage -> Fast Economic Tier."

        # Map score and context type to specialized model tier on Regolo.ai
        if context_type == "extract":
            model = config.MODEL_COGNEE_EXTRACT  # gpt-oss-20b
            full_rationale = f"Context: extract (Score {score}/10) -> Fast Economic Tier: Routed to {model} (Fast 0.28s extraction)"
        elif score >= 7.5 or context_type == "reasoning":
            model = config.MODEL_AGENT_REASONING  # qwen3.5-122b
            full_rationale = f"Score {score}/10 (Context: {context_type}) -> High Complexity: Routed to {model} (Deep Reasoning)"
        elif context_type == "coder" or score >= 4.0:
            model = config.MODEL_AGENT_CODER  # qwen3-coder-next
            full_rationale = f"Score {score}/10 (Context: {context_type}) -> Code Specialist: Routed to {model} (262K context AST specialist)"
        else:
            model = config.MODEL_COGNEE_EXTRACT  # gpt-oss-20b
            full_rationale = f"Score {score}/10 (Context: {context_type}) -> Fast Economic Tier: Routed to {model} (Fast 0.28s extraction)"

        return model, score, full_rationale


class RegoloClient:
    """Unified client for Regolo.ai EU-sovereign inference with Zero Data Retention."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = (api_key or config.REGOLO_API_KEY).strip()
        self.base_url = (base_url or config.REGOLO_BASE_URL).rstrip("/")

        if not self.api_key:
            raise ValueError(
                "REGOLO_API_KEY is not configured. Please set REGOLO_API_KEY in .env or pass it to RegoloClient."
            )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers={
                "X-Zero-Data-Retention": "true",
                "User-Agent": "Regolo-Cognee-Agent/1.0",
            },
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        stage: str = "chat",
        override_model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        stream_callback: Optional[Callable[[str, int], None]] = None,
    ) -> Dict[str, Any]:
        """Execute real chat completion on Regolo.ai with automatic Brick semantic routing."""
        start_time = time.time()

        if status_callback:
            status_callback("Evaluating task complexity with Brick Semantic Router...")

        # Determine Model via Brick Router or Override
        if override_model:
            model = override_model
            score = 5.0
            rationale = f"Explicit override to {override_model}."
        else:
            model, score, rationale = BrickRouter.evaluate_task(
                prompt=prompt,
                client=self.client,
                context_type=stage,
            )

        if status_callback:
            status_callback(f"Routed to {model} (Score {score}/10) • Synthesizing code patch...")

        # Setup parameters
        stage_cfg = config.STAGE_CONFIGS.get(stage, {})
        tok_limit = max_tokens or stage_cfg.get("max_tokens", 1200)
        temp = temperature if temperature is not None else stage_cfg.get("temperature", 0.2)

        # Enforce reasoning constraint: qwen3.5-122b requires max_tokens >= 800
        if "122b" in model.lower() and tok_limit < 800:
            tok_limit = 800

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Execute Live API call to Regolo with automatic fallback to REGOLO_DEFAULT_MODEL on failure
        try:
            if stream_callback:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=tok_limit,
                    temperature=temp,
                    stream=True,
                )
                chunks = []
                for chunk in response:
                    delta = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta else None
                    if delta:
                        chunks.append(delta)
                        stream_callback(delta, len(chunks))
                content = "".join(chunks)
                prompt_tokens = int(len(prompt) / 3.5)
                completion_tokens = int(len(content) / 3.5)
            else:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=tok_limit,
                    temperature=temp,
                )
                content = response.choices[0].message.content or ""
                prompt_tokens = response.usage.prompt_tokens if response.usage else int(len(prompt) / 3.5)
                completion_tokens = response.usage.completion_tokens if response.usage else int(len(content) / 3.5)
        except Exception as err:
            fallback_model = config.REGOLO_DEFAULT_MODEL
            if model != fallback_model:
                logger.warning(
                    f"API call to {model} failed ({err}). Falling back to default model {fallback_model}."
                )
                model = fallback_model
                rationale += f" [Fallback to {fallback_model} on error: {err}]"
                if stream_callback:
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=tok_limit,
                        temperature=temp,
                        stream=True,
                    )
                    chunks = []
                    for chunk in response:
                        delta = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta else None
                        if delta:
                            chunks.append(delta)
                            stream_callback(delta, len(chunks))
                    content = "".join(chunks)
                    prompt_tokens = int(len(prompt) / 3.5)
                    completion_tokens = int(len(content) / 3.5)
                else:
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=tok_limit,
                        temperature=temp,
                    )
                    content = response.choices[0].message.content or ""
                    prompt_tokens = response.usage.prompt_tokens if response.usage else int(len(prompt) / 3.5)
                    completion_tokens = response.usage.completion_tokens if response.usage else int(len(content) / 3.5)
            else:
                raise err

        latency = time.time() - start_time
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)

        return {
            "content": content,
            "model": model,
            "complexity_score": score,
            "routing_rationale": rationale,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_eur": cost,
            "latency_seconds": round(latency, 3),
            "zero_data_retention": True,
            "simulated": False,
        }

    def get_embedding(self, text: str) -> List[float]:
        """Fetch 4096-dimensional dense vector embeddings using Regolo Qwen3-Embedding-8B."""
        clean_text = text.replace("\n", " ").strip()[:3000]
        res = self.client.embeddings.create(
            model=config.MODEL_EMBEDDING,
            input=[clean_text],
        )
        return res.data[0].embedding

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding generation on Regolo.ai."""
        clean_texts = [t.replace("\n", " ").strip()[:3000] for t in texts]
        res = self.client.embeddings.create(
            model=config.MODEL_EMBEDDING,
            input=clean_texts,
        )
        return [item.embedding for item in res.data]

    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate exact token inference cost in EUR based on Regolo public pricing."""
        pricing = MODEL_PRICING.get(model, {"input": 0.50, "output": 2.00})
        cost = (prompt_tokens / 1_000_000 * pricing["input"]) + (completion_tokens / 1_000_000 * pricing["output"])
        return round(cost, 6)
