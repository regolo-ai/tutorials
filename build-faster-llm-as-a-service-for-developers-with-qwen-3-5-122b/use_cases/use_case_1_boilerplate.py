"""Use case 1: generate FastAPI boilerplate from a resource schema."""

from __future__ import annotations

from regolo_client import RegoloClient


def build_fastapi_prompt(resource_name: str, fields: list[dict[str, str]]) -> str:
    fields_str = "\n".join([f"  - {f['name']}: {f['type']}" for f in fields])
    return f"""Generate a complete FastAPI router for a '{resource_name}' resource with these fields:
{fields_str}

Include:
- Pydantic model
- GET /list endpoint
- POST /create endpoint
- DELETE /{resource_name.lower()}/{{id}} endpoint
- In-memory dict as storage (no DB needed for this example)

Output only valid Python code, no explanations."""


def generate_fastapi_endpoint(client: RegoloClient, resource_name: str, fields: list[dict[str, str]]) -> str:
    prompt = build_fastapi_prompt(resource_name, fields)
    return client.chat_completion(messages=[{"role": "user", "content": prompt}])
