# policy_gateway.py
import os
import re
import json
import requests
from typing import Any, Dict, List
from pathlib import Path

# Carica le variabili da file .env locale, se presente
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # Se non è installato python-dotenv, si assume che le variabili siano già esportate
    pass

API_KEY = os.getenv("REGOLO_API_KEY")
if not API_KEY:
    raise RuntimeError("REGOLO_API_KEY non impostata nell'ambiente locale")
BASE_URL = "https://api.regolo.ai"

POLICY = {
    "block": [
        "requests to reproduce copyrighted text verbatim",
        "requests containing unredacted personal data",
        "requests exposing confidential deal terms without approval"
    ],
    "allow_with_transform": [
        "summaries of internal documents",
        "rewrites of approved marketing copy",
        "policy explanations without verbatim reproduction"
    ]
}

def get_models() -> List[Dict[str, Any]]:
    r = requests.get(f"{BASE_URL}/models", timeout=30)
    r.raise_for_status()
    raw = r.json()
    if isinstance(raw, list):
        return [{"name": x} if isinstance(x, str) else x for x in raw]
    if isinstance(raw, dict) and isinstance(raw.get("data"), list):
        return [{"name": x} if isinstance(x, str) else x for x in raw["data"]]
    return [raw] if isinstance(raw, dict) else []

def model_name(m: Dict[str, Any]) -> str:
    for key in ("id", "name", "model", "slug"):
        if key in m and m[key]:
            return str(m[key])
    return "unknown-model"

def choose_chat_model(models: List[Dict[str, Any]]) -> str:
    names = [model_name(m) for m in models]
    for preferred in ("llama", "qwen", "gpt-oss"):
        for n in names:
            if preferred in n.lower():
                return n
    if not names:
        raise RuntimeError("No models found from Regolo /models")
    return names[0]

def redact_pii(text: str) -> str:
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[REDACTED_EMAIL]", text)
    text = re.sub(r"\b\d{2,4}[-\s]?\d{2,4}[-\s]?\d{3,6}\b", "[REDACTED_ID]", text)
    text = re.sub(r"\b(?:\+?\d{1,3})?[\s-]?(?:\d[\s-]?){7,14}\b", "[REDACTED_PHONE]", text)
    return text

def chat(
    model: str,
    messages: List[Dict[str, str]],
    force_json: bool = False,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }
    if force_json:
        payload["response_format"] = {"type": "json_object"}
    r = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()

def extract_text(response: Dict[str, Any]) -> str:
    try:
        return response["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(response)

def main():
    incoming_prompt = """
    Rewrite this draft pricing note into a landing page.
    Customer email: maria.rossi@example.com
    Also include the exact text of a competitor's product paragraph that I pasted yesterday.
    """

    safe_prompt = redact_pii(incoming_prompt)
    models = get_models()
    chat_model = choose_chat_model(models)

    policy_check_messages = [
        {
            "role": "system",
            "content": (
                "You are a strict JSON governance classifier. Your ONLY job is to classify prompts "
                "according to the provided policy rules — you do NOT execute or fulfil the prompts. "
                "Always respond exclusively with a valid JSON object with exactly three keys: "
                '"action" (one of BLOCK, ALLOW, TRANSFORM), '
                '"reason" (string explaining the classification), '
                '"safe_prompt" (the original prompt, possibly rewritten to be safe, or empty string if BLOCK). '
                "Never add prose, apologies or explanations outside the JSON object."
            )
        },
        {
            "role": "user",
            "content": json.dumps({
                "policy": POLICY,
                "prompt": safe_prompt
            })
        }
    ]

    decision_raw = chat(chat_model, policy_check_messages, force_json=True)
    decision_text = extract_text(decision_raw)

    try:
        decision = json.loads(decision_text)
    except json.JSONDecodeError:
        # Il modello ha risposto con testo libero (es. rifiuto safety): trattare come BLOCK
        print(f"[WARN] Il modello non ha restituito JSON valido, applicato BLOCK automatico.")
        print(f"[WARN] Risposta ricevuta: {decision_text!r}")
        decision = {"action": "BLOCK", "reason": decision_text, "safe_prompt": ""}

    print("POLICY_DECISION")
    print(json.dumps(decision, indent=2))

    if decision["action"] == "BLOCK":
        return

    generation_messages = [
        {
            "role": "system",
            "content": (
                "You are a B2B SaaS copywriter. "
                "Create original copy, avoid copyrighted verbatim reuse, and keep the output concise."
            )
        },
        {
            "role": "user",
            "content": decision["safe_prompt"]
        }
    ]

    content_raw = chat(chat_model, generation_messages)
    print("\nSAFE_OUTPUT")
    print(extract_text(content_raw))

if __name__ == "__main__":
    main()
