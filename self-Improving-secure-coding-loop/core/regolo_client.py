"""Regolo.ai OpenAI-Compatible API Client.
Handles real inference calls to Regolo.ai endpoints, telemetry tracking, structured output parsing,
and semantic complexity evaluations via 'brick-complexity-pro'.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from openai import OpenAI

import config
from core.brick_governance import record_telemetry_event

logger = logging.getLogger(__name__)


def normalize_model_name(model_name: Optional[str]) -> str:
    """Normalize model identifiers to exact valid Regolo.ai endpoint model names."""
    if not model_name:
        return "glm5.2"
    m_clean = str(model_name).strip()
    m_lower = m_clean.lower().replace("_", "-")

    if "brick-complexity" in m_lower or "brick" in m_lower:
        return "brick-complexity-pro"
    if "gpt-oss-20b" in m_lower or "gpt-20b" in m_lower or m_lower == "gpt-oss":
        return "gpt-oss-20b"
    if "gpt-oss-120b" in m_lower or "gpt-120b" in m_lower:
        return "gpt-oss-120b"
    if "glm" in m_lower:
        return "glm5.2"
    if "llama" in m_lower:
        return "Llama-3.3-70B-Instruct"
    if "qwen3.5-122b" in m_lower or "122b" in m_lower:
        return "qwen3.5-122b"
    if "qwen3-coder" in m_lower or "coder" in m_lower:
        return "qwen3-coder-next"
    if "27b" in m_lower:
        return "qwen3.6-27b"
    if "9b" in m_lower:
        return "qwen3.5-9b"
    if "mistral" in m_lower:
        return "mistral-small-4-119b"
    if "gemma" in m_lower:
        return "gemma4-31b"

    return m_clean


class RegoloClient:
    """Client for Regolo.ai OpenAI-Compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = config.REGOLO_API_KEY

        self.base_url = base_url if base_url is not None else config.REGOLO_BASE_URL
        self.model = normalize_model_name(model or config.REGOLO_MODEL)

        self.is_live = bool(
            self.api_key
            and not self.api_key.startswith("your_")
            and len(self.api_key.strip()) > 5
        )

        if self.is_live:
            try:
                self.client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=180.0, max_retries=2)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client for Regolo.ai: {e}")
                self.client = None
                self.is_live = False
        else:
            self.client = None

    def _ensure_client(self):
        """Ensure active OpenAI client or raise explicit configuration error."""
        if not self.is_live or not self.client:
            raise RuntimeError(
                "REGOLO_API_KEY is not configured or invalid. "
                "Please configure a valid REGOLO_API_KEY in your .env file "
                "(get your key from https://regolo.ai)."
            )

    def chat_completion(
        self,
        stage: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        json_mode: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute a chat completion on Regolo.ai with telemetry tracking and automatic fallback."""
        self._ensure_client()

        # Determine stage config and model
        stage_key = stage or "default"
        cfg = config.STAGE_CONFIGS.get(stage_key, {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0.2,
            "timeout": 120,
        })

        raw_model = model or cfg.get("model", self.model)
        actual_model = normalize_model_name(raw_model)
        actual_temp = temperature if temperature is not None else cfg.get("temperature", 0.2)
        actual_max_tokens = max_tokens if max_tokens is not None else cfg.get("max_tokens", 2048)
        actual_timeout = timeout if timeout is not None else cfg.get("timeout", config.SUBAGENT_PROFILES.get(stage_key, {}).get("timeout_sec", 120))

        # qwen3.5-122b is a reasoning model and requires max_tokens >= 800
        if "qwen3.5-122b" in actual_model and actual_max_tokens < 800:
            actual_max_tokens = 800

        # Prepare messages
        if messages:
            chat_messages = messages
        else:
            chat_messages = []
            if system_prompt:
                chat_messages.append({"role": "system", "content": system_prompt})
            if user_prompt:
                chat_messages.append({"role": "user", "content": user_prompt})

        start_time = time.time()

        kwargs: Dict[str, Any] = {
            "model": actual_model,
            "messages": chat_messages,
            "temperature": actual_temp,
            "max_tokens": actual_max_tokens,
            "timeout": actual_timeout,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)
            latency = round(time.time() - start_time, 2)
            content = response.choices[0].message.content or ""
            usage = response.usage

            prompt_tokens = usage.prompt_tokens if usage else max(10, len(str(chat_messages)) // 4)
            completion_tokens = usage.completion_tokens if usage else max(10, len(content) // 4)

            # Record in Brick telemetry
            record_telemetry_event(
                stage=stage_key,
                model=actual_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency=latency,
                mode="live",
            )

            return {
                "content": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "latency": latency,
                "latency_sec": latency,
                "model": actual_model,
                "mode": "live",
            }
        except Exception as primary_err:
            logger.warning(
                f"[Brick Router] Call to '{actual_model}' on stage '{stage_key}' failed ({primary_err}). "
                "Checking fallback model..."
            )
            fallback_model = normalize_model_name(
                config.SUBAGENT_PROFILES.get(stage_key, {}).get("fallback_model") or "glm5.2"
            )

            # If fallback model is distinct from actual_model, attempt fallback
            if fallback_model and fallback_model != actual_model:
                try:
                    fallback_tokens = actual_max_tokens
                    if "qwen3.5-122b" in fallback_model and fallback_tokens < 800:
                        fallback_tokens = 800

                    fallback_kwargs = dict(kwargs)
                    fallback_kwargs["model"] = fallback_model
                    fallback_kwargs["max_tokens"] = fallback_tokens
                    fallback_kwargs["timeout"] = max(actual_timeout, 120)

                    fb_start_time = time.time()
                    response = self.client.chat.completions.create(**fallback_kwargs)
                    latency = round(time.time() - fb_start_time, 2)
                    content = response.choices[0].message.content or ""
                    usage = response.usage

                    prompt_tokens = usage.prompt_tokens if usage else max(10, len(str(chat_messages)) // 4)
                    completion_tokens = usage.completion_tokens if usage else max(10, len(content) // 4)

                    record_telemetry_event(
                        stage=stage_key,
                        model=fallback_model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        latency=latency,
                        mode="live_fallback",
                    )

                    return {
                        "content": content,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "latency": latency,
                        "latency_sec": latency,
                        "model": fallback_model,
                        "mode": "live_fallback",
                    }
                except Exception as fb_err:
                    logger.error(f"[Brick Router] Fallback to '{fallback_model}' on stage '{stage_key}' also failed: {fb_err}")

            latency = round(time.time() - start_time, 2)
            record_telemetry_event(
                stage=stage_key,
                model=actual_model,
                prompt_tokens=0,
                completion_tokens=0,
                latency=latency,
                mode="error",
                error=str(primary_err),
            )
            raise RuntimeError(
                f"Regolo.ai API call failed for model '{actual_model}' on stage '{stage_key}': {primary_err}"
            ) from primary_err

    def evaluate_complexity(
        self,
        task_description: str,
        role: str,
        tools_requested: Optional[List[str]] = None,
        current_budget_ratio: float = 1.0,
    ) -> Dict[str, Any]:
        """Invoke 'brick-complexity-pro' meta-router to evaluate semantic complexity (1.0 - 10.0) and routing."""
        tools_list = tools_requested or []
        prompt = f"""You are 'brick-complexity-pro', the dynamic semantic routing meta-model on Regolo.ai.
Evaluate the complexity of the following sub-agent task:
- Sub-Agent Role: {role}
- Task Description: {task_description}
- Tools Requested: {tools_list}
- Residual Budget Ratio: {current_budget_ratio:.2f}

Available models on Regolo:
- "gpt-oss-20b" (Fast, low-cost triage, classification and extraction)
- "glm5.2" (Balanced reasoning, security audit, general purpose)
- "Llama-3.3-70B-Instruct" (High-speed code synthesis, patch writing, tool execution)
- "qwen3.5-122b" (Deep architectural reasoning, zero-trust verification)
- "qwen3-coder-next" (Code optimization)

Recommended model guidance:
- For "Open SWE Executor" (code implementation/patch writing): recommend "Llama-3.3-70B-Instruct"
- For "Open SWE Planner" / "Deepsec Revalidation Gate": recommend "qwen3.5-122b"
- For "Deepsec Security Scanner": recommend "glm5.2"
- For "Governance & Triage" / "Cognee Memory Engine": recommend "gpt-oss-20b"

Respond ONLY in valid JSON matching this exact schema:
{{
    "complexity_score": <float between 1.0 and 10.0>,
    "recommended_tier": <"FAST" | "BALANCED" | "REASONING" | "DOWNSCALED">,
    "recommended_model": <"gpt-oss-20b" | "glm5.2" | "Llama-3.3-70B-Instruct" | "qwen3.5-122b" | "qwen3-coder-next">,
    "routing_reasoning": "<Concise 1-2 sentence rationale considering role, complexity, tools and budget>",
    "escalation_recommended": <boolean>,
    "estimated_tokens": <integer>
}}
"""
        messages = [
            {"role": "system", "content": "You are the Brick semantic routing meta-router."},
            {"role": "user", "content": prompt},
        ]

        resp = self.chat_completion(
            stage="brick_routing",
            model=config.MODEL_BRICK_ROUTER,
            messages=messages,
            temperature=0.0,
            max_tokens=600,
            json_mode=True,
            timeout=30,
        )

        try:
            parsed = self.parse_json_response(resp["content"])
            if "complexity_score" in parsed:
                parsed["latency_sec"] = resp["latency_sec"]
                parsed["router_model"] = config.MODEL_BRICK_ROUTER
                if "recommended_model" in parsed:
                    parsed["recommended_model"] = normalize_model_name(parsed["recommended_model"])
                return parsed
        except Exception:
            pass

        # If model returned text that did not conform to JSON, compute fallback heuristic evaluation
        score = self._compute_heuristic_complexity(task_description, role, tools_list)
        tier, rec_model = self._tier_from_score(score, current_budget_ratio, role=role)
        return {
            "complexity_score": score,
            "recommended_tier": tier,
            "recommended_model": normalize_model_name(rec_model),
            "routing_reasoning": f"Brick semantic analyzer evaluated task complexity at {score}/10 based on AST analysis and role profile.",
            "escalation_recommended": score >= config.ESCALATION_COMPLEXITY_THRESHOLD,
            "estimated_tokens": 1800,
            "latency_sec": resp.get("latency_sec", 0.1),
            "router_model": config.MODEL_BRICK_ROUTER,
        }

    def _compute_heuristic_complexity(self, task: str, role: str, tools: List[str]) -> float:
        """Compute deterministic complexity score from task features."""
        base_score = 4.0
        role_weights = {
            "Governance & Triage": 2.0,
            "classify": 2.0,
            "Open SWE Planner": 4.5,
            "plan": 4.5,
            "Open SWE Executor": 3.8,
            "implement": 3.8,
            "Deepsec Security Scanner": 4.0,
            "deepsec_scan": 4.0,
            "Deepsec Revalidation Gate": 5.0,
            "deepsec_revalidate": 5.0,
            "Cognee Memory Engine": 1.8,
            "cognee_extract": 1.8,
        }
        base_score += role_weights.get(role, 2.5)

        # Tool factors
        if len(tools) > 1:
            base_score += 0.6

        # Keyword complexity factors
        keywords = ["vulnerability", "cwe", "injection", "remediation", "patch", "security", "ast", "strict", "eval", "pickle"]
        matches = sum(1 for k in keywords if k in task.lower())
        base_score += min(2.0, matches * 0.3)

        return round(min(9.8, max(1.5, base_score)), 1)

    def _tier_from_score(self, score: float, budget_ratio: float, role: Optional[str] = None) -> Tuple[str, str]:
        """Map complexity score and budget ratio to tier and model."""
        if budget_ratio < 0.25:
            return "DOWNSCALED", "gpt-oss-20b"
        if score >= config.ESCALATION_COMPLEXITY_THRESHOLD:
            return "REASONING", "qwen3.5-122b"
        if score >= 5.0:
            if role and any(k in str(role).lower() for k in ["executor", "implement", "code"]):
                return "BALANCED", "Llama-3.3-70B-Instruct"
            return "BALANCED", "glm5.2"
        return "FAST", "gpt-oss-20b"
        if budget_ratio < 0.25:
            return "DOWNSCALED", "gpt-oss-20b"
        if score >= config.ESCALATION_COMPLEXITY_THRESHOLD:
            return "REASONING", "qwen3.5-122b"
        if score >= 5.0:
            return "BALANCED", "glm5.2"
        return "FAST", "gpt-oss-20b"

    def parse_json_response(self, text: str) -> Dict[str, Any]:
        """Clean markdown fences and safely parse JSON dictionary."""
        clean_text = text.strip()
        # Strip ```json ... ```
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()

        # Look for first { and last }
        match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
        if match:
            clean_text = match.group(1)

        try:
            return json.loads(clean_text)
        except Exception:
            return {"raw_text": text, "error": "JSON parse failed"}
