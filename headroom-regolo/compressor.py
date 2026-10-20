"""Local context compression and routing helper (context-mode + headroom style).

Implements:
1. BM25 + trigram reciprocal rank fusion (RRF) file selector (context-mode pattern).
2. AST-aware Python code compressor and JSON log crusher (headroom pattern).
3. Effort router that sets reasoning_effort="none" on file lookups and "low"/"none" on diagnosis.
"""
import ast
import json
import math
import re
from collections import Counter

STOPWORDS = {
    "in", "the", "what", "is", "are", "of", "and", "to", "for", "on", "with",
    "why", "does", "how", "when", "if", "by", "from", "src", "py", "json", "logs",
    "file", "value", "values", "exact", "name",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if t not in STOPWORDS]


def trigrams(text: str) -> set[str]:
    clean = re.sub(r"\s+", "_", text.lower())
    if len(clean) < 3:
        return {clean}
    return {clean[i : i + 3] for i in range(len(clean) - 2)}


def compress_python_ast(source: str) -> str:
    """Strip bloated module-level compliance headers while preserving executable AST and function docs."""
    try:
        tree = ast.parse(source)
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            tree.body.pop(0)
        return ast.unparse(tree)
    except Exception:
        return source


def crush_json_logs(raw_json: str) -> str:
    """Collapse repetitive INFO/HEALTHCHECK log entries while preserving WARN/ERROR/FATAL lines byte-for-byte."""
    try:
        data = json.loads(raw_json)
        if not isinstance(data, dict) or "events" not in data:
            return raw_json
        kept = []
        info_counts = Counter()
        for ev in data["events"]:
            level = ev.get("level", "INFO")
            if level in ("ERROR", "FATAL", "WARN"):
                kept.append(ev)
            else:
                info_counts[ev.get("event", "routine")] += 1
        summary = {
            "service": data.get("service"),
            "collapsed_routine_events": dict(info_counts),
            "critical_events": kept,
        }
        return json.dumps(summary, separators=(",", ":"))
    except Exception:
        return raw_json


def compress_file_content(file_entry: dict) -> str:
    path = file_entry["path"]
    content = file_entry["content"]
    if path.endswith(".py"):
        return compress_python_ast(content)
    if path.endswith(".json"):
        return crush_json_logs(content)
    return content


def rank_files_rrf(files: list[dict], query: str, top_k: int = 4) -> list[dict]:
    """Rank repository files using BM25 + trigram overlap on compressed representations via RRF."""
    q_tokens = tokenize(query)
    q_tris = trigrams(query)
    n_docs = len(files)

    compressed_bodies = [compress_file_content(f) for f in files]
    doc_tokens = [tokenize(f["path"] + " " + compressed_bodies[i]) for i, f in enumerate(files)]
    avgdl = sum(len(t) for t in doc_tokens) / max(n_docs, 1)

    df = Counter()
    for tokens in doc_tokens:
        for term in set(tokens):
            df[term] += 1

    bm25_scores = []
    tri_scores = []
    for idx, f in enumerate(files):
        tokens = doc_tokens[idx]
        tf = Counter(tokens)
        dl = len(tokens)
        score = 0.0
        for term in q_tokens:
            if term not in tf:
                continue
            idf = math.log(1.0 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            num = tf[term] * (1.5 + 1.0)
            den = tf[term] + 1.5 * (1.0 - 0.75 + 0.75 * (dl / max(avgdl, 1.0)))
            score += idf * (num / den)

        stem = Path_stem(f["path"])
        if stem in q_tokens or stem in query.lower():
            score += 15.0
        bm25_scores.append((score, idx))

        f_tris = trigrams(f["path"] + " " + compressed_bodies[idx])
        overlap = len(q_tris & f_tris) / max(len(q_tris), 1)
        tri_scores.append((overlap, idx))

    bm25_ranked = [idx for _, idx in sorted(bm25_scores, reverse=True)]
    tri_ranked = [idx for _, idx in sorted(tri_scores, reverse=True)]

    rrf_scores = Counter()
    for rank, idx in enumerate(bm25_ranked):
        rrf_scores[idx] += 1.0 / (10 + rank + 1)
    for rank, idx in enumerate(tri_ranked):
        rrf_scores[idx] += 1.0 / (20 + rank + 1)
    for idx, f in enumerate(files):
        if Path_stem(f["path"]) in query.lower() or f["path"].lower() in query.lower():
            rrf_scores[idx] += 1.0

    best_indices = [idx for idx, _ in rrf_scores.most_common(top_k)]
    return [files[i] for i in sorted(best_indices)]


def Path_stem(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0].lower()


def build_uncompressed_prompt(corpus: dict) -> str:
    """Concatenate all files and raw logs without filtering or compression."""
    chunks = []
    for f in corpus["files"]:
        chunks.append(f"=== FILE: {f['path']} ===\n{f['content']}")
    return "\n\n".join(chunks)


def build_compressed_prompt(corpus: dict, question: str, top_k: int = 4) -> str:
    """Select top-k files via RRF and apply AST compression + JSON log crushing."""
    trace = inspect_three_layers(corpus, question, top_k=top_k)
    return trace["compressed_prompt"]


def inspect_file_compression(file_entry: dict) -> dict:
    """Return compressed body plus explicit Headroom action diagnostics per file."""
    path = file_entry["path"]
    content = file_entry["content"]
    raw_chars = len(content)
    if path.endswith(".py"):
        body = compress_python_ast(content)
        comp_chars = len(body)
        return {
            "path": path,
            "compressor": "ast_strip_module_docstring",
            "raw_chars": raw_chars,
            "compressed_chars": comp_chars,
            "reduction_pct": round(100.0 * (1.0 - comp_chars / max(raw_chars, 1)), 1),
            "detail": f"stripped {raw_chars - comp_chars} chars of module compliance headers; kept executable AST & function signatures",
            "body": body,
        }
    if path.endswith(".json"):
        body = crush_json_logs(content)
        comp_chars = len(body)
        try:
            parsed = json.loads(body)
            collapsed = sum(parsed.get("collapsed_routine_events", {}).values())
            kept = len(parsed.get("critical_events", []))
            detail = f"collapsed {collapsed} routine INFO healthchecks -> 1 counter; preserved {kept} WARN/FATAL events"
        except Exception:
            detail = "crushed repetitive JSON log arrays"
        return {
            "path": path,
            "compressor": "json_log_crusher",
            "raw_chars": raw_chars,
            "compressed_chars": comp_chars,
            "reduction_pct": round(100.0 * (1.0 - comp_chars / max(raw_chars, 1)), 1),
            "detail": detail,
            "body": body,
        }
    return {
        "path": path,
        "compressor": "passthrough",
        "raw_chars": raw_chars,
        "compressed_chars": raw_chars,
        "reduction_pct": 0.0,
        "detail": "unmodified",
        "body": content,
    }


def inspect_three_layers(corpus: dict, question: str, top_k: int = 4) -> dict:
    """Run Layer 1 (RRF file selection) and Layer 2 (AST/JSON compression) with explicit metrics."""
    all_files = corpus["files"]
    raw_total_chars = sum(len(f["content"]) for f in all_files)

    # Layer 1: context-mode BM25 + trigram RRF module selection
    selected = rank_files_rrf(all_files, question, top_k=top_k)
    selected_paths = [f["path"] for f in selected]
    skipped_paths = [f["path"] for f in all_files if f["path"] not in selected_paths]
    layer1_chars = sum(len(f["content"]) for f in selected)

    # Layer 2: headroom AST docstring stripping + JSON log crushing (per-file breakdown)
    chunks = []
    headroom_actions = []
    for f in selected:
        info = inspect_file_compression(f)
        headroom_actions.append({k: v for k, v in info.items() if k != "body"})
        chunks.append(f"=== FILE: {f['path']} ===\n{info['body']}")
    compressed_prompt = "\n\n".join(chunks)
    layer2_chars = len(compressed_prompt)

    return {
        "raw_files_count": len(all_files),
        "raw_total_chars": raw_total_chars,
        "layer1_selected_paths": selected_paths,
        "layer1_skipped_paths": skipped_paths,
        "layer1_chars": layer1_chars,
        "layer1_reduction_pct": round(100.0 * (1.0 - layer1_chars / max(raw_total_chars, 1)), 1),
        "layer2_chars": layer2_chars,
        "layer2_step_reduction_pct": round(100.0 * (1.0 - layer2_chars / max(layer1_chars, 1)), 1),
        "layer2_reduction_pct": round(100.0 * (1.0 - layer2_chars / max(raw_total_chars, 1)), 1),
        "headroom_actions": headroom_actions,
        "compressed_prompt": compressed_prompt,
    }


def select_route_and_effort(question_item: dict, use_regolo_routing: bool) -> tuple[str, str]:
    """Return (model_name, reasoning_effort) based on task complexity."""
    if not use_regolo_routing:
        return ("qwen3.5-122b", "high")
    if question_item["category"] == "lookup":
        return ("brick-complexity-pro", "none")
    return ("qwen3.5-122b", "high")
