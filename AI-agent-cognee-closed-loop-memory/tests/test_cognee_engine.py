"""Unit tests for Cognee Knowledge Graph & Memory Engine."""

import shutil
import tempfile
from pathlib import Path
import pytest

from core.cognee_engine import CogneeMemoryEngine


@pytest.fixture
def temp_engine():
    """Create isolated temporary engine instance with seeded initial ADRs."""
    temp_dir = Path(tempfile.mkdtemp())
    graph_f = temp_dir / "test_graph.json"
    vector_f = temp_dir / "test_vector.json"
    log_f = temp_dir / "test_log.json"

    engine = CogneeMemoryEngine(
        graph_file=graph_f,
        vector_file=vector_f,
        session_log_file=log_f,
    )

    # Seed test entities
    engine.add_node(
        node_id="ADR-001",
        node_type="ArchitecturalDecision",
        title="Tenant Isolation via Explicit Context Session",
        content="All database operations must extract tenant_id strictly from verified JWT session context.",
    )
    engine.add_node(
        node_id="ADR-003",
        node_type="ArchitecturalDecision",
        title="Mandatory Parameterized SQLAlchemy Core Queries",
        content="Prohibit all Python f-string or string formatting inside SQL queries. Use select().where().",
    )
    engine.add_node(
        node_id="PR-142",
        node_type="SimilarPR",
        title="Fix SQL injection in search & enforce ADR-003 parameterized query binding",
        content="Refactored user search filter to use SQLAlchemy select(User) and context tenant_id.",
    )
    engine.add_node(
        node_id="CI-FAIL-89",
        node_type="PastCIError",
        title="CI Run #89: Tenant search test suite broke due to unparameterized SQL query",
        content="Test test_tenant_search_isolation failed with SQLSyntaxError when query contained special characters.",
    )
    engine.add_relation("PR-142", "CI-FAIL-89", "FIXES_CI_FAILURE")
    engine.add_relation("PR-142", "ADR-003", "IMPLEMENTS_DECISION")

    yield engine
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_seed_memory_entities(temp_engine):
    """Verify seeded entities and relations."""
    summary = temp_engine.get_graph_summary()
    assert summary["total_nodes"] >= 4
    assert summary["total_edges"] >= 2
    assert "ADR-001" in temp_engine.nodes_data
    assert "ADR-003" in temp_engine.nodes_data


def test_add_custom_node_and_relation(temp_engine):
    """Verify adding custom nodes and querying edges."""
    node = temp_engine.add_node("TEST-01", "SecurityRule", "Custom Rule", "Content description")
    assert node["id"] == "TEST-01"
    assert "TEST-01" in temp_engine.nodes_data

    temp_engine.add_relation("TEST-01", "ADR-001", "TEST_RELATION")
    assert temp_engine.graph.has_edge("TEST-01", "ADR-001")


def test_cognitive_memory_recall(temp_engine):
    """Verify multi-hop graph recall for tenant search query."""
    res = temp_engine.recall_memory("tenant search SQL query")
    assert "memory_prompt_block" in res
    assert len(res["nodes"]) > 0

    node_ids = [n["id"] for n in res["nodes"]]
    # Should recall ADR-001 or ADR-003 or PR-142
    assert any(nid in node_ids for nid in ["ADR-001", "ADR-003", "PR-142", "CI-FAIL-89"])


def test_cognify_sample_repo(temp_engine, tmp_path):
    """Verify cognifying codebase files into graph."""
    # Create small test repo fixture with an ADR and code file
    test_repo = tmp_path / "mini_repo"
    test_repo.mkdir()
    adr_file = test_repo / "ADR-001-tenant-isolation.md"
    adr_file.write_text("# ADR-001: Tenant Isolation\nTenant context is mandatory.", encoding="utf-8")
    code_file = test_repo / "users.py"
    code_file.write_text("async def get_users(): pass", encoding="utf-8")

    res = temp_engine.cognify_codebase(test_repo)
    assert res["status"] == "SUCCESS"
    assert res["scanned_files"] >= 2


def test_update_and_delete_node(temp_engine):
    """Verify modifying node content and deleting node from graph and vector index."""
    # Update node
    updated = temp_engine.update_node("ADR-001", title="Updated Tenant Title", content="Updated Content")
    assert updated is not None
    assert temp_engine.nodes_data["ADR-001"]["title"] == "Updated Tenant Title"
    assert temp_engine.nodes_data["ADR-001"]["content"] == "Updated Content"

    # Delete node
    del_res = temp_engine.delete_node("CI-FAIL-89")
    assert del_res is True
    assert "CI-FAIL-89" not in temp_engine.nodes_data
    assert not temp_engine.graph.has_node("CI-FAIL-89")
    # Verify related edge was also pruned
    assert not any(e["source"] == "CI-FAIL-89" or e["target"] == "CI-FAIL-89" for e in temp_engine.edges_data)


def test_generate_visual_html_graph(temp_engine, tmp_path):
    """Verify HTML graph generation with new exploration menu and node CRUD support."""
    out_html = tmp_path / "test_graph.html"
    path = temp_engine.generate_visual_html_graph(out_html)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "nav-exploration-bar" in content
    assert "openEditNodeModal" in content
    assert "deleteNode" in content
    assert "togglePhysics" not in content  # Physics button removed
