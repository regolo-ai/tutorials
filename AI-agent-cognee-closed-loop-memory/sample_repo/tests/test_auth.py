"""Test suite for authentication and tenant isolation."""

import asyncio
import sys
from pathlib import Path

sample_repo_root = Path(__file__).resolve().parent.parent
if str(sample_repo_root) not in sys.path:
    sys.path.insert(0, str(sample_repo_root))

from src.api.auth import search_users


def test_tenant_search_isolation():
    """Verify that user search filters by current tenant and rejects SQL injection."""
    malicious_query = "' UNION SELECT * FROM users --"
    # Should not throw syntax error and should only return current tenant records
    results = asyncio.run(search_users(None, malicious_query))
    assert isinstance(results, list)
    for r in results:
        assert r["tenant_id"] == 1
