import requests


class LocalLLM:
    def __init__(self, model_name="llama3", endpoint="http://localhost:11434/api/generate"):
        self.model_name = model_name
        self.endpoint = endpoint

    def query(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": f"System: {system_prompt}\n\nUser: {user_prompt}",
            "stream": False,
            "options": {"temperature": 0.2}
        }
        try:
            response = requests.post(self.endpoint, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except Exception:
            pass

        # Mock Fallback to guarantee execution without dependencies
        is_dreaming_prompt = "you are a dreaming memory consolidator" in system_prompt.lower()
        if is_dreaming_prompt:
            return """# consolidated_memory.md
- **Multi-agent orchestration**: Platform features launched at CWC 2026.
- **Dreaming**: Scheduled background job that reads and consolidates raw conversation history.
- **Reference URL**: Installed notes at https://example.com/notes/cma

# _index.md
- `consolidated_memory.md`: Core system launches from CWC 2026 conference.
- `event-logistics.md`: Schedule and timeline for conference events."""
        else:
            return "Mock Agent: Saved key notes from CWC 2026. Memory store successfully written."


class RegoloLLM:
    """LLM client for Regolo API (OpenAI-compatible endpoint)."""

    BASE_URL = "https://api.regolo.ai/v1"

    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.api_key = api_key
        self.endpoint = f"{self.BASE_URL}/chat/completions"

    @classmethod
    def fetch_models(cls) -> list[str]:
        """Fetch available model IDs from the Regolo API."""
        resp = requests.get(f"{cls.BASE_URL}/models", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]

    def query(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        try:
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.HTTPError as e:
            raise RuntimeError(
                f"Regolo API error {response.status_code}: {response.text}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Regolo request failed: {e}") from e
