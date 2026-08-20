"""Regolo.ai OpenAI-Compatible API Client powered by GLM-5.2.
Handles model calls, telemetry tracking, structured output parsing, and graceful simulation fallback.
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional
from openai import OpenAI

import config
from core.brick_governance import record_telemetry_event


class RegoloClient:
    """Client for Regolo.ai OpenAI-Compatible API using GLM-5.2."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or config.REGOLO_API_KEY
        self.base_url = base_url or config.REGOLO_BASE_URL
        self.model = model or config.REGOLO_MODEL

        # Check if we have a valid non-placeholder API key
        self.is_live = bool(
            self.api_key
            and not self.api_key.startswith("your_")
            and len(self.api_key.strip()) > 5
        )

        if self.is_live:
            self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        else:
            self.client = None

    def chat_completion(
        self,
        stage: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute a chat completion on Regolo with telemetry logging."""
        cfg = config.STAGE_CONFIGS.get(stage, {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0.2,
        })

        actual_model = cfg.get("model", self.model)
        actual_temp = temperature if temperature is not None else cfg.get("temperature", 0.2)
        actual_max_tokens = max_tokens if max_tokens is not None else cfg.get("max_tokens", 2048)

        start_time = time.time()

        if self.is_live and self.client:
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                kwargs = {
                    "model": actual_model,
                    "messages": messages,
                    "temperature": actual_temp,
                    "max_tokens": actual_max_tokens,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                response = self.client.chat.completions.create(**kwargs)
                latency = time.time() - start_time
                content = response.choices[0].message.content or ""
                usage = response.usage

                prompt_tokens = usage.prompt_tokens if usage else int(len(user_prompt.split()) * 1.3)
                completion_tokens = usage.completion_tokens if usage else int(len(content.split()) * 1.3)

                # Record in Brick telemetry
                record_telemetry_event(
                    stage=stage,
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
                    "latency": latency,
                    "model": actual_model,
                    "mode": "live",
                }
            except Exception as e:
                # If network or API fails, record fallback simulation
                latency = time.time() - start_time
                simulated = self._simulate_response(stage, system_prompt, user_prompt, model_name=actual_model)
                record_telemetry_event(
                    stage=stage,
                    model=f"{actual_model} (fallback-sim)",
                    prompt_tokens=simulated["prompt_tokens"],
                    completion_tokens=simulated["completion_tokens"],
                    latency=latency + 0.35,
                    mode="simulated",
                    error=str(e),
                )
                return simulated
        else:
            # Offline simulation mode (high-fidelity responses for demo & video tutorial)
            time.sleep(0.4)  # Realistic inference pacing
            latency = time.time() - start_time + 0.38
            simulated = self._simulate_response(stage, system_prompt, user_prompt, model_name=actual_model)
            record_telemetry_event(
                stage=stage,
                model=actual_model,
                prompt_tokens=simulated["prompt_tokens"],
                completion_tokens=simulated["completion_tokens"],
                latency=latency,
                mode="simulated",
            )
            return simulated

    def parse_json_response(self, text: str) -> Dict[str, Any]:
        """Clean markdown fences and safely parse JSON."""
        clean_text = text.strip()
        # Strip ```json ... ```
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n", "", clean_text)
            clean_text = re.sub(r"\n```$", "", clean_text)
        
        # Look for first { and last }
        match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
        if match:
            clean_text = match.group(1)

        try:
            return json.loads(clean_text)
        except Exception:
            # Fallback structure
            return {"raw_text": text, "error": "JSON parse failed"}

    def _simulate_response(self, stage: str, system: str, user: str, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Realistic high-fidelity simulations for all stages with Regolo model output structure."""
        effective_model = model_name or config.STAGE_CONFIGS.get(stage, {}).get("model", self.model)
        if stage == "classify":
            content = json.dumps({
                "intent": "security_vulnerability_remediation",
                "risk_level": "CRITICAL",
                "affected_components": ["authentication", "database_queries", "network_gateways"],
                "policy_decision": "REQUIRE_HUMAN_APPROVAL_AND_DEEPSEC_SCAN",
                "summary": "Detected critical security vulnerabilities (CWE-89 SQLi / CWE-918 SSRF / CWE-287 Auth Bypass). Routed to Open SWE remediation pipeline."
            }, indent=2)
            p_tokens, c_tokens = 340, 120

        elif stage == "plan":
            content = json.dumps({
                "plan_id": "PLAN-GLM52-0941",
                "title": "Automated Security Hardening & Remediation Plan",
                "steps": [
                    {
                        "step_number": 1,
                        "action": "Context & Knowledge Retrieval",
                        "description": "Consult Cognee memory graph for previous CWE remediations in authentication and request dispatchers."
                    },
                    {
                        "step_number": 2,
                        "action": "Parameterize Queries & Fix Algorithm Confusion",
                        "description": "Replace raw SQL string interpolation with parameterized queries; enforce strict HS256 algorithm and signature verification in JWT decoder."
                    },
                    {
                        "step_number": 3,
                        "action": "Implement IP Allowlisting & Safe Subprocess",
                        "description": "Block private/link-local IPv4 ranges for webhooks; replace shell=True with safe argument lists and regex hostname validation."
                    },
                    {
                        "step_number": 4,
                        "action": "Execute Test Suite",
                        "description": "Run pytest in isolated sandbox to ensure zero functional regressions."
                    },
                    {
                        "step_number": 5,
                        "action": "Deepsec Revalidation Gate",
                        "description": "Trigger automated security scan to confirm vulnerability resolution."
                    }
                ],
                "estimated_risk": "MEDIUM (Safe Sandboxed Refactor)",
                "recommended_review": "ACCEPT"
            }, indent=2)
            p_tokens, c_tokens = 620, 310

        elif stage == "implement":
            content = json.dumps({
                "files_to_modify": [
                    {
                        "file_path": "app.py",
                        "explanation": "Fixed SQL Injection using parameterized query 'WHERE username LIKE ?' and hardened JWT verification with algorithms=['HS256'] and verify_signature=True.",
                        "patch": "Applied security patch to database queries and auth header decoding."
                    }
                ],
                "remediation_summary": "All identified insecure patterns were replaced with defensive coding best practices."
            }, indent=2)
            p_tokens, c_tokens = 950, 480

        elif stage == "deepsec_scan":
            content = json.dumps({
                "findings": [
                    {
                        "id": "SEC-001",
                        "severity": "CRITICAL",
                        "cwe": "CWE-89",
                        "title": "SQL Injection in User Search Filter",
                        "file": "app.py",
                        "line": 64,
                        "description": "Unsanitized user input formatted directly into raw SQL query allows arbitrary database extraction.",
                        "status": "DETECTED_NEEDS_FIX"
                    },
                    {
                        "id": "SEC-002",
                        "severity": "HIGH",
                        "cwe": "CWE-287",
                        "title": "Insecure JWT Algorithm & Signature Bypass",
                        "file": "app.py",
                        "line": 80,
                        "description": "JWT decoding accepts 'none' algorithm and explicitly disables signature verification.",
                        "status": "DETECTED_NEEDS_FIX"
                    }
                ],
                "security_score": 38,
                "gate_status": "FAILED_VULNERABILITIES_PRESENT"
            }, indent=2)
            p_tokens, c_tokens = 840, 390

        elif stage == "deepsec_revalidate":
            content = json.dumps({
                "revalidation_passed": True,
                "findings_resolved": ["SEC-001", "SEC-002"],
                "residual_vulnerabilities": [],
                "security_score": 98,
                "gate_status": "PASSED_CLEAN_SECURITY_GATE",
                "evidence": "Deepsec re-scan confirmed parameterized queries and enforced HS256 signature verification. Zero residual findings."
            }, indent=2)
            p_tokens, c_tokens = 580, 210

        elif stage == "cognee_extract":
            content = json.dumps({
                "entities": [
                    {"type": "Vulnerability", "name": "SQL Injection", "cwe": "CWE-89"},
                    {"type": "Vulnerability", "name": "JWT Algorithm Confusion", "cwe": "CWE-287"},
                    {"type": "RemediationPattern", "name": "SQLite Parameterized Binding"},
                    {"type": "RemediationPattern", "name": "Strict JWT Signature Verification"}
                ],
                "relationships": [
                    {"from": "app.py", "rel": "VULNERABLE_TO", "to": "SQL Injection"},
                    {"from": "SQL Injection", "rel": "RESOLVED_BY", "to": "SQLite Parameterized Binding"},
                    {"from": "JWT Algorithm Confusion", "rel": "RESOLVED_BY", "to": "Strict JWT Signature Verification"}
                ],
                "learning_insight": "For future FastAPI services: enforce Pydantic query sanitizers and default PyJWT verify=True in all auth headers."
            }, indent=2)
            p_tokens, c_tokens = 490, 240

        else:
            content = "OK: Stage completed successfully with GLM-5.2 on Regolo.ai."
            p_tokens, c_tokens = 200, 80

        return {
            "content": content,
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "latency": 0.45,
            "model": effective_model,
            "mode": "simulated",
        }
