# architecture_router.py
import os
import json
import requests
from pathlib import Path
from typing import Any, Dict, List, Union

BASE_URL = "https://api.regolo.ai"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(Path(__file__).resolve().with_name(".env"))

API_KEY = os.environ["REGOLO_API_KEY"]

def get_json(url: str) -> Any:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def post_json(url: str, payload: Dict[str, Any]) -> Any:
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()

def normalize_models(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, str):
                out.append({"id": item, "name": item})
            elif isinstance(item, dict):
                out.append(item)
        return out
    if isinstance(raw, dict):
        if isinstance(raw.get("data"), list):
            return normalize_models(raw["data"])
        return [raw]
    return []

def get_model_name(model: Union[str, Dict[str, Any]]) -> str:
    if isinstance(model, str):
        return model
    for key in ("id", "name", "model", "slug"):
        if key in model and model[key]:
            return str(model[key])
    return json.dumps(model)

def pick_model(
    models: List[Dict[str, Any]],
    task: Dict[str, Any],
    preferred_model: str | None = None,
) -> str:
    names = [get_model_name(m) for m in models]
    lowered = [n.lower() for n in names]

    if preferred_model:
        preferred_lower = preferred_model.strip().lower()
        for original, low in zip(names, lowered):
            if preferred_lower == low or preferred_lower in low:
                return original

    def first_match(keywords: List[str]) -> str:
        for original, low in zip(names, lowered):
            if all(k in low for k in keywords):
                return original
        return ""

    if task["need_reasoning"]:
        for kws in (
            ["gpt-oss"],
            ["qwen"],
            ["llama"],
        ):
            match = first_match(kws)
            if match:
                return match

    for kws in (
        ["llama"],
        ["qwen"],
        ["gpt-oss"],
    ):
        match = first_match(kws)
        if match:
            return match

    if names:
        return names[0]
    raise RuntimeError("No Regolo models returned by /models")

def route_task(user_input: str) -> Dict[str, Any]:
    need_reasoning = any(
        token in user_input.lower()
        for token in ["exception", "justify", "why", "compare", "conflict", "policy"]
    )
    return {
        "task_type": "insurance_ops",
        "need_reasoning": need_reasoning,
        "system_prompt": (
            "You are an enterprise insurance operations assistant. "
            "Answer clearly, cite assumptions, and separate facts from recommendations."
        ),
    }

def main():
    user_input = (
        "Explain whether this claim note should trigger a manual review. "
        "There is a policy exception around delayed reporting and conflicting loss descriptions."
    )

    models_raw = get_json(f"{BASE_URL}/models")
    models = normalize_models(models_raw)
    task = route_task(user_input)
    selected_model = pick_model(models, task, os.environ.get("REGOLO_CORE_MODEL"))

    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": task["system_prompt"]},
            {"role": "user", "content": user_input},
        ],
        "temperature": 0.2,
    }

    if task["need_reasoning"]:
        payload["thinking"] = True

    result = post_json(f"{BASE_URL}/v1/chat/completions", payload)
    print(json.dumps({
        "selected_model": selected_model,
        "need_reasoning": task["need_reasoning"],
        "response": result
    }, indent=2))

if __name__ == "__main__":
    main()
