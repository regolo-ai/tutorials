"""Unit tests for Coding Agent Loop (Naive RAG vs Cognee Memory & ReAct Loop)."""

from unittest.mock import patch
import pytest
from core.agent_loop import CodingAgentLoop


def test_agent_loop_benchmark():
    """Verify side-by-side benchmark execution on Regolo.ai."""
    agent_loop = CodingAgentLoop()
    task = "Implement user search endpoint with tenant isolation"

    mock_cognee_gen = {
        "content": "```python\nfrom src.core.context import get_current_tenant_id\nasync def search_users(q):\n    tenant_id = get_current_tenant_id()\n    return []\n```",
        "model": "qwen3-coder-next",
        "complexity_score": 6.2,
        "total_tokens": 120,
        "cost_eur": 0.0001,
        "zero_data_retention": True,
        "simulated": False,
    }
    mock_naive_gen = {
        "content": "```python\nasync def search_users(q, tenant_id):\n    return []\n```",
        "model": "qwen3-coder-next",
        "complexity_score": 6.2,
        "total_tokens": 80,
        "cost_eur": 0.00008,
        "zero_data_retention": True,
        "simulated": False,
    }

    with patch.object(agent_loop.client, "generate", side_effect=[mock_naive_gen, mock_cognee_gen]):
        naive_res = agent_loop.run_naive_rag_agent(task)
        cognee_res = agent_loop.run_cognee_memory_agent(task)

    # Cognee Memory Agent should enforce ADR compliance and high security score
    assert cognee_res.adr_compliance is True
    assert cognee_res.security_score >= 80

    # Naive RAG lacks ADR-001/003 context
    assert isinstance(naive_res.security_score, int)


def test_comparison_benchmark_delta():
    """Verify delta output structure."""
    agent_loop = CodingAgentLoop()
    mock_gen = {
        "content": "```python\nfrom src.core.context import get_current_tenant_id\nasync def search_users(q):\n    tenant_id = get_current_tenant_id()\n    return []\n```",
        "model": "qwen3-coder-next",
        "complexity_score": 6.2,
        "total_tokens": 120,
        "cost_eur": 0.0001,
        "zero_data_retention": True,
        "simulated": False,
    }

    with patch.object(agent_loop.client, "generate", return_value=mock_gen):
        res = agent_loop.run_comparison_benchmark("Search users endpoint")

    assert "naive_rag" in res
    assert "cognee_memory" in res
    assert "delta" in res


def test_react_self_healing_demo():
    """Verify ReAct mini-loop with tool calling and pytest execution."""
    agent_loop = CodingAgentLoop()
    mock_gen = {
        "content": (
            "```python\n"
            "from typing import Any, Dict, List, Optional\n"
            "from src.core.context import get_current_tenant_id\n\n"
            "SAMPLE_USERS_DB = [\n"
            '    {"id": 1, "username": "alice", "email": "alice@tenant1.com", "tenant_id": 1, "role": "admin"},\n'
            '    {"id": 2, "username": "bob", "email": "bob@tenant1.com", "tenant_id": 1, "role": "developer"},\n'
            '    {"id": 3, "username": "alice", "email": "alice@tenant2.com", "tenant_id": 2, "role": "admin"},\n'
            '    {"id": 4, "username": "charlie", "email": "charlie@tenant2.com", "tenant_id": 2, "role": "member"},\n'
            "]\n\n"
            "async def search_users(query_str: str, client_tenant_override: Optional[int] = None) -> List[Dict[str, Any]]:\n"
            "    tenant_id = get_current_tenant_id()\n"
            "    clean_query = query_str.strip().lower()\n"
            "    return [\n"
            '        u for u in SAMPLE_USERS_DB\n'
            '        if u["tenant_id"] == tenant_id and clean_query in u["username"].lower()\n'
            "    ]\n"
            "```"
        ),
        "model": "qwen3-coder-next",
        "complexity_score": 6.2,
        "total_tokens": 250,
        "cost_eur": 0.0005,
        "zero_data_retention": True,
        "simulated": False,
    }

    with patch.object(agent_loop.client, "generate", return_value=mock_gen):
        res = agent_loop.run_react_self_healing_demo("Add user search endpoint")

    assert "steps" in res
    assert len(res["steps"]) >= 4
    assert res["passed_ci"] is True
    assert res["security_score"] >= 80
    assert "pytest_result" in res
    assert res["pytest_result"].get("passed") is True


def test_multi_session_timeline():
    """Verify multi-session timeline simulation."""
    agent_loop = CodingAgentLoop()
    mock_gen = {
        "content": "```python\nfrom src.core.context import get_current_tenant_id\nasync def search_users(q):\n    tenant_id = get_current_tenant_id()\n    return []\n```",
        "model": "qwen3-coder-next",
        "complexity_score": 6.2,
        "total_tokens": 120,
        "cost_eur": 0.0001,
        "zero_data_retention": True,
        "simulated": False,
    }

    with patch.object(agent_loop.client, "generate", return_value=mock_gen):
        res = agent_loop.run_multi_session_timeline_demo()

    assert "timeline" in res
    assert len(res["timeline"]) == 3
    assert res["timeline"][0]["day"] == "Day 1"
    assert res["timeline"][1]["day"] == "Day 2"
    assert res["timeline"][2]["day"] == "Day 15"


def test_causal_trail_demo():
    """Verify causal trail recall."""
    agent_loop = CodingAgentLoop()
    res = agent_loop.run_causal_trail_demo("tenant isolation and parameterized queries")

    assert "nodes" in res
    assert "relations" in res
    assert len(res["nodes"]) > 0
