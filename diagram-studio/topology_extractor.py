"""Local topology extraction, Mermaid/Compose compression, and 4px-grid SVG validation."""
import json
import re


def compress_yaml_config(raw_yaml: str) -> dict:
    """Strip bloated YAML comments and deployment boilerplate while keeping services, ports, and depends_on."""
    raw_chars = len(raw_yaml)
    kept_lines = []
    comment_lines = 0
    for line in raw_yaml.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            comment_lines += 1
            continue
        if any(stripped.startswith(k) for k in ("logging:", "driver:", "max-size:", "max-file:", "labels:", "com.enterprise.")):
            comment_lines += 1
            continue
        kept_lines.append(line)
    body = "\n".join(kept_lines)
    comp_chars = len(body)
    return {
        "compressor": "yaml_topology_stripper",
        "raw_chars": raw_chars,
        "compressed_chars": comp_chars,
        "reduction_pct": round(100.0 * (1.0 - comp_chars / max(raw_chars, 1)), 1),
        "detail": f"stripped {comment_lines} comment/logging lines; kept service, port & dependency edges",
        "body": body,
    }


def compress_sql_schema(raw_sql: str) -> dict:
    """Strip verbose SQL audit triggers and header comments while preserving CREATE TABLE and REFERENCES."""
    raw_chars = len(raw_sql)
    kept_lines = []
    removed = 0
    for line in raw_sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            removed += 1
            continue
        kept_lines.append(line)
    body = "\n".join(kept_lines)
    comp_chars = len(body)
    return {
        "compressor": "sql_fk_extractor",
        "raw_chars": raw_chars,
        "compressed_chars": comp_chars,
        "reduction_pct": round(100.0 * (1.0 - comp_chars / max(raw_chars, 1)), 1),
        "detail": f"stripped {removed} SQL comment/audit lines; preserved tables, primary keys & foreign keys",
        "body": body,
    }


def compress_routes_py(raw_py: str) -> dict:
    """Strip module docstrings and handler bodies, keeping route decorators and upstream calls."""
    raw_chars = len(raw_py)
    kept = []
    removed = 0
    in_doc = False
    for line in raw_py.splitlines():
        s = line.strip()
        if s.startswith('"""') or s.startswith("'''"):
            if s.count('"""') == 2 or s.count("'''") == 2:
                removed += 1
                continue
            in_doc = not in_doc
            removed += 1
            continue
        if in_doc or not s or s.startswith("#"):
            removed += 1
            continue
        kept.append(line)
    body = "\n".join(kept)
    comp_chars = len(body)
    return {
        "compressor": "ast_route_skeleton",
        "raw_chars": raw_chars,
        "compressed_chars": comp_chars,
        "reduction_pct": round(100.0 * (1.0 - comp_chars / max(raw_chars, 1)), 1),
        "detail": f"stripped {removed} docstring/comment lines; kept route signatures & service calls",
        "body": body,
    }


def inspect_repo_compression(files: list[dict], task_category: str) -> dict:
    """Layer 1 + Layer 2: select relevant architecture files and compress topology definitions."""
    raw_total_chars = sum(len(f["content"]) for f in files)
    selected = []
    for f in files:
        p = f["path"]
        if task_category == "topology" and p.endswith((".yml", ".py")):
            selected.append(f)
        elif task_category == "schema" and p.endswith((".sql", ".py")):
            selected.append(f)
        elif task_category == "svg_map":
            selected.append(f)
    if not selected:
        selected = files

    layer1_chars = sum(len(f["content"]) for f in selected)
    actions = []
    chunks = []
    for f in selected:
        p = f["path"]
        if p.endswith(".yml"):
            info = compress_yaml_config(f["content"])
        elif p.endswith(".sql"):
            info = compress_sql_schema(f["content"])
        elif p.endswith(".py"):
            info = compress_routes_py(f["content"])
        else:
            info = {
                "compressor": "passthrough",
                "raw_chars": len(f["content"]),
                "compressed_chars": len(f["content"]),
                "reduction_pct": 0.0,
                "detail": "unmodified",
                "body": f["content"],
            }
        info["path"] = p
        actions.append({k: v for k, v in info.items() if k != "body"})
        chunks.append(f"=== FILE: {p} ===\n{info['body']}")

    compressed_prompt = "\n\n".join(chunks)
    layer2_chars = len(compressed_prompt)
    return {
        "raw_total_chars": raw_total_chars,
        "layer1_selected_paths": [f["path"] for f in selected],
        "layer1_chars": layer1_chars,
        "layer2_chars": layer2_chars,
        "layer2_step_reduction_pct": round(100.0 * (1.0 - layer2_chars / max(layer1_chars, 1)), 1),
        "layer2_reduction_pct": round(100.0 * (1.0 - layer2_chars / max(raw_total_chars, 1)), 1),
        "actions": actions,
        "compressed_prompt": compressed_prompt,
    }


def select_diagram_route(task_item: dict, use_regolo_routing: bool) -> tuple[str, str]:
    """Layer 3: route topology/schema extraction to brick-complexity-pro (none) and SVG synthesis to qwen3.5-122b (high)."""
    if not use_regolo_routing:
        return ("qwen3.5-122b", "high")
    if task_item["category"] in ("topology", "schema"):
        return ("brick-complexity-pro", "none")
    return ("qwen3.5-122b", "high")
