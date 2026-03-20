"""
Runnable Regolo-only triage example:
- sends all incidents to Regolo's chat completions endpoint

Setup:
    Optional: pip install certifi

Env:
    export REGOLO_API_KEY="your-virtual-key"
    export REGOLO_BASE_URL="https://api.regolo.ai/v1"
    export REGOLO_MODEL="Llama-3.3-70B-Instruct"
    # REGOLO_REASONING_MODEL is also supported as a fallback
"""

import json
import importlib
import os
import re
import uuid
import urllib.error
import urllib.request
import ssl
from pathlib import Path
from typing import Dict, Any, List
import logging

colorama = importlib.import_module("colorama")
Fore = colorama.Fore
Style = colorama.Style
colorama.init(autoreset=True)


def load_dotenv_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv_file(Path(__file__).with_name(".env"))

REGOLO_API_KEY = os.getenv("REGOLO_API_KEY")
REGOLO_BASE_URL = os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
REGOLO_MODEL = os.getenv("REGOLO_MODEL") or os.getenv("REGOLO_REASONING_MODEL", "Llama-3.3-70B-Instruct")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)
RUN_ID = uuid.uuid4().hex[:8]

if not REGOLO_API_KEY:
    raise RuntimeError("Missing REGOLO_API_KEY")

logger.info("Loaded Regolo configuration: base_url=%s model=%s", REGOLO_BASE_URL, REGOLO_MODEL)


def log_step(event: str, message: str, *args: Any, level: int = logging.INFO) -> None:
    formatted_message = message % args if args else message
    if level >= logging.ERROR:
        color = Fore.RED
    elif level >= logging.WARNING:
        color = Fore.YELLOW
    elif event in {"BOOT", "DONE", "OK", "EXIT"}:
        color = Fore.GREEN
    elif event in {"SEND", "RECV", "ROUTE"}:
        color = Fore.CYAN
    else:
        color = Fore.MAGENTA

    logger.log(level, "%s[%s] %s - %s%s", color, RUN_ID, event, formatted_message, Style.RESET_ALL)

def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def build_ssl_context() -> ssl.SSLContext:
    try:
        certifi = importlib.import_module("certifi")
        log_step("TLS", "using certifi trust store", level=logging.DEBUG)
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        log_step("TLS", "certifi not installed; falling back to unverified TLS context", level=logging.WARNING)
        return ssl._create_unverified_context()


def ask_regolo(ticket_text: str) -> Dict[str, Any]:
    log_step("PREP", "preparing Regolo request (ticket_chars=%d)", len(ticket_text))

    system_prompt = """
You are a senior LLMOps incident triage assistant.

Your job:
- classify the incident
- estimate severity
- provide safe immediate actions
- identify owner team
- decide whether a human escalation is required

Rules:
- Be concise and operational.
- Prefer verifiable actions over speculation.
- If compliance/security/customer impact is plausible, escalate.
- Return JSON only.

JSON schema:
{
  "category": "string",
  "severity": "low|medium|high|critical",
  "likely_root_cause": "string",
  "immediate_actions": ["string"],
  "owner_team": "string",
  "customer_impact": "string",
  "escalate_to_human": true,
  "summary": "string"
}
""".strip()

    user_payload = {
        "ticket": ticket_text,
    }

    request_body = json.dumps(
        {
            "model": REGOLO_MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")

    log_step(
        "BUILD",
        "request ready for model=%s endpoint=%s",
        REGOLO_MODEL,
        f"{REGOLO_BASE_URL.rstrip('/')}/chat/completions",
        level=logging.DEBUG,
    )

    request = urllib.request.Request(
        url=f"{REGOLO_BASE_URL.rstrip('/')}/chat/completions",
        data=request_body,
        method="POST",
        headers={
            "Authorization": f"Bearer {REGOLO_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        log_step("SEND", "dispatching request to Regolo")
        with urllib.request.urlopen(request, timeout=60, context=build_ssl_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
        log_step("RECV", "Regolo response received")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        log_step("FAIL", "Regolo request failed with HTTP %s", exc.code, level=logging.ERROR)
        raise RuntimeError(f"Regolo request failed with HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        log_step("FAIL", "Regolo request failed: %s", exc.reason, level=logging.ERROR)
        raise RuntimeError(f"Regolo request failed: {exc.reason}") from exc

    choices = payload.get("choices", [])
    if not choices:
        log_step("FAIL", "Regolo response missing choices: keys=%s", sorted(payload.keys()), level=logging.ERROR)
        raise RuntimeError(f"Regolo response did not include choices: {payload}")

    message = choices[0].get("message", {})
    content = strip_code_fences(message.get("content") or "{}")

    log_step("PARSE", "response content length=%d", len(content), level=logging.DEBUG)

    try:
        result = json.loads(content)
        log_step("OK", "parsed Regolo response successfully")
        return result
    except json.JSONDecodeError:
        log_step("WARN", "Regolo returned non-JSON output; using fallback structure", level=logging.WARNING)
        return {
            "category": "unknown",
            "severity": "high",
            "likely_root_cause": "Model returned non-JSON output; manual review recommended.",
            "immediate_actions": ["Retry with JSON-only prompt constraints.", "Escalate to a human reviewer."],
            "owner_team": "ml-platform",
            "customer_impact": "Unknown",
            "escalate_to_human": True,
            "summary": content[:500],
        }


def route_incident(ticket_text: str) -> Dict[str, Any]:
    log_step("ROUTE", "routing incident through Regolo-only flow")
    result = {
        "mode": "regolo_escalation",
        "cloud_result": ask_regolo(ticket_text),
    }
    log_step("DONE", "incident routing complete")
    return result


if __name__ == "__main__":
    log_step("BOOT", "starting Regolo triage demo")
    sample_ticket = """
    Since last night's deployment, our customer-facing RAG assistant shows much worse answers.
    Citations look irrelevant, p95 latency doubled, and GPU memory alerts appeared on two inference nodes.
    One enterprise customer reported incorrect policy guidance in production.
    Please triage priority and likely cause.
    """

    result = route_incident(sample_ticket)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    log_step("EXIT", "demo finished")
