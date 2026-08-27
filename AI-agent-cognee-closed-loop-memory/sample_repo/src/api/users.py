from typing import Any, Dict, List, Optional
from src.core.context import get_current_tenant_id

SAMPLE_USERS_DB = [
    {"id": 1, "username": "alice", "email": "alice@tenant1.com", "tenant_id": 1, "role": "admin"},
    {"id": 2, "username": "bob", "email": "bob@tenant1.com", "tenant_id": 1, "role": "developer"},
    {"id": 3, "username": "alice", "email": "alice@tenant2.com", "tenant_id": 2, "role": "admin"},
    {"id": 4, "username": "charlie", "email": "charlie@tenant2.com", "tenant_id": 2, "role": "member"},
]

async def search_users(query_str: str, client_tenant_override: Optional[int] = None) -> List[Dict[str, Any]]:
    tenant_id = get_current_tenant_id()
    clean_query = query_str.strip().lower()
    return [
        u for u in SAMPLE_USERS_DB
        if u["tenant_id"] == tenant_id and clean_query in u["username"].lower()
    ]