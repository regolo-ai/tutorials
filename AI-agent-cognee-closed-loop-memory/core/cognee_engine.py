"""Cognee Knowledge Graph & Long-Term Memory Engine for Coding Agents.
Unifies Knowledge Graph extraction, Vector Embeddings (Qwen3-Embedding-8B),
Multi-Session Recall, and Traceable Feedback Loops on Regolo.ai.
"""

import json
import logging
import math
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

import config
from core.regolo_client import RegoloClient

logger = logging.getLogger(__name__)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two dense vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class CogneeMemoryEngine:
    """Enterprise Cognitive Memory Engine for Software Engineering Agents.

    Maintains:
    - Knowledge Graph (Entities: ADRs, Conventions, CI Errors, PRs, Vulnerabilities)
    - Dense Vector Semantic Store (using Regolo Qwen3-Embedding-8B)
    - Traceable Feedback Loop (Session recall logs & outcome tracking)
    """

    def __init__(
        self,
        regolo_client: Optional[RegoloClient] = None,
        graph_file: Optional[Path] = None,
        vector_file: Optional[Path] = None,
        session_log_file: Optional[Path] = None,
        auto_bootstrap: bool = False,
    ):
        self.client = regolo_client or RegoloClient()
        self.graph_file = graph_file or config.COGNEE_GRAPH_FILE
        self.vector_file = vector_file or config.COGNEE_VECTOR_FILE
        self.session_log_file = session_log_file or config.COGNEE_MEMORY_LOG
        self.auto_bootstrap = auto_bootstrap

        self.graph = nx.DiGraph()
        self.nodes_data: Dict[str, Dict[str, Any]] = {}
        self.edges_data: List[Dict[str, Any]] = []
        self.vector_index: List[Dict[str, Any]] = []
        self.session_history: List[Dict[str, Any]] = []

        self._load_storage()

    def _load_storage(self):
        """Load graph, vector store, and session memory logs from disk."""
        # 1. Load Graph
        if self.graph_file.exists():
            try:
                with open(self.graph_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.nodes_data = data.get("nodes", {})
                    self.edges_data = data.get("edges", [])
                    for node_id, node_attrs in self.nodes_data.items():
                        self.graph.add_node(node_id, **node_attrs)
                    for edge in self.edges_data:
                        self.graph.add_edge(edge["source"], edge["target"], **edge)
            except Exception as e:
                logger.warning(f"Error loading graph file: {e}")
                if self.auto_bootstrap:
                    self._bootstrap_sample_repo_memory()
        elif self.auto_bootstrap:
            self._bootstrap_sample_repo_memory()

        # 2. Load Vector Store
        if self.vector_file.exists():
            try:
                with open(self.vector_file, "r", encoding="utf-8") as f:
                    self.vector_index = json.load(f)
            except Exception:
                self.vector_index = []

        # 3. Load Session Logs
        if self.session_log_file.exists():
            try:
                with open(self.session_log_file, "r", encoding="utf-8") as f:
                    self.session_history = json.load(f)
            except Exception:
                self.session_history = []

    def _save_storage(self):
        """Persist graph and vector index to disk."""
        try:
            with open(self.graph_file, "w", encoding="utf-8") as f:
                json.dump({"nodes": self.nodes_data, "edges": self.edges_data}, f, indent=2)

            with open(self.vector_file, "w", encoding="utf-8") as f:
                json.dump(self.vector_index, f, indent=2)

            with open(self.session_log_file, "w", encoding="utf-8") as f:
                json.dump(self.session_history, f, indent=2)
        except Exception as e:
            logger.warning(f"Error persisting memory state: {e}")

    def _bootstrap_sample_repo_memory(self):
        """Bootstrap memory from sample_repo if available."""
        if config.SAMPLE_REPO_DIR.exists():
            self.cognify_codebase(config.SAMPLE_REPO_DIR)

    def cognify_codebase(
        self,
        repo_path: Path,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Scan a repository/directory, parse documentation, ADRs, PRs, and code files,
        and extract semantic graph nodes & relations using real Regolo.ai inference & embeddings.
        """
        if not repo_path.exists():
            return {"error": f"Path '{repo_path}' does not exist."}

        start_time = time.time()
        scanned_files = []
        extracted_nodes = 0
        extracted_edges = 0

        if progress_callback:
            progress_callback(f"Scanning codebase files in {repo_path.name}...")

        # Discover relevant markdown docs, ADRs, history, and python code
        for p in repo_path.rglob("*"):
            if p.is_file() and not any(part.startswith(".") for part in p.parts):
                if p.suffix in [".md", ".py", ".json", ".sql", ".txt", ".yml", ".yaml"]:
                    scanned_files.append(p)

        if progress_callback:
            progress_callback(f"Found {len(scanned_files)} files. Extracting knowledge graph nodes with Regolo...")

        # Process key documentation and code files with real LLM entity extraction
        for idx, fpath in enumerate(scanned_files):
            try:
                rel_path = fpath.relative_to(repo_path)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(3000)

                if len(content.strip()) < 20:
                    continue

                clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", str(rel_path))
                node_id = f"FILE_{clean_name}"
                node_type = "SourceCode" if fpath.suffix == ".py" else ("ArchitecturalDecision" if "ADR" in fpath.name else "Documentation")

                # Extract title and summary using Regolo if doc or ADR
                title = fpath.stem.replace("-", " ").replace("_", " ").title()
                summary = content[:400]

                # If ADR or history file, run LLM entity and relation extraction on Regolo
                if "ADR" in fpath.name or "conventions" in str(fpath).lower() or ".history" in str(fpath).lower():
                    if progress_callback:
                        progress_callback(f"Extracting cognitive entities from {fpath.name} via Regolo...")

                    extract_prompt = (
                        f"Extract structured software engineering entities and relationships from this document as JSON.\n"
                        f"Include entity ID (e.g. ADR-001, CONV-01, CI-FAIL-89, PR-142), type, title, and key constraint.\n\n"
                        f"Document ({fpath.name}):\n{content[:1500]}\n\n"
                        f"JSON schema:\n"
                        f"{{\n"
                        f'  "entities": [{{"id": "...", "type": "ArchitecturalDecision|Convention|PastCIError|SimilarPR|Vulnerability", "title": "...", "content": "..."}}],\n'
                        f'  "relations": [{{"source": "...", "target": "...", "type": "ENFORCES|RESOLVES|PREVENTS|IMPLEMENTS"}}]\n'
                        f"}}"
                    )

                    try:
                        res = self.client.generate(
                            prompt=extract_prompt,
                            stage="extract",
                            max_tokens=1000,
                            temperature=0.1,
                        )
                        raw_json_match = re.search(r"\{[\s\S]*\}", res["content"])
                        if raw_json_match:
                            parsed_data = json.loads(raw_json_match.group(0))
                            for ent in parsed_data.get("entities", []):
                                if "id" in ent and "title" in ent:
                                    self.add_node(
                                        node_id=ent["id"],
                                        node_type=ent.get("type", "Entity"),
                                        title=ent["title"],
                                        content=ent.get("content", summary),
                                        category=fpath.parent.name,
                                    )
                                    extracted_nodes += 1

                            for rel in parsed_data.get("relations", []):
                                if "source" in rel and "target" in rel:
                                    self.add_relation(
                                        source_id=rel["source"],
                                        target_id=rel["target"],
                                        relation_type=rel.get("type", "RELATES_TO"),
                                    )
                                    extracted_edges += 1
                    except Exception as err:
                        logger.warning(f"LLM entity extraction error for {fpath.name}: {err}")

                # Always add the file node itself with real Regolo dense embedding
                self.add_node(
                    node_id=node_id,
                    node_type=node_type,
                    title=f"File: {rel_path}",
                    content=summary,
                    category=fpath.parent.name or "root",
                )
                extracted_nodes += 1

            except Exception as e:
                logger.warning(f"Error indexing {fpath}: {e}")

        # Ensure baseline foundational relational edges for multi-tenant SaaS
        self._ensure_domain_relations()

        self._save_storage()
        elapsed = round(time.time() - start_time, 2)

        return {
            "scanned_files": len(scanned_files),
            "indexed_nodes": len(self.nodes_data),
            "indexed_edges": len(self.edges_data),
            "new_nodes_added": extracted_nodes,
            "new_edges_added": extracted_edges,
            "elapsed_seconds": elapsed,
            "status": "SUCCESS",
        }

    def _ensure_domain_relations(self):
        """Ensure relational edges between ADRs, conventions, and past CI errors exist in the graph."""
        domain_edges = [
            ("CI-FAIL-89", "VULN-CWE-89", "TRIGGERED_BY"),
            ("PR-142", "CI-FAIL-89", "FIXES_CI_FAILURE"),
            ("PR-142", "VULN-CWE-89", "MITIGATES_VULNERABILITY"),
            ("PR-142", "ADR-003", "IMPLEMENTS_DECISION"),
            ("ADR-001", "CONV-01", "ENFORCES_CONVENTION"),
            ("ADR-003", "VULN-CWE-89", "PREVENTS_CATEGORY"),
            ("RUNBOOK-01", "PR-142", "REFERENCES_PRECEDENT"),
        ]
        for src, tgt, rel in domain_edges:
            if src in self.nodes_data and tgt in self.nodes_data:
                self.add_relation(src, tgt, rel)

    def add_node(
        self,
        node_id: str,
        node_type: str,
        title: str,
        content: str,
        category: str = "Custom",
    ) -> Dict[str, Any]:
        """Add or update an entity node in the knowledge graph with real Qwen3-Embedding-8B."""
        # Compute real vector embedding via Regolo.ai
        embedding_text = f"{title}. {content}"
        try:
            vector = self.client.get_embedding(embedding_text)
        except Exception as e:
            logger.warning(f"Embedding generation error for {node_id}: {e}")
            vector = [0.0] * 4096

        payload = {
            "id": node_id,
            "type": node_type,
            "title": title,
            "content": content,
            "category": category,
            "created_at": time.time(),
        }
        self.nodes_data[node_id] = payload
        self.graph.add_node(node_id, **payload)

        # Update vector store
        # Remove previous embedding if present
        self.vector_index = [v for v in self.vector_index if v.get("id") != node_id]
        self.vector_index.append({
            "id": node_id,
            "title": title,
            "content": content,
            "type": node_type,
            "vector": vector,
        })

        self._save_storage()
        return payload

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight: float = 1.0,
    ) -> bool:
        """Create a typed edge between two memory nodes."""
        edge = {
            "source": source_id,
            "target": target_id,
            "type": relation_type,
            "weight": weight,
        }
        # Check if edge already exists
        for existing in self.edges_data:
            if existing["source"] == source_id and existing["target"] == target_id and existing["type"] == relation_type:
                return True

        self.edges_data.append(edge)
        self.graph.add_edge(source_id, target_id, **edge)
        self._save_storage()
        return True

    def update_node(
        self,
        node_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        node_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update the content, title, or metadata of an existing node and recalculate embeddings."""
        if node_id not in self.nodes_data:
            return None

        node = self.nodes_data[node_id]
        if title is not None:
            node["title"] = title
        if content is not None:
            node["content"] = content
        if category is not None:
            node["category"] = category
        if node_type is not None:
            node["type"] = node_type
        node["updated_at"] = time.time()

        # Update in NetworkX graph
        if node_id in self.graph:
            self.graph.nodes[node_id].update(node)

        # Update vector embedding if title or content changed
        if title is not None or content is not None:
            embedding_text = f"{node['title']}. {node['content']}"
            try:
                vector = self.client.get_embedding(embedding_text)
            except Exception as e:
                logger.warning(f"Embedding update error for {node_id}: {e}")
                vector = [0.0] * 4096

            for item in self.vector_index:
                if item.get("id") == node_id:
                    item["title"] = node["title"]
                    item["content"] = node["content"]
                    item["type"] = node.get("type", item.get("type"))
                    item["vector"] = vector
                    break

        self._save_storage()
        return node

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its connected edges from memory graph and vector store."""
        if node_id not in self.nodes_data:
            return False

        # Remove from nodes_data
        del self.nodes_data[node_id]

        # Remove from graph
        if node_id in self.graph:
            self.graph.remove_node(node_id)

        # Remove from edges_data
        self.edges_data = [
            e for e in self.edges_data
            if e.get("source") != node_id and e.get("target") != node_id
        ]

        # Remove from vector index
        self.vector_index = [
            v for v in self.vector_index
            if v.get("id") != node_id
        ]

        self._save_storage()
        return True

    def recall_memory(
        self,
        query: str,
        max_hops: int = 2,
        max_results: int = 6,
    ) -> Dict[str, Any]:
        """Perform Cognitive Long-Term Recall:
        Combines real Qwen3-Embedding-8B cosine similarity + Knowledge Graph Hop Traversal.
        """
        start_time = time.time()

        # Step 1: Real Dense Semantic Search with Regolo Embeddings
        query_vector = self.client.get_embedding(query)
        scored_nodes: List[Tuple[str, float]] = []

        for item in self.vector_index:
            node_id = item.get("id")
            node_vec = item.get("vector")
            if node_id and node_vec and len(node_vec) == len(query_vector):
                sim = cosine_similarity(query_vector, node_vec)
                scored_nodes.append((node_id, sim))

        scored_nodes.sort(key=lambda x: x[1], reverse=True)
        primary_node_ids = [n[0] for n in scored_nodes[:3]]

        # Step 2: Multi-Hop Graph Traversal (Connect causal relations)
        retrieved_node_ids: Set[str] = set(primary_node_ids)
        relational_paths: List[Dict[str, Any]] = []

        for p_id in primary_node_ids:
            if p_id in self.graph:
                # Successors
                for succ in self.graph.successors(p_id):
                    retrieved_node_ids.add(succ)
                    edge_data = self.graph.get_edge_data(p_id, succ) or {}
                    relational_paths.append({
                        "from": p_id,
                        "to": succ,
                        "relation": edge_data.get("type", "RELATES_TO"),
                    })

                # Predecessors
                for pred in self.graph.predecessors(p_id):
                    retrieved_node_ids.add(pred)
                    edge_data = self.graph.get_edge_data(pred, p_id) or {}
                    relational_paths.append({
                        "from": pred,
                        "to": p_id,
                        "relation": edge_data.get("type", "RELATES_TO"),
                    })

        # Ensure fallback to top scored if graph is small
        if not retrieved_node_ids and self.nodes_data:
            retrieved_node_ids = set(list(self.nodes_data.keys())[:3])

        final_nodes = [self.nodes_data[nid] for nid in retrieved_node_ids if nid in self.nodes_data][:max_results]

        # Step 3: Format Structured Causal Memory Context for Agent
        causal_summary_lines = []
        causal_summary_lines.append("### 🧠 Cognee Cognitive Memory Recall (Regolo.ai EU)")
        causal_summary_lines.append(f"Query: '{query}'")
        causal_summary_lines.append(f"Linked Graph Entities ({len(final_nodes)} nodes, {len(relational_paths)} relational edges):\n")

        for n in final_nodes:
            causal_summary_lines.append(f"- **[{n.get('id')}] {n.get('title')}** ({n.get('type')})")
            causal_summary_lines.append(f"  *Key Insight:* {n.get('content')}")

        if relational_paths:
            causal_summary_lines.append("\n**Causal Graph Links:**")
            for rp in relational_paths[:6]:
                causal_summary_lines.append(f"  • `{rp['from']}` ──[{rp['relation']}]──▶ `{rp['to']}`")

        memory_prompt_block = "\n".join(causal_summary_lines)
        latency = round(time.time() - start_time, 3)

        # Log session event for traceability
        session_entry = {
            "timestamp": time.time(),
            "query": query,
            "retrieved_nodes": [n["id"] for n in final_nodes],
            "graph_paths": len(relational_paths),
            "latency_seconds": latency,
        }
        self.session_history.append(session_entry)
        self._save_storage()

        return {
            "query": query,
            "nodes": final_nodes,
            "relations": relational_paths,
            "memory_prompt_block": memory_prompt_block,
            "latency_seconds": latency,
            "total_nodes_in_graph": len(self.nodes_data),
            "total_edges_in_graph": len(self.edges_data),
        }

    def get_graph_summary(self) -> Dict[str, Any]:
        """Return topological summary of the knowledge graph."""
        type_counts = {}
        for n in self.nodes_data.values():
            t = n.get("type", "Unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        relation_counts = {}
        for e in self.edges_data:
            r = e.get("type", "RELATES_TO")
            relation_counts[r] = relation_counts.get(r, 0) + 1

        return {
            "total_nodes": len(self.nodes_data),
            "total_edges": len(self.edges_data),
            "entity_breakdown": type_counts,
            "relation_breakdown": relation_counts,
            "session_recall_events": len(self.session_history),
        }

    def get_web_ui_url(self) -> Dict[str, str]:
        """Return official URLs for the self-hosted Cognee Web UI & OpenAPI Swagger documentation."""
        from core.docker_manager import ACTIVE_PORTS
        port = ACTIVE_PORTS.get("cognee", config.COGNEE_API_PORT)
        host = config.COGNEE_API_HOST
        base_url = f"http://{host}:{port}"
        return {
            "web_ui_url": base_url,
            "swagger_docs_url": f"{base_url}/docs",
            "openapi_json_url": f"{base_url}/openapi.json",
            "health_endpoint": f"{base_url}/health",
        }

    def get_formatted_edge_list(self) -> List[Dict[str, Any]]:
        """Return structured list of all knowledge graph connections with ASCII visual representation."""
        formatted = []
        for e in self.edges_data:
            src = e.get("source", "")
            tgt = e.get("target", "")
            rel = e.get("type", "RELATES_TO")
            src_node = self.nodes_data.get(src, {})
            tgt_node = self.nodes_data.get(tgt, {})
            diagram = f"[{src}] ───({rel})───▶ [{tgt}]"
            formatted.append({
                "source": src,
                "source_title": src_node.get("title", src),
                "source_type": src_node.get("type", "Unknown"),
                "relation": rel,
                "target": tgt,
                "target_title": tgt_node.get("title", tgt),
                "target_type": tgt_node.get("type", "Unknown"),
                "diagram": diagram,
            })
        return formatted

    def get_node_neighbors(self, node_id: str) -> Dict[str, Any]:
        """Inspect inbound and outbound connections for a specific graph node."""
        if node_id not in self.nodes_data:
            return {"error": f"Node '{node_id}' not found in graph."}

        outbound = []
        if node_id in self.graph:
            for succ in self.graph.successors(node_id):
                edata = self.graph.get_edge_data(node_id, succ) or {}
                succ_node = self.nodes_data.get(succ, {})
                outbound.append({
                    "target_id": succ,
                    "target_title": succ_node.get("title", succ),
                    "relation": edata.get("type", "RELATES_TO"),
                })

        inbound = []
        if node_id in self.graph:
            for pred in self.graph.predecessors(node_id):
                edata = self.graph.get_edge_data(pred, node_id) or {}
                pred_node = self.nodes_data.get(pred, {})
                inbound.append({
                    "source_id": pred,
                    "source_title": pred_node.get("title", pred),
                    "relation": edata.get("type", "RELATES_TO"),
                })

        return {
            "node": self.nodes_data[node_id],
            "inbound": inbound,
            "outbound": outbound,
        }

    def generate_visual_html_graph(self, output_path: Optional[Path] = None) -> Path:
        """Generate an interactive HTML/JavaScript Knowledge Graph visualizer with a modern light theme.
        Features node CRUD (edit/delete/add), interactive exploration & navigation bottom toolbar,
        cluster and hub focusing, subgraph isolation, dynamic filtering, live node inspection,
        and light/dark mode toggling.
        """
        target_path = output_path or (config.DATA_DIR / "knowledge_graph_visualizer.html")
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Color mapping for modern light theme with high-contrast text and soft pastel backgrounds
        color_map = {
            "ArchitecturalDecision": {"bg": "#ECFDF5", "border": "#10B981", "text": "#065F46", "badge": "#D1FAE5"},
            "PastCIError": {"bg": "#FFF1F2", "border": "#F43F5E", "text": "#9F1239", "badge": "#FFE4E6"},
            "SimilarPR": {"bg": "#F0F9FF", "border": "#38BDF8", "text": "#0369A1", "badge": "#E0F2FE"},
            "RepositoryConvention": {"bg": "#FFFBEB", "border": "#F59E0B", "text": "#92400E", "badge": "#FEF3C7"},
            "ResolvedVulnerability": {"bg": "#FAF5FF", "border": "#A855F7", "text": "#6B21A8", "badge": "#F3E8FF"},
            "TeamPreference": {"bg": "#FFF7ED", "border": "#FB923C", "text": "#9A3412", "badge": "#FFEDD5"},
            "Runbook": {"bg": "#F0FDF4", "border": "#0EA5E9", "text": "#0284C7", "badge": "#E0F2FE"},
            "SourceCode": {"bg": "#F8FAFC", "border": "#818CF8", "text": "#3730A3", "badge": "#EEF2FF"},
            "Documentation": {"bg": "#F8FAFC", "border": "#94A3B8", "text": "#1E293B", "badge": "#F1F5F9"},
            "SessionOutcome": {"bg": "#F0FDF4", "border": "#22C55E", "text": "#15803D", "badge": "#DCFCE7"},
        }

        vis_nodes = []
        for node_id, node in self.nodes_data.items():
            ntype = node.get("type", "Custom")
            palette = color_map.get(ntype, {"bg": "#F8FAFC", "border": "#94A3B8", "text": "#334155", "badge": "#E2E8F0"})
            
            title_text = node.get("title", node_id)
            clean_title = title_text[:28] + ("..." if len(title_text) > 28 else "")

            node_label = f"{node_id}\n{clean_title}"

            vis_nodes.append({
                "id": node_id,
                "label": node_label,
                "group": ntype,
                "shape": "box",
                "margin": {"top": 10, "bottom": 10, "left": 14, "right": 14},
                "color": {
                    "background": palette["bg"],
                    "border": palette["border"],
                    "highlight": {"background": "#FFFFFF", "border": palette["border"]},
                    "hover": {"background": "#FFFFFF", "border": palette["border"]},
                },
                "font": {
                    "color": palette["text"],
                    "size": 12,
                    "face": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                    "bold": "600",
                },
                "borderWidth": 2,
                "shadow": {
                    "enabled": True,
                    "color": "rgba(15, 23, 42, 0.08)",
                    "size": 10,
                    "x": 0,
                    "y": 4,
                },
                "raw_data": node,
            })

        vis_edges = []
        for idx, e in enumerate(self.edges_data):
            rel = e.get("type", "RELATES_TO")
            vis_edges.append({
                "id": f"e_{idx}",
                "from": e["source"],
                "to": e["target"],
                "label": rel,
                "arrows": {"to": {"enabled": True, "scaleFactor": 0.75}},
                "font": {
                    "color": "#64748B",
                    "size": 10,
                    "face": "Inter, sans-serif",
                    "align": "middle",
                    "background": "#FFFFFF",
                    "strokeWidth": 0,
                },
                "color": {
                    "color": "#CBD5E1",
                    "highlight": "#10B981",
                    "hover": "#0EA5E9",
                },
                "smooth": {"type": "cubicBezier", "roundness": 0.25},
                "width": 1.75,
            })

        nodes_json = json.dumps(vis_nodes)
        edges_json = json.dumps(vis_edges)
        summary = self.get_graph_summary()
        current_time_str = time.strftime("%Y-%m-%d %H:%M:%S")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Regolo.ai + Cognee • Long-Term Memory Knowledge Graph</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        :root {{
            --bg-canvas: #F8FAFC;
            --bg-card: #FFFFFF;
            --bg-subtle: #F1F5F9;
            --border: #E2E8F0;
            --border-hover: #CBD5E1;
            --text-main: #0F172A;
            --text-muted: #64748B;
            --text-subtle: #94A3B8;
            --primary: #10B981;
            --primary-light: #ECFDF5;
            --primary-dark: #047857;
            --accent: #0284C7;
            --danger: #F43F5E;
            --danger-light: #FFF1F2;
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -1px rgba(0, 0, 0, 0.04);
            --shadow-lg: 0 10px 25px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
        }}

        [data-theme="dark"] {{
            --bg-canvas: #090D0B;
            --bg-card: #111A15;
            --bg-subtle: #18241D;
            --border: #1E2D24;
            --border-hover: #2E4537;
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
            --text-subtle: #64748B;
            --primary: #00FF66;
            --primary-light: rgba(0, 255, 102, 0.12);
            --primary-dark: #00CC52;
            --accent: #00E5FF;
            --danger: #FF4D4D;
            --danger-light: rgba(255, 77, 77, 0.15);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, sans-serif; }}
        body {{ background-color: var(--bg-canvas); color: var(--text-main); overflow: hidden; height: 100vh; display: flex; flex-direction: column; transition: background-color 0.2s ease, color 0.2s ease; }}
        
        /* Modern Header */
        header {{
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            z-index: 20;
            box-shadow: var(--shadow-sm);
        }}
        .brand-section {{ display: flex; align-items: center; gap: 14px; }}
        .logo-badge {{
            background: linear-gradient(135deg, #10B981 0%, #059669 100%);
            color: #FFFFFF;
            font-weight: 800;
            font-size: 13px;
            padding: 6px 12px;
            border-radius: 8px;
            letter-spacing: 0.5px;
            box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
        }}
        .brand-title {{ font-size: 15px; font-weight: 700; color: var(--text-main); letter-spacing: -0.3px; }}
        .brand-subtitle {{ font-size: 11px; color: var(--text-muted); font-weight: 400; }}
        
        .live-status-pill {{
            display: flex;
            align-items: center;
            gap: 6px;
            background: var(--primary-light);
            color: var(--primary-dark);
            border: 1px solid rgba(16, 185, 129, 0.2);
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
        }}
        .status-dot {{ width: 7px; height: 7px; background: #10B981; border-radius: 50%; box-shadow: 0 0 8px #10B981; }}

        .header-actions {{ display: flex; align-items: center; gap: 12px; }}
        .stats-badge {{ font-size: 12px; color: var(--text-muted); background: var(--bg-subtle); border: 1px solid var(--border); padding: 4px 10px; border-radius: 6px; }}
        .stats-badge strong {{ color: var(--text-main); font-weight: 700; }}

        .btn-action {{
            background: var(--bg-subtle);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s;
        }}
        .btn-action:hover {{ background: var(--border); }}
        .btn-primary {{
            background: var(--primary);
            color: #FFFFFF;
            border: 1px solid var(--primary-dark);
        }}
        .btn-primary:hover {{ background: var(--primary-dark); }}

        /* Main Workspace */
        .main-container {{ display: flex; flex: 1; height: calc(100vh - 65px); position: relative; }}
        #network-canvas {{
            flex: 1;
            height: 100%;
            background-color: var(--bg-canvas);
            background-image: radial-gradient(var(--border) 1px, transparent 1px);
            background-size: 24px 24px;
        }}
        
        /* Modern Side Inspector */
        .sidebar {{
            width: 420px;
            background: var(--bg-card);
            border-left: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            padding: 20px;
            overflow-y: auto;
            box-shadow: var(--shadow-lg);
            z-index: 10;
            transition: background-color 0.2s;
        }}
        .sidebar-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }}
        .sidebar-header h2 {{ font-size: 15px; font-weight: 700; color: var(--text-main); }}

        .search-container {{ position: relative; margin-bottom: 14px; }}
        .search-input {{
            width: 100%;
            background: var(--bg-subtle);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 9px 12px 9px 34px;
            border-radius: 8px;
            font-size: 13px;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        .search-input:focus {{ border-color: var(--primary); box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15); }}
        .search-icon {{ position: absolute; left: 11px; top: 9px; font-size: 14px; color: var(--text-muted); }}

        .filter-chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }}
        .chip {{
            font-size: 11px;
            font-weight: 600;
            padding: 4px 9px;
            border-radius: 6px;
            cursor: pointer;
            border: 1px solid var(--border);
            background: var(--bg-subtle);
            color: var(--text-muted);
            transition: all 0.15s;
        }}
        .chip:hover, .chip.active {{ border-color: var(--primary); color: var(--primary-dark); background: var(--primary-light); }}

        /* Node Details Card */
        .node-card {{
            background: var(--bg-subtle);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 14px;
            box-shadow: var(--shadow-sm);
        }}
        .badge-type {{
            display: inline-block;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        .node-title {{ font-size: 15px; font-weight: 700; color: var(--text-main); margin-bottom: 8px; line-height: 1.4; }}
        .node-desc {{ font-size: 13px; color: var(--text-muted); line-height: 1.6; white-space: pre-wrap; font-family: 'Inter', sans-serif; }}
        
        .node-manage-bar {{
            display: flex;
            gap: 8px;
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
        }}
        .btn-node-edit {{
            flex: 1;
            background: #F0F9FF;
            border: 1px solid #BAE6FD;
            color: #0369A1;
            padding: 7px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            transition: all 0.15s;
        }}
        .btn-node-edit:hover {{ border-color: #0284C7; background: #E0F2FE; }}
        .btn-node-delete {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: var(--danger);
            padding: 7px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            transition: all 0.15s;
        }}
        .btn-node-delete:hover {{ border-color: var(--danger); background: var(--danger-light); }}

        .section-label {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin: 16px 0 8px 0; }}
        
        .relation-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 12px;
            padding: 8px 12px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            margin-bottom: 6px;
            cursor: pointer;
            transition: border-color 0.15s, background-color 0.15s;
        }}
        .relation-item:hover {{ border-color: var(--primary); background: var(--bg-subtle); }}
        .rel-label {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600; color: var(--primary); background: var(--primary-light); padding: 2px 6px; border-radius: 4px; }}

        /* Network Exploration & Navigation Bottom Bar */
        .nav-exploration-bar {{
            position: absolute;
            bottom: 20px;
            left: 24px;
            right: 444px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 10px;
            background: var(--bg-card);
            padding: 8px 14px;
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-lg);
            z-index: 10;
        }}
        .nav-group {{ display: flex; align-items: center; gap: 6px; }}
        .nav-divider {{ width: 1px; height: 22px; background: var(--border); margin: 0 4px; }}
        .nav-btn {{
            background: var(--bg-subtle);
            color: var(--text-main);
            border: 1px solid var(--border);
            padding: 6px 11px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: all 0.15s;
        }}
        .nav-btn:hover {{ background: var(--border); color: var(--primary-dark); }}
        .nav-btn.active {{ background: var(--primary-light); color: var(--primary-dark); border-color: var(--primary); }}
        .nav-select {{
            background: var(--bg-subtle);
            color: var(--text-main);
            border: 1px solid var(--border);
            padding: 6px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            outline: none;
            cursor: pointer;
        }}
        .nav-indicator {{ font-size: 11px; font-weight: 700; color: var(--text-muted); padding: 0 4px; }}

        /* Legend Card */
        .legend-card {{
            position: absolute;
            top: 20px;
            left: 24px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 12px 16px;
            border-radius: 10px;
            font-size: 11px;
            box-shadow: var(--shadow-md);
            z-index: 10;
            max-width: 260px;
        }}
        .legend-title {{ font-weight: 700; font-size: 11px; margin-bottom: 8px; color: var(--text-main); text-transform: uppercase; letter-spacing: 0.5px; }}
        .legend-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 5px; font-size: 11px; color: var(--text-muted); }}
        .legend-indicator {{ width: 9px; height: 9px; border-radius: 3px; }}

        /* Modal for Editing/Adding Node */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(15, 23, 42, 0.45);
            backdrop-filter: blur(4px);
            z-index: 100;
            display: none;
            align-items: center;
            justify-content: center;
        }}
        .modal-box {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            width: 520px;
            max-width: 90vw;
            padding: 24px;
            box-shadow: var(--shadow-lg);
        }}
        .modal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }}
        .modal-header h3 {{ font-size: 16px; font-weight: 700; color: var(--text-main); }}
        .modal-close {{ background: transparent; border: none; font-size: 18px; color: var(--text-muted); cursor: pointer; }}
        .form-group {{ margin-bottom: 14px; }}
        .form-label {{ display: block; font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }}
        .form-input, .form-textarea, .form-select {{
            width: 100%;
            background: var(--bg-subtle);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 9px 12px;
            border-radius: 6px;
            font-size: 13px;
            outline: none;
        }}
        .form-textarea {{ height: 110px; resize: vertical; }}
        .modal-footer {{ display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }}
    </style>
</head>
<body data-theme="light">
    <!-- Header -->
    <header>
        <div class="brand-section">
            <div class="logo-badge">COGNEE</div>
            <div>
                <div class="brand-title">Long-Term Memory Knowledge Graph</div>
                <div class="brand-subtitle">Regolo.ai Sovereign EU Inference • Causal Relational Memory</div>
            </div>
            <div class="live-status-pill">
                <div class="status-dot"></div>
                LIVE MEMORY STATE
            </div>
        </div>

        <div class="header-actions">
            <div class="stats-badge">Nodes: <strong id="statNodes">{summary['total_nodes']}</strong></div>
            <div class="stats-badge">Edges: <strong id="statEdges">{summary['total_edges']}</strong></div>
            <button class="btn-action" onclick="openAddNodeModal()">➕ Add Node</button>
            <button class="btn-action" onclick="exportGraphData()">💾 Export JSON</button>
            <button class="btn-action" onclick="toggleTheme()" id="themeBtn">🌙 Dark Mode</button>
        </div>
    </header>

    <div class="main-container">
        <!-- Legend Overlay -->
        <div class="legend-card">
            <div class="legend-title">Entity Categories</div>
            <div class="legend-row"><div class="legend-indicator" style="background:#10B981;"></div> Architectural Decisions (ADR)</div>
            <div class="legend-row"><div class="legend-indicator" style="background:#F43F5E;"></div> Past CI Errors</div>
            <div class="legend-row"><div class="legend-indicator" style="background:#38BDF8;"></div> Similar PRs & Resolutions</div>
            <div class="legend-row"><div class="legend-indicator" style="background:#F59E0B;"></div> Repository Conventions</div>
            <div class="legend-row"><div class="legend-indicator" style="background:#A855F7;"></div> Resolved Vulnerabilities</div>
            <div class="legend-row"><div class="legend-indicator" style="background:#818CF8;"></div> Source Code & Docs</div>
        </div>

        <!-- Canvas -->
        <div id="network-canvas"></div>

        <!-- Network Exploration & Navigation Bottom Bar -->
        <div class="nav-exploration-bar">
            <!-- Viewport & Step Navigation -->
            <div class="nav-group">
                <button class="nav-btn" onclick="fitNetwork()" title="Reset view and center the entire graph">🎯 Center Graph</button>
                <div class="nav-divider"></div>
                <button class="nav-btn" onclick="stepNode(-1)" title="Previous node">◀ Prev</button>
                <span class="nav-indicator" id="navStepIndicator">1 / {len(vis_nodes)}</span>
                <button class="nav-btn" onclick="stepNode(1)" title="Next node">Next ▶</button>
            </div>

            <!-- Hub & Cluster Exploration -->
            <div class="nav-group">
                <div class="nav-divider"></div>
                <select class="nav-select" id="hubSelector" onchange="if(this.value) focusNode(this.value)">
                    <option value="">🌟 Key Hub Nodes...</option>
                    <option value="ADR-001">📜 ADR-001 (Tenant Context)</option>
                    <option value="ADR-003">🛡️ ADR-003 (Parameterized SQL)</option>
                    <option value="CI-FAIL-89">🚨 CI Failure #89 (SQL Injection)</option>
                    <option value="PR-142">🔧 PR-142 (Security Hotfix)</option>
                    <option value="VULN-CWE-89">⚠️ CWE-89 (SQL Injection)</option>
                </select>

                <select class="nav-select" id="clusterSelector" onchange="jumpToCluster(this.value)">
                    <option value="">🗂️ Jump to Cluster...</option>
                    <option value="ArchitecturalDecision">ADRs (Decisions)</option>
                    <option value="PastCIError">Historical CI Errors</option>
                    <option value="SimilarPR">Previous Pull Requests</option>
                    <option value="RepositoryConvention">Repository Conventions</option>
                    <option value="ResolvedVulnerability">Resolved Vulnerabilities</option>
                    <option value="SourceCode">Code & Documentation</option>
                </select>

                <button class="nav-btn" id="isolateBtn" onclick="toggleIsolateNeighborhood()" title="Isolate connected neighbors for selected node">🔍 Isolate Neighbors</button>
            </div>

            <!-- Zoom controls -->
            <div class="nav-group">
                <div class="nav-divider"></div>
                <button class="nav-btn" onclick="zoomNetwork(1.25)" title="Zoom In">➕</button>
                <button class="nav-btn" onclick="zoomNetwork(0.8)" title="Zoom Out">➖</button>
            </div>
        </div>

        <!-- Node Inspector Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <h2>Node Inspector & Memory Manager</h2>
                <span style="font-size: 11px; color: var(--text-subtle);">Live Graph State</span>
            </div>

            <div class="search-container">
                <span class="search-icon">🔍</span>
                <input type="text" class="search-input" id="nodeSearch" placeholder="Search memory nodes, ADRs, CVEs..." oninput="searchNodes(this.value)">
            </div>

            <div class="filter-chips">
                <div class="chip active" onclick="filterType('ALL', this)">All</div>
                <div class="chip" onclick="filterType('ArchitecturalDecision', this)">ADRs</div>
                <div class="chip" onclick="filterType('PastCIError', this)">CI Errors</div>
                <div class="chip" onclick="filterType('SimilarPR', this)">PRs</div>
                <div class="chip" onclick="filterType('RepositoryConvention', this)">Conventions</div>
                <div class="chip" onclick="filterType('ResolvedVulnerability', this)">CVEs</div>
            </div>

            <div id="nodeDetails">
                <div class="node-card">
                    <span class="badge-type" style="background: #E2E8F0; color: #475569;">Interactive Explorer</span>
                    <div class="node-title">Explore & Manage Knowledge Graph</div>
                    <div class="node-desc">Click any node on the canvas to inspect policy specifications, edit knowledge content, or delete node entities. Use the bottom navigation bar to explore clusters and causal relationships.</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal for Edit / Add Node -->
    <div class="modal-overlay" id="nodeModal">
        <div class="modal-box">
            <div class="modal-header">
                <h3 id="modalTitle">Edit Node Knowledge</h3>
                <button class="modal-close" onclick="closeNodeModal()">✕</button>
            </div>
            <div class="form-group">
                <label class="form-label">Node ID</label>
                <input type="text" class="form-input" id="modalNodeId" placeholder="e.g. ADR-004">
            </div>
            <div class="form-group">
                <label class="form-label">Category / Entity Type</label>
                <select class="form-select" id="modalNodeType">
                    <option value="ArchitecturalDecision">ArchitecturalDecision (ADR)</option>
                    <option value="PastCIError">PastCIError (CI Error)</option>
                    <option value="SimilarPR">SimilarPR (Pull Request)</option>
                    <option value="RepositoryConvention">RepositoryConvention (Convention)</option>
                    <option value="ResolvedVulnerability">ResolvedVulnerability (Vulnerability)</option>
                    <option value="TeamPreference">TeamPreference (Team Preference)</option>
                    <option value="SourceCode">SourceCode (Code)</option>
                    <option value="Documentation">Documentation (Documentation)</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Title</label>
                <input type="text" class="form-input" id="modalNodeTitle" placeholder="Descriptive title...">
            </div>
            <div class="form-group">
                <label class="form-label">Content / Knowledge Specifications</label>
                <textarea class="form-textarea" id="modalNodeContent" placeholder="Detailed policy description, constraints, or code specifications..."></textarea>
            </div>
            <div class="modal-footer">
                <button class="btn-action" onclick="closeNodeModal()">Cancel</button>
                <button class="btn-action btn-primary" onclick="saveNodeModal()">Save Knowledge</button>
            </div>
        </div>
    </div>

    <script type="text/javascript">
        let rawNodes = {nodes_json};
        let rawEdges = {edges_json};
        let currentNodeIndex = 0;
        let selectedNodeId = null;
        let isIsolatedNeighborhood = false;

        const colorMap = {{
            "ArchitecturalDecision": {{"bg": "#ECFDF5", "border": "#10B981", "text": "#065F46", "badge": "#D1FAE5"}},
            "PastCIError": {{"bg": "#FFF1F2", "border": "#F43F5E", "text": "#9F1239", "badge": "#FFE4E6"}},
            "SimilarPR": {{"bg": "#F0F9FF", "border": "#38BDF8", "text": "#0369A1", "badge": "#E0F2FE"}},
            "RepositoryConvention": {{"bg": "#FFFBEB", "border": "#F59E0B", "text": "#92400E", "badge": "#FEF3C7"}},
            "ResolvedVulnerability": {{"bg": "#FAF5FF", "border": "#A855F7", "text": "#6B21A8", "badge": "#F3E8FF"}},
            "TeamPreference": {{"bg": "#FFF7ED", "border": "#FB923C", "text": "#9A3412", "badge": "#FFEDD5"}},
            "Runbook": {{"bg": "#F0FDF4", "border": "#0EA5E9", "text": "#0284C7", "badge": "#E0F2FE"}},
            "SourceCode": {{"bg": "#F8FAFC", "border": "#818CF8", "text": "#3730A3", "badge": "#EEF2FF"}},
            "Documentation": {{"bg": "#F8FAFC", "border": "#94A3B8", "text": "#1E293B", "badge": "#F1F5F9"}},
            "SessionOutcome": {{"bg": "#F0FDF4", "border": "#22C55E", "text": "#15803D", "badge": "#DCFCE7"}}
        }};

        const container = document.getElementById('network-canvas');
        const nodesDataSet = new vis.DataSet(rawNodes);
        const edgesDataSet = new vis.DataSet(rawEdges);
        const data = {{ nodes: nodesDataSet, edges: edgesDataSet }};

        const options = {{
            nodes: {{
                shape: 'box',
                borderWidth: 2,
                shadow: true,
                chosen: {{
                    node: function(values, id, selected, hovering) {{
                        values.borderWidth = 3;
                        values.shadowSize = 14;
                    }}
                }}
            }},
            edges: {{
                width: 1.75,
                arrows: {{ to: {{ enabled: true, scaleFactor: 0.75 }} }},
                font: {{ color: '#475569', size: 10, align: 'middle', background: '#FFFFFF', strokeWidth: 2, strokeColor: '#FFFFFF' }},
                color: {{ color: '#CBD5E1', highlight: '#10B981', hover: '#0EA5E9' }}
            }},
            physics: {{
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {{
                    gravitationalConstant: -45,
                    centralGravity: 0.01,
                    springLength: 100,
                    springConstant: 0.08,
                    damping: 0.4
                }},
                maxVelocity: 50,
                minVelocity: 0.1,
                stabilization: {{ iterations: 160 }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 200,
                navigationButtons: false,
                keyboard: true
            }}
        }};

        const network = new vis.Network(container, data, options);

        // Stabilize physics automatically so nodes stay locked in place
        network.once("stabilizationIterationsDone", function () {{
            network.setOptions({{ physics: {{ enabled: false }} }});
        }});

        network.on("click", function (params) {{
            if (params.nodes.length > 0) {{
                const nId = params.nodes[0];
                selectAndDisplayNode(nId);
            }} else {{
                if (isIsolatedNeighborhood) {{
                    resetIsolation();
                }}
            }}
        }});

        function updateStats() {{
            document.getElementById('statNodes').innerText = nodesDataSet.length;
            document.getElementById('statEdges').innerText = edgesDataSet.length;
            updateStepIndicator();
        }}

        function updateStepIndicator() {{
            const visibleNodes = rawNodes.filter(n => !n.hidden);
            const total = visibleNodes.length;
            const current = total > 0 ? (currentNodeIndex % total) + 1 : 0;
            document.getElementById('navStepIndicator').innerText = `${{current}} / ${{total}}`;
        }}

        function selectAndDisplayNode(nodeId) {{
            selectedNodeId = nodeId;
            const idx = rawNodes.findIndex(n => n.id === nodeId);
            if (idx !== -1) currentNodeIndex = idx;
            updateStepIndicator();
            displayNodeDetails(nodeId);
        }}

        function displayNodeDetails(nodeId) {{
            const node = rawNodes.find(n => n.id === nodeId);
            if (!node) return;

            const nData = node.raw_data || {{}};
            const inbound = rawEdges.filter(e => e.to === nodeId);
            const outbound = rawEdges.filter(e => e.from === nodeId);

            const badgeBg = node.color.background;
            const badgeColor = node.color.border;

            let inHtml = inbound.map(e => `
                <div class="relation-item" onclick="focusNode('${{e.from}}')">
                    <span><b>${{e.from}}</b></span>
                    <span class="rel-label">◀ ${{e.label}}</span>
                </div>
            `).join('') || '<div style="color:var(--text-subtle); font-size:12px; padding: 4px 0;">(No inbound relations)</div>';

            let outHtml = outbound.map(e => `
                <div class="relation-item" onclick="focusNode('${{e.to}}')">
                    <span><b>${{e.to}}</b></span>
                    <span class="rel-label">${{e.label}} ▶</span>
                </div>
            `).join('') || '<div style="color:var(--text-subtle); font-size:12px; padding: 4px 0;">(No outbound dependencies)</div>';

            const html = `
                <div class="node-card">
                    <span class="badge-type" style="background: ${{badgeBg}}; color: ${{badgeColor}};">${{nData.type || 'Entity'}}</span>
                    <div class="node-title">${{nodeId}} • ${{nData.title || ''}}</div>
                    <div class="node-desc">${{nData.content || '(No description text)'}}</div>
                    
                    <div class="node-manage-bar">
                        <button class="btn-node-edit" onclick="openEditNodeModal('${{nodeId}}')">✏️ Edit Content</button>
                        <button class="btn-node-delete" onclick="deleteNode('${{nodeId}}')">🗑️ Delete</button>
                    </div>
                </div>

                <div class="section-label">Inbound Causal Precedents (${{inbound.length}})</div>
                ${{inHtml}}

                <div class="section-label">Outbound Dependencies (${{outbound.length}})</div>
                ${{outHtml}}
            `;
            document.getElementById('nodeDetails').innerHTML = html;
        }}

        function focusNode(nodeId) {{
            selectAndDisplayNode(nodeId);
            network.focus(nodeId, {{
                scale: 1.35,
                animation: {{ duration: 600, easingFunction: 'easeInOutQuad' }}
            }});
            network.selectNodes([nodeId]);
        }}

        function fitNetwork() {{
            resetIsolation();
            network.fit({{ animation: {{ duration: 600, easingFunction: 'easeInOutQuad' }} }});
        }}

        function zoomNetwork(factor) {{
            const currentScale = network.getScale();
            network.moveTo({{
                scale: currentScale * factor,
                animation: {{ duration: 300 }}
            }});
        }}

        function stepNode(delta) {{
            const visibleNodes = rawNodes.filter(n => !n.hidden);
            if (visibleNodes.length === 0) return;
            currentNodeIndex = (currentNodeIndex + delta + visibleNodes.length) % visibleNodes.length;
            const target = visibleNodes[currentNodeIndex];
            if (target) focusNode(target.id);
        }}

        function jumpToCluster(groupType) {{
            if (!groupType) return;
            const matching = rawNodes.filter(n => n.group === groupType);
            if (matching.length > 0) {{
                const targetIds = matching.map(n => n.id);
                network.fit({{
                    nodes: targetIds,
                    animation: {{ duration: 600, easingFunction: 'easeInOutQuad' }}
                }});
                focusNode(matching[0].id);
            }}
        }}

        function toggleIsolateNeighborhood() {{
            if (!selectedNodeId) {{
                alert("Please select a node on the canvas first to isolate its neighbors.");
                return;
            }}

            isIsolatedNeighborhood = !isIsolatedNeighborhood;
            const btn = document.getElementById('isolateBtn');
            btn.classList.toggle('active', isIsolatedNeighborhood);

            if (isIsolatedNeighborhood) {{
                const connectedNodes = new Set(network.getConnectedNodes(selectedNodeId));
                connectedNodes.add(selectedNodeId);

                const updates = rawNodes.map(n => ({{
                    id: n.id,
                    opacity: connectedNodes.has(n.id) ? 1.0 : 0.15
                }}));
                nodesDataSet.update(updates);
            }} else {{
                resetIsolation();
            }}
        }}

        function resetIsolation() {{
            isIsolatedNeighborhood = false;
            document.getElementById('isolateBtn').classList.remove('active');
            nodesDataSet.update(rawNodes.map(n => ({{ id: n.id, opacity: 1.0 }})));
        }}

        function searchNodes(query) {{
            if (!query.trim()) return;
            const q = query.toLowerCase();
            const match = rawNodes.find(n => n.id.toLowerCase().includes(q) || (n.raw_data && n.raw_data.title && n.raw_data.title.toLowerCase().includes(q)));
            if (match) {{
                focusNode(match.id);
            }}
        }}

        function filterType(typeName, chipEl) {{
            document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            chipEl.classList.add('active');

            if (typeName === 'ALL') {{
                rawNodes.forEach(n => n.hidden = false);
                nodesDataSet.update(rawNodes.map(n => ({{ id: n.id, hidden: false }})));
            }} else {{
                rawNodes.forEach(n => n.hidden = (n.group !== typeName));
                nodesDataSet.update(rawNodes.map(n => ({{ id: n.id, hidden: n.group !== typeName }})));
            }}
            updateStepIndicator();
        }}

        /* Node CRUD Operations in UI */
        let isEditing = false;

        function openEditNodeModal(nodeId) {{
            const node = rawNodes.find(n => n.id === nodeId);
            if (!node) return;

            isEditing = true;
            document.getElementById('modalTitle').innerText = `Edit Node: ${{nodeId}}`;
            document.getElementById('modalNodeId').value = nodeId;
            document.getElementById('modalNodeId').disabled = true;
            document.getElementById('modalNodeType').value = node.group || 'ArchitecturalDecision';
            document.getElementById('modalNodeTitle').value = node.raw_data.title || '';
            document.getElementById('modalNodeContent').value = node.raw_data.content || '';
            document.getElementById('nodeModal').style.display = 'flex';
        }}

        function openAddNodeModal() {{
            isEditing = false;
            document.getElementById('modalTitle').innerText = "Add New Knowledge Node";
            document.getElementById('modalNodeId').value = `MEM-${{Math.floor(100 + Math.random() * 900)}}`;
            document.getElementById('modalNodeId').disabled = false;
            document.getElementById('modalNodeType').value = 'ArchitecturalDecision';
            document.getElementById('modalNodeTitle').value = '';
            document.getElementById('modalNodeContent').value = '';
            document.getElementById('nodeModal').style.display = 'flex';
        }}

        function closeNodeModal() {{
            document.getElementById('nodeModal').style.display = 'none';
        }}

        function saveNodeModal() {{
            const nId = document.getElementById('modalNodeId').value.trim();
            const nType = document.getElementById('modalNodeType').value;
            const nTitle = document.getElementById('modalNodeTitle').value.trim();
            const nContent = document.getElementById('modalNodeContent').value.trim();

            if (!nId || !nTitle) {{
                alert("Node ID and Title are required.");
                return;
            }}

            const palette = colorMap[nType] || {{"bg": "#F8FAFC", "border": "#94A3B8", "text": "#334155"}};
            const cleanTitle = nTitle.length > 28 ? nTitle.slice(0, 28) + '...' : nTitle;
            const nodeLabel = `${{nId}}\\n${{cleanTitle}}`;

            if (isEditing) {{
                const existing = rawNodes.find(n => n.id === nId);
                if (existing) {{
                    existing.group = nType;
                    existing.label = nodeLabel;
                    existing.color = {{ background: palette.bg, border: palette.border, highlight: {{ background: "#FFF", border: palette.border }} }};
                    existing.font = {{ color: palette.text, size: 12, bold: "600" }};
                    existing.raw_data.title = nTitle;
                    existing.raw_data.content = nContent;
                    existing.raw_data.type = nType;
                    nodesDataSet.update(existing);
                }}
            }} else {{
                const newNode = {{
                    id: nId,
                    label: nodeLabel,
                    group: nType,
                    shape: "box",
                    margin: {{ top: 10, bottom: 10, left: 14, right: 14 }},
                    color: {{ background: palette.bg, border: palette.border, highlight: {{ background: "#FFF", border: palette.border }} }},
                    font: {{ color: palette.text, size: 12, bold: "600" }},
                    borderWidth: 2,
                    shadow: {{ enabled: true, color: "rgba(15, 23, 42, 0.08)", size: 10, x: 0, y: 4 }},
                    raw_data: {{ id: nId, type: nType, title: nTitle, content: nContent, category: "Custom", created_at: Date.now() }}
                }};
                rawNodes.push(newNode);
                nodesDataSet.add(newNode);
            }}

            closeNodeModal();
            updateStats();
            focusNode(nId);
        }}

        function deleteNode(nodeId) {{
            if (!confirm(`Are you sure you want to delete memory node '${{nodeId}}' and all its causal relations?`)) return;

            rawNodes = rawNodes.filter(n => n.id !== nodeId);
            nodesDataSet.remove(nodeId);

            const edgesToRemove = rawEdges.filter(e => e.from === nodeId || e.to === nodeId).map(e => e.id);
            rawEdges = rawEdges.filter(e => e.from !== nodeId && e.to !== nodeId);
            edgesDataSet.remove(edgesToRemove);

            updateStats();
            document.getElementById('nodeDetails').innerHTML = `
                <div class="node-card">
                    <span class="badge-type" style="background: var(--danger-light); color: var(--danger);">Deleted</span>
                    <div class="node-title">Node ${{nodeId}} Removed</div>
                    <div class="node-desc">The entity knowledge and its associated relationships have been removed from the active graph.</div>
                </div>
            `;
        }}

        function exportGraphData() {{
            const exportObj = {{
                exported_at: new Date().toISOString(),
                total_nodes: rawNodes.length,
                total_edges: rawEdges.length,
                nodes: rawNodes.map(n => n.raw_data || {{ id: n.id, title: n.label }}),
                edges: rawEdges.map(e => ({{ source: e.from, target: e.to, relation: e.label }}))
            }};
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportObj, null, 2));
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", `cognee_knowledge_graph_export_${{Date.now()}}.json`);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
        }}

        function toggleTheme() {{
            const body = document.body;
            const isDark = body.getAttribute('data-theme') === 'dark';
            const newTheme = isDark ? 'light' : 'dark';
            body.setAttribute('data-theme', newTheme);
            document.getElementById('themeBtn').innerHTML = isDark ? '🌙 Dark Mode' : '☀️ Light Mode';
        }}

        updateStats();
    </script>
</body>
</html>
"""
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return target_path
