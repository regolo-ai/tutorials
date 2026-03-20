import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List


class RegoloClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.regolo.ai/v1",
        timeout: int = 60,
        mock_if_no_key: bool = True,
    ) -> None:
        self.api_key = api_key or os.getenv("REGOLO_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.mock_if_no_key = mock_if_no_key

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            if self.mock_if_no_key:
                return self._mock_chat_completion(payload)
            raise RuntimeError(
                "Missing REGOLO_API_KEY. Set it in the environment or keep mock_if_no_key=True."
            )

        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        request = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Regolo API error {e.code}: {error_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error calling Regolo API: {e}") from e

    def responses(self, model: str, input: Any) -> Dict[str, Any]:
        if isinstance(input, dict):
            user_content = json.dumps(input, ensure_ascii=False, indent=2)
        else:
            user_content = str(input)

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a field-service support assistant. "
                        "Return concise, safe, actionable recommendations. "
                        "If safety risk exists, explicitly recommend human technician escalation."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
        }

        data = self._post_json("/chat/completions", payload)
        message = data["choices"][0]["message"]["content"]

        parsed_content: Any
        try:
            parsed_content = json.loads(message)
        except Exception:
            parsed_content = message

        return {
            "model": model,
            "content": parsed_content,
            "raw": data,
        }

    def _mock_chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        user_text = payload["messages"][-1]["content"].lower()

        safety = any(
            keyword in user_text
            for keyword in ["smoke", "overheat", "shock", "fire", "critical"]
        )

        if "firmware" in user_text or "update" in user_text or "version" in user_text:
            root_cause = "Possible firmware mismatch or failed update sequence"
            actions = [
                "Confirm installed firmware version",
                "Compare device version with approved baseline",
                "Retry update only after backing up the current configuration",
            ]
        elif "network" in user_text or "latency" in user_text or "offline" in user_text:
            root_cause = "Possible connectivity issue or unstable local network"
            actions = [
                "Check link status and signal quality",
                "Verify gateway reachability",
                "Collect network logs before replacing hardware",
            ]
        elif "motor" in user_text or "noise" in user_text or "mechanical" in user_text:
            root_cause = "Possible mechanical wear or alignment problem"
            actions = [
                "Power down the unit safely",
                "Inspect moving parts for visible wear",
                "Check alignment against maintenance manual",
            ]
        else:
            root_cause = "Insufficient evidence for a reliable remote diagnosis"
            actions = [
                "Collect device logs",
                "Attach a photo of the equipment label",
                "Request technician review",
            ]

        result = {
            "root_cause_hypothesis": root_cause,
            "safe_next_actions": actions,
            "technician_escalation_required": safety or "insufficient evidence" in root_cause.lower(),
        }

        return {
            "id": "mock-regolo-response",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(result, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
        }


regolo = RegoloClient()

REGOLO_CHAT_MODEL = os.getenv("REGOLO_CHAT_MODEL", "Llama-3.3-70B-Instruct")
REGOLO_REASONING_MODEL = os.getenv("REGOLO_REASONING_MODEL", REGOLO_CHAT_MODEL)

SAFETY_KEYWORDS = {"smoke", "overheat", "shock", "fire", "critical"}

LABEL_RULES: Dict[str, Dict[str, Any]] = {
    "firmware": {
        "keywords": {"firmware", "update", "version", "patch", "bootloop", "flash"},
        "draft_steps": [
            "Check installed firmware version",
            "Compare version against approved baseline",
            "Retry update only after backup",
        ],
    },
    "network": {
        "keywords": {"network", "offline", "latency", "wifi", "ethernet", "gateway"},
        "draft_steps": [
            "Verify physical and wireless connectivity",
            "Check gateway reachability",
            "Collect network logs before replacement",
        ],
    },
    "mechanical": {
        "keywords": {"motor", "noise", "vibration", "mechanical", "belt", "bearing"},
        "draft_steps": [
            "Stop the unit safely",
            "Inspect visible wear and alignment",
            "Check maintenance history for repeated faults",
        ],
    },
    "electrical": {
        "keywords": {"voltage", "fuse", "breaker", "power", "electrical", "short"},
        "draft_steps": [
            "Verify power source and breaker state",
            "Inspect fuse path if safe to do so",
            "Do not continue if overheating or burning smell is present",
        ],
    },
}


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def local_model_classify(text: str) -> Dict[str, Any]:
    tokens = set(tokenize(text))
    scores: List[tuple[str, int]] = []

    for label, config in LABEL_RULES.items():
        matches = len(tokens.intersection(config["keywords"]))
        scores.append((label, matches))

    best_label, best_score = max(scores, key=lambda x: x[1])

    if best_score == 0:
        return {
            "label": "unknown",
            "confidence": 0.45,
            "draft_steps": [
                "Collect device logs",
                "Attach a clear photo of the label or error screen",
                "Escalate if the issue affects safety or production continuity",
            ],
        }

    confidence = min(0.55 + best_score * 0.12, 0.91)
    if len(text.strip()) < 40:
        confidence = min(confidence, 0.68)

    return {
        "label": best_label,
        "confidence": round(confidence, 2),
        "draft_steps": LABEL_RULES[best_label]["draft_steps"],
    }


def should_escalate(local_result: Dict[str, Any], text: str) -> bool:
    if local_result["confidence"] < 0.72:
        return True
    if local_result["label"] == "unknown":
        return True
    if any(k in text.lower() for k in SAFETY_KEYWORDS):
        return True
    return False


def build_enterprise_prompt(ticket_id: str, ticket_text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    metadata = metadata or {}

    return {
        "task": "Enterprise incident triage and resolution planning",
        "overview": (
            "You are a senior incident response analyst for a Fortune 500 field support team. "
            "Evaluate stabilization, root cause, impact, and escalation plan, composing a structured JSON response."
        ),
        "ticket": {
            "ticket_id": ticket_id,
            "summary": ticket_text[:200],
            "details": ticket_text,
            "metadata": metadata,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "category": {"type": "string"},
                "priority": {"type": "string"},
                "sla_level": {"type": "string"},
                "impact": {"type": "string"},
                "root_cause_hypothesis": {"type": "string"},
                "initial_mitigation_steps": {"type": "array", "items": {"type": "string"}},
                "long_term_fix_recommendation": {"type": "string"},
                "escalation_path": {"type": "string"},
                "follow_up_questions": {"type": "array", "items": {"type": "string"}},
                "stakeholders_to_notify": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number"},
            },
            "required": ["ticket_id", "category", "priority", "root_cause_hypothesis", "initial_mitigation_steps"],
        },
        "instructions": [
            "Return ONLY JSON matching output_schema (no markdown)",
            "Use concise enterprise-operational language",
            "Preserve fields even if unknown (use 'unknown' or empty list)",
            "Include escalation path to L2/L3 if hazard or production outage"
        ],
    }


def route_ticket_enterprise(ticket_text: str, ticket_id: str = "AUTO-0001", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    prompt = build_enterprise_prompt(ticket_id=ticket_id, ticket_text=ticket_text, metadata=metadata)

    cloud_result = regolo.responses(model=REGOLO_REASONING_MODEL, input=prompt)

    parsed: Any = cloud_result["content"]
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except Exception:
            parsed = {
                "ticket_id": ticket_id,
                "category": "unknown",
                "priority": "unknown",
                "sla_level": "unknown",
                "impact": "unknown",
                "root_cause_hypothesis": "Could not parse Regolo output",
                "initial_mitigation_steps": [],
                "long_term_fix_recommendation": "",
                "escalation_path": "",
                "follow_up_questions": [],
                "stakeholders_to_notify": [],
                "confidence": 0.0,
                "raw_text": parsed,
            }

    # Ensure required data shape
    parsed = {
        "ticket_id": ticket_id,
        "mode": "regolo_escalation",
        "model_used": REGOLO_REASONING_MODEL,
        **(parsed if isinstance(parsed, dict) else {}),
    }

    return parsed


def route_ticket(ticket_text: str) -> Dict[str, Any]:
    return route_ticket_enterprise(ticket_text=ticket_text)


if __name__ == "__main__":
    tickets = [
        "Device shows firmware update failed after patch. It is stuck in bootloop.",
        "Machine reports high latency and goes offline every 10 minutes.",
        "There is smoke near the power module and the unit smells hot.",
        "The unit is acting weird.",
    ]

    for idx, ticket in enumerate(tickets, start=1):
        outcome = route_ticket(ticket)
        print(f"\n--- Ticket {idx} ---")
        print(ticket)
        print(json.dumps(outcome, indent=2, ensure_ascii=False))
