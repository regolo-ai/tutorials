import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
REGOLO_BASE_URL = "https://api.regolo.ai/v1"

# Runtime config — set by main.py before any use
_backend: str = "ollama"
_model: str = "llama3"
_api_key: str | None = None


def configure(backend: str, model: str, api_key: str | None = None) -> None:
    """Configure the active LLM backend for the whole session."""
    global _backend, _model, _api_key
    _backend = backend
    _model = model
    _api_key = api_key


def query_llm(prompt: str, system_prompt: str = "") -> str:
    """Unified interface: routes the call to the active backend."""
    if _backend == "regolo":
        return _query_regolo(prompt, system_prompt)
    return _query_ollama(prompt, system_prompt)


def _query_ollama(prompt: str, system_prompt: str = "") -> str:
    """Calls the local Ollama server via /api/generate."""
    payload = {
        "model": _model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        return f"Error connecting to Ollama: {str(e)}"


def _query_regolo(prompt: str, system_prompt: str = "") -> str:
    """Calls the Regolo API (OpenAI-compatible) via /v1/chat/completions."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": _model,
        "messages": messages,
        "temperature": 0.0
    }
    headers = {
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(
            f"{REGOLO_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Error connecting to Regolo: {str(e)}"