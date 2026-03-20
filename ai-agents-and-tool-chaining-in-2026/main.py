#!/usr/bin/env python3
import os
import sys
import json
import re
import ssl
from pathlib import Path
from typing import List, Dict, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

def load_local_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key or key in os.environ:
            continue

        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        os.environ[key] = value


load_local_env()

BASE_URL = os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai")
API_KEY = os.getenv("REGOLO_API_KEY")

if not API_KEY:
    raise SystemExit("Missing REGOLO_API_KEY environment variable.")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def _build_ssl_context(allow_insecure: bool = False) -> ssl.SSLContext:
    if allow_insecure:
        return ssl._create_unverified_context()
    return ssl.create_default_context()


def _request_json(
    method: str,
    path: str,
    payload: Dict[str, Any] | None = None,
    timeout: int = 60,
    allow_insecure_tls: bool | None = None,
) -> Any:
    body = None
    headers = dict(HEADERS)
    if allow_insecure_tls is None:
        allow_insecure_tls = os.getenv("REGOLO_INSECURE_TLS", "").strip().lower() in {"1", "true", "yes", "on"}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Length"] = str(len(body))

    request = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=timeout, context=_build_ssl_context(allow_insecure_tls)) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace") if error.fp else ""
        raise RuntimeError(
            f"HTTP {error.code} calling {method} {path}: {error_body or error.reason}"
        ) from error
    except URLError as error:
        if not allow_insecure_tls and isinstance(error.reason, ssl.SSLCertVerificationError):
            print(
                f"Warning: TLS certificate verification failed for {method} {path}; retrying with REGOLO_INSECURE_TLS=1.",
                file=sys.stderr,
            )
            return _request_json(method, path, payload=payload, timeout=timeout, allow_insecure_tls=True)

        raise RuntimeError(f"Network error calling {method} {path}: {error.reason}") from error

DEFAULT_POLICY_DOCS = [
    "Standard payment term is net 30. Any net 60 or longer requires finance approval.",
    "Auto-renewal longer than 12 months requires legal review.",
    "Annual uplift above 5% requires VP approval.",
    "Custom exception clauses must be reviewed by finance before approval.",
    "If contract language conflicts with policy, escalate to human review."
]

SAMPLE_CONTRACT = """
Vendor: Acme Cloud Ltd.
Agreement term: 24 months.
Payment terms: Net 60 from invoice date.
Renewal: Automatically renews for 24 months unless cancelled 30 days before renewal.
Pricing: €120,000 annual subscription with 8% annual uplift.
Special clause: Customer may request billing deferral for 45 additional days in exceptional cases.
"""

def http_get(path: str) -> Any:
    return _request_json("GET", path, timeout=60)

def http_post(path: str, payload: Dict[str, Any]) -> Any:
    return _request_json("POST", path, payload=payload, timeout=120)

def list_models() -> List[str]:
    data = http_get("/models")
    if isinstance(data, dict) and "data" in data:
        return [item["id"] for item in data["data"] if isinstance(item, dict) and "id" in item]
    if isinstance(data, list):
        ids = []
        for item in data:
            if isinstance(item, dict) and "id" in item:
                ids.append(item["id"])
            elif isinstance(item, str):
                ids.append(item)
        return ids
    return []

def pick_chat_model(model_ids: List[str]) -> str:
    env_model = os.getenv("REGOLO_CHAT_MODEL")
    if env_model:
        return env_model

    preferred_patterns = [
        r"llama.*instruct",
        r"qwen.*instruct",
        r"gpt-oss",
        r"mistral",
    ]

    lowered = [(m, m.lower()) for m in model_ids]
    for pattern in preferred_patterns:
        for original, low in lowered:
            if re.search(pattern, low) and "vision" not in low and "embed" not in low and "rerank" not in low:
                return original

    return "Llama-3.3-70B-Instruct"

def pick_rerank_model(model_ids: List[str]) -> str:
    env_model = os.getenv("REGOLO_RERANK_MODEL")
    if env_model:
        return env_model

    for m in model_ids:
        low = m.lower()
        if "rerank" in low or "reranker" in low:
            return m

    return "Qwen3-Reranker-4B"

def chat_completion(model: str, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }
    data = http_post("/v1/chat/completions", payload)
    return data["choices"][0]["message"]["content"]

def rerank_documents(model: str, query: str, documents: List[str], top_n: int = 3) -> List[Dict[str, Any]]:
    payload = {
        "model": model,
        "query": query,
        "documents": documents,
        "top_n": top_n
    }
    data = http_post("/rerank", payload)
    results = data.get("results", [])
    normalized = []
    for item in results:
        doc = item.get("document", {})
        if isinstance(doc, dict):
            text = doc.get("text", "")
        else:
            text = str(doc)
        normalized.append({
            "text": text,
            "score": item.get("relevance_score", 0.0)
        })
    return normalized

def extract_json_block(text: str, required_keys: set[str] | None = None) -> Dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if required_keys is None or required_keys.issubset(data.keys()):
            return data
    except json.JSONDecodeError:
        pass

    candidates = []
    start = None
    depth = 0
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if start is None:
            if char == "{":
                start = index
                depth = 1
                in_string = False
                escape = False
            continue

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                block = text[start:index + 1]
                try:
                    candidates.append(json.loads(block))
                except json.JSONDecodeError:
                    pass
                start = None

    if required_keys is not None:
        for candidate in candidates:
            if isinstance(candidate, dict) and required_keys.issubset(candidate.keys()):
                return candidate

    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate

    if candidates:
        raise ValueError("Model output contained JSON, but not a JSON object.")

    raise ValueError(f"Could not parse complete JSON object from model output:\n{text}")

def extract_contract_fields(contract_text: str, chat_model: str) -> Dict[str, Any]:
    system = (
        "You are a strict contract extraction engine. "
        "Return only valid JSON with no markdown."
    )
    user = f"""
Extract these fields from the contract text and return exactly one JSON object:
{{
  "vendor": "string",
  "payment_terms_days": integer or null,
  "auto_renewal_months": integer or null,
  "uplift_percent": number or null,
  "special_clauses": ["string", "..."],
  "term_months": integer or null
}}

Rules:
- Infer numeric values only when explicitly stated.
- If absent, use null.
- Do not include extra keys.

Contract:
{contract_text}
""".strip()

    raw = chat_completion(
        model=chat_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
    )
    return extract_json_block(raw)

def decide_action(
    contract_text: str,
    extracted: Dict[str, Any],
    top_policy_docs: List[Dict[str, Any]],
    chat_model: str
) -> Dict[str, Any]:
    evidence = [item["text"] for item in top_policy_docs if isinstance(item, dict) and item.get("text")]

    payment_terms_days = extracted.get("payment_terms_days")
    auto_renewal_months = extracted.get("auto_renewal_months")
    uplift_percent = extracted.get("uplift_percent")
    special_clauses = extracted.get("special_clauses") or []

    violations = []
    action = "approve_standard_terms"

    if isinstance(auto_renewal_months, (int, float)) and auto_renewal_months > 12:
        action = "ask_human"
        violations.append(f"auto-renewal is {auto_renewal_months} months, above the 12-month policy limit")

    if isinstance(uplift_percent, (int, float)) and uplift_percent > 5:
        action = "ask_human"
        violations.append(f"uplift is {uplift_percent}%, above the 5% policy limit")

    if action == "approve_standard_terms":
        if isinstance(payment_terms_days, (int, float)) and payment_terms_days > 30:
            action = "create_finance_ticket"
            violations.append(f"payment terms are net {payment_terms_days}, above the net 30 policy limit")

        if special_clauses:
            action = "create_finance_ticket"
            violations.append("special clauses require finance review")

    if not violations:
        return {
            "action": "approve_standard_terms",
            "reason": "The extracted contract terms are within the stated policy limits.",
            "evidence": evidence[:4],
            "confidence": 0.96,
        }

    if action == "ask_human":
        reason = " and ".join(violations)
    else:
        reason = "; ".join(violations)

    return {
        "action": action,
        "reason": reason,
        "evidence": evidence[:4],
        "confidence": 0.98 if action == "ask_human" else 0.93,
    }

def validate_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    required = {"action", "reason", "evidence", "confidence"}
    missing = required - set(decision.keys())
    if missing:
        raise ValueError(f"Decision missing required fields: {missing}")

    if decision["action"] not in {"approve_standard_terms", "create_finance_ticket", "ask_human"}:
        raise ValueError(f"Invalid action: {decision['action']}")

    if not isinstance(decision["evidence"], list) or not decision["evidence"]:
        raise ValueError("Evidence must be a non-empty list.")

    confidence = float(decision["confidence"])
    if confidence < 0 or confidence > 1:
        raise ValueError("Confidence must be between 0 and 1.")

    decision["confidence"] = confidence
    return decision

def load_contract_text() -> str:
    if len(sys.argv) > 1:
        path = sys.argv[1]
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return SAMPLE_CONTRACT.strip()

def main() -> None:
    contract_text = load_contract_text()
    model_ids = list_models()

    chat_model = pick_chat_model(model_ids)
    rerank_model = pick_rerank_model(model_ids)

    extracted = extract_contract_fields(contract_text, chat_model)

    rerank_query = (
        "Which policy passages are relevant to payment terms, auto-renewal, uplift, "
        "and special clause exceptions for this contract?"
    )
    ranked_policy = rerank_documents(
        model=rerank_model,
        query=rerank_query,
        documents=DEFAULT_POLICY_DOCS,
        top_n=4
    )

    decision = decide_action(contract_text, extracted, ranked_policy, chat_model)
    decision = validate_decision(decision)

    result = {
        "selected_models": {
            "chat_model": chat_model,
            "rerank_model": rerank_model
        },
        "extracted_contract_fields": extracted,
        "ranked_policy_evidence": ranked_policy,
        "final_decision": decision
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
