"""Cognee Engineering Memory & Knowledge Graph Layer.
Provides persistent memory across sessions: records issues, vulnerabilities, fixes, decisions,
and builds an interconnected knowledge graph so future coding tasks learn from past PRs.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import config


class CogneeMemoryGraph:
    """Persistent Graph & Vector Memory store for engineering agents."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.COGNEE_DB_PATH
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
            except Exception:
                pass
        self._seed_default_memory()

    def _save_database(self):
        """Persist graph to JSON store."""
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump({"nodes": self.nodes, "edges": self.edges}, f, indent=2)
        except Exception:
            pass

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

    def query_relevant_patterns(self, issue_description: str, file_names: List[str]) -> List[Dict[str, Any]]:
        """Query memory graph for previous architectural patterns, rules, and fixes relevant to the issue."""
        matched = []
        issue_lower = issue_description.lower()
        files_joined = " ".join(file_names).lower()

        keywords_map = {
            "sql": "RULE-01",
            "injection": "RULE-01",
            "jwt": "RULE-02",
            "token": "RULE-02",
            "auth": "RULE-02",
            "algorithm": "RULE-02",
            "ssrf": "RULE-03",
            "webhook": "RULE-03",
            "url": "RULE-03",
            "command": "RULE-04",
            "ping": "RULE-04",
            "subprocess": "RULE-04",
            "shell": "RULE-04",
            "traversal": "RULE-05",
            "path": "RULE-05",
            "download": "RULE-05",
            "upload": "RULE-05",
            "eval": "RULE-06",
            "pickle": "RULE-06",
            "formula": "RULE-06",
            "analytics": "RULE-06",
            "wallet": "RULE-07",
            "crypto": "RULE-07",
            "secret": "RULE-07",
            "random": "RULE-07",
            "profile": "RULE-08",
            "xss": "RULE-08",
            "assignment": "RULE-08",
        }

        matched_ids = set()
        for kw, rule_id in keywords_map.items():
            if (kw in issue_lower or kw in files_joined) and rule_id in self.nodes:
                matched_ids.add(rule_id)

        # If no specific keyword matched, return top rules
        if not matched_ids:
            for k in list(self.nodes.keys())[:2]:
                matched_ids.add(k)

        for nid in matched_ids:
            matched.append(self.nodes[nid])

        return matched

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
