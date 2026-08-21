"""Cognee Engineering Memory & Knowledge Graph Layer.
Provides persistent memory across sessions: records issues, vulnerabilities, fixes, decisions,
and builds an interconnected knowledge graph so future coding tasks learn from past PRs.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import config

logger = logging.getLogger(__name__)


class CogneeMemoryGraph:
    """Persistent Graph & Knowledge Memory store for engineering agents."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        client: Optional[Any] = None,
    ):
        self.db_path = db_path or config.COGNEE_DB_PATH
        self.client = client
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self._load_database()

    def _load_database(self):
        """Load graph from JSON store or seed default corporate memory."""
        if self.db_path.exists():
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.nodes = data.get("nodes", {})
                    self.edges = data.get("edges", [])
                    return
            except Exception as e:
                logger.warning(f"Could not load cognee database: {e}")
        self._seed_default_memory()

    def _save_database(self):
        """Persist graph to JSON store."""
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump({"nodes": self.nodes, "edges": self.edges}, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save cognee database: {e}")

    def _seed_default_memory(self):
        """Seed initial engineering graph memory with historical learnings."""
        self.nodes = {
            "RULE-01": {
                "id": "RULE-01",
                "type": "SecurityRule",
                "name": "SQL Query Parameterization Rule",
                "description": "Never use Python f-strings or string concatenation in SQLite/Postgres queries. Always pass tuples as query parameters.",
                "cwe": "CWE-89",
                "created_at": time.time() - 86400 * 5,
            },
            "RULE-02": {
                "id": "RULE-02",
                "type": "SecurityRule",
                "name": "Strict JWT Signature & Algorithm Whitelisting",
                "description": "Enforce explicit algorithms=['HS256'] and options={'verify_signature': True} in all PyJWT decode calls to prevent algorithm confusion attacks.",
                "cwe": "CWE-287",
                "created_at": time.time() - 86400 * 4,
            },
            "RULE-03": {
                "id": "RULE-03",
                "type": "SecurityRule",
                "name": "SSRF Defense in Depth: Private IP Filter",
                "description": "All external webhook callers must resolve DNS and reject RFC1918 private IPv4 subnets (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.1, 169.254.169.254).",
                "cwe": "CWE-918",
                "created_at": time.time() - 86400 * 3,
            },
            "RULE-04": {
                "id": "RULE-04",
                "type": "SecurityRule",
                "name": "Subprocess Safe Argument List Enforcement",
                "description": "Never use shell=True in subprocess calls. Use list arguments ['ping', '-c', '1', host] with strict hostname regex validation.",
                "cwe": "CWE-78",
                "created_at": time.time() - 86400 * 2,
            },
            "RULE-05": {
                "id": "RULE-05",
                "type": "SecurityRule",
                "name": "Path Traversal & Storage Boundary Defense",
                "description": "Always extract filename base with Path.name and verify target.is_relative_to(STORAGE_DIR) to block directory traversal attacks.",
                "cwe": "CWE-22",
                "created_at": time.time() - 86400 * 2,
            },
            "RULE-06": {
                "id": "RULE-06",
                "type": "SecurityRule",
                "name": "Safe AST Math Evaluation & JSON Deserialization",
                "description": "Never use eval() or pickle.loads() on user input. Use abstract syntax tree (ast.parse) operator whitelist and standard json.loads.",
                "cwe": "CWE-94 / CWE-502",
                "created_at": time.time() - 86400 * 1,
            },
            "RULE-07": {
                "id": "RULE-07",
                "type": "SecurityRule",
                "name": "Secrets Management & CSPRNG Standard",
                "description": "Never hardcode private keys in repository. Load from environment variables and use secrets.token_hex for cryptographic tokens.",
                "cwe": "CWE-798 / CWE-338",
                "created_at": time.time() - 86400 * 1,
            },
            "RULE-08": {
                "id": "RULE-08",
                "type": "SecurityRule",
                "name": "XSS Sanitization & Strict Pydantic Models",
                "description": "Always escape user-rendered HTML with html.escape and define explicit Pydantic fields to block Mass Assignment privilege escalation.",
                "cwe": "CWE-79 / CWE-915",
                "created_at": time.time() - 86400 * 1,
            },
            "DECISION-99": {
                "id": "DECISION-99",
                "type": "HumanDecision",
                "name": "PR #89 Human Review Policy",
                "description": "Human security lead accepted parameterized query standard and mandated automated Deepsec revalidation before merge.",
                "status": "APPROVED",
                "created_at": time.time() - 86400 * 1,
            },
        }

        self.edges = [
            {"from": "RULE-01", "rel": "ENFORCED_BY", "to": "DECISION-99"},
            {"from": "RULE-02", "rel": "PROTECTS", "to": "AuthService"},
            {"from": "RULE-03", "rel": "PROTECTS", "to": "WebhookGateway"},
            {"from": "RULE-04", "rel": "PROTECTS", "to": "SystemDiagnostics"},
            {"from": "RULE-05", "rel": "PROTECTS", "to": "FileStorage"},
            {"from": "RULE-06", "rel": "PROTECTS", "to": "AnalyticsEngine"},
            {"from": "RULE-07", "rel": "PROTECTS", "to": "CryptoWallet"},
            {"from": "RULE-08", "rel": "PROTECTS", "to": "UserProfile"},
        ]
        self._save_database()

    def query_relevant_patterns(
        self,
        issue_description: str,
        file_names: List[str],
    ) -> List[Dict[str, Any]]:
        """Dynamically query memory graph for previous patterns, rules, and fixes relevant to the issue."""
        query_text = f"{issue_description} {' '.join(file_names)}".lower()

        # Extract potential CWE references from query
        cwes_in_query = set(re.findall(r"cwe-\d+", query_text))

        # Extract words (alphanumeric tokens >= 3 chars)
        query_tokens = set(re.findall(r"[a-z0-9_]{3,}", query_text))

        scored_nodes = []
        for nid, node in self.nodes.items():
            score = 0.0
            node_cwe = str(node.get("cwe", "")).lower()
            node_name = str(node.get("name", node.get("title", ""))).lower()
            node_desc = str(node.get("description", node.get("pattern_learned", ""))).lower()

            # 1. Exact CWE match: highest priority
            for cwe in cwes_in_query:
                if cwe in node_cwe:
                    score += 10.0

            # 2. Token overlap with Name
            name_tokens = set(re.findall(r"[a-z0-9_]{3,}", node_name))
            score += len(query_tokens.intersection(name_tokens)) * 2.0

            # 3. Token overlap with Description
            desc_tokens = set(re.findall(r"[a-z0-9_]{3,}", node_desc))
            score += len(query_tokens.intersection(desc_tokens)) * 1.0

            # 4. File overlap
            for fn in file_names:
                if fn.lower() in node_desc or fn.lower() in node_name:
                    score += 3.0

            if score > 0:
                scored_nodes.append((score, node))

        # Sort by relevance score descending
        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        if scored_nodes:
            return [node for _, node in scored_nodes[:4]]

        # Default fallback: return top rules
        return list(self.nodes.values())[:2]

    def record_learning(
        self,
        issue_id: str,
        issue_title: str,
        files_modified: List[str],
        vulnerabilities_fixed: List[str],
        fix_summary: str,
        test_passed: bool,
        human_decision: str,
        pattern_learned: str,
    ) -> Dict[str, Any]:
        """Add new learning node and interconnected edges to the Cognee graph."""
        node_id = f"LEARN-{int(time.time())}"
        node_data = {
            "id": node_id,
            "type": "ClosedLoopLearning",
            "issue_id": issue_id,
            "title": issue_title,
            "files": files_modified,
            "vulnerabilities": vulnerabilities_fixed,
            "fix_summary": fix_summary,
            "test_passed": test_passed,
            "human_decision": human_decision,
            "pattern_learned": pattern_learned,
            "timestamp": time.time(),
        }
        self.nodes[node_id] = node_data

        # Add graph relationships
        for f in files_modified:
            self.edges.append({"from": node_id, "rel": "MODIFIED_FILE", "to": f})
        for v in vulnerabilities_fixed:
            self.edges.append({"from": node_id, "rel": "REMEDIATED_VULN", "to": v})
        self.edges.append({"from": node_id, "rel": "VALIDATED_BY", "to": human_decision})

        self._save_database()
        return node_data

    def get_stats(self) -> Dict[str, Any]:
        """Return graph node and edge counts."""
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "rules_count": sum(1 for n in self.nodes.values() if n.get("type") == "SecurityRule"),
            "learnings_count": sum(1 for n in self.nodes.values() if n.get("type") == "ClosedLoopLearning"),
        }

    def get_all_nodes(self) -> List[Dict[str, Any]]:
        """Return list of all memory nodes."""
        return list(self.nodes.values())
