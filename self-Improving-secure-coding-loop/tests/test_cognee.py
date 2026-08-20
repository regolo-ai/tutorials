"""Unit tests for Cognee Memory Graph."""

import tempfile
from pathlib import Path
from core.cognee_memory import CogneeMemoryGraph


def test_cognee_memory_graph():
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        tmp_path = Path(tmp.name)
        memory = CogneeMemoryGraph(db_path=tmp_path)

        stats = memory.get_stats()
        assert stats["total_nodes"] > 0
        assert stats["rules_count"] > 0

        # Query patterns
        patterns = memory.query_relevant_patterns("Fix SQL Injection in user search", ["app.py"])
        assert len(patterns) >= 1
        assert any("SQL" in str(p) for p in patterns)

        # Record new learning
        new_node = memory.record_learning(
            issue_id="ISSUE-TEST-1",
            issue_title="Parameterized query enforcement",
            files_modified=["app.py"],
            vulnerabilities_fixed=["CWE-89"],
            fix_summary="Used sqlite3 parameterized binding",
            test_passed=True,
            human_decision="APPROVED",
            pattern_learned="Always bind SQL parameters with tuples",
        )
        assert new_node["id"] in memory.nodes
        assert memory.get_stats()["total_nodes"] == stats["total_nodes"] + 1
