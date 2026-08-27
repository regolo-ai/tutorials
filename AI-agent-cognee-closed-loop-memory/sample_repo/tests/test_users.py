"""Test suite for User Search Endpoint & Tenant Isolation (sample_repo).
Validates ADR-001 (Tenant Isolation) and ADR-003 (Parameterized Queries / IDOR Protection).
"""

import asyncio
import sys
from pathlib import Path

# Ensure sample_repo is in python path
sample_repo_root = Path(__file__).resolve().parent.parent
if str(sample_repo_root) not in sys.path:
    sys.path.insert(0, str(sample_repo_root))

from src.core.context import set_current_tenant_id, get_current_tenant_id
from src.api.users import search_users


def test_tenant_isolation_filter():
    """Verify searching for a user only returns records belonging to the active tenant session."""
    set_current_tenant_id(1)
    results = asyncio.run(search_users("alice"))
    assert len(results) == 1
    assert results[0]["tenant_id"] == 1
    assert results[0]["email"] == "alice@tenant1.com"


def test_cross_tenant_leak_prevention():
    """Verify that tenant 2 context returns tenant 2 user even with duplicate usernames."""
    set_current_tenant_id(2)
    results = asyncio.run(search_users("alice"))
    assert len(results) == 1
    assert results[0]["tenant_id"] == 2
    assert results[0]["email"] == "alice@tenant2.com"


def test_sql_injection_safety():
    """Verify malicious input payload cannot bypass tenant boundary or cause crashes."""
    set_current_tenant_id(1)
    malicious_payload = "' OR 1=1 --"
    results = asyncio.run(search_users(malicious_payload))
    # Malicious string should not match any user or return all rows
    assert len(results) == 0


def test_idor_client_override_forbidden():
    """Verify that a client cannot specify an arbitrary tenant ID to access other tenant data."""
    set_current_tenant_id(1)
    # Attempting to override tenant_id to 2 should be ignored per ADR-001
    results = asyncio.run(search_users("charlie", client_tenant_override=2))
    # Charlie belongs to tenant 2, but session is tenant 1 -> must return 0 results
    assert len(results) == 0
