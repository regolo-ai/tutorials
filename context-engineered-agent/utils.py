import re
import json

def estimate_tokens(text: str) -> int:
    """Simple token heuristic based on character-to-token distribution."""
    return max(1, len(text) // 4)

def calculate_history_tokens(messages) -> int:
    """Calculates total estimated tokens in message thread."""
    return sum(estimate_tokens(msg.get("content", "")) for msg in messages)

def extract_json(text: str):
    """Extracts and parses JSON structures safely from raw LLM text block outputs."""
    text = text.strip()
    match = re.search(r"```(?:json)?\\s*({.*?})\\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
    return None