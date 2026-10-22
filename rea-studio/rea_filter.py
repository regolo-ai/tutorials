"""Local REA evidence filtering, IPC/symbol table crusher, and model router (rea pattern)."""
import json


def filter_electron_ipc_dump(raw_json: str) -> dict:
    """Collapse vendor/UI renderer noise in an Electron IPC dump while keeping preload & main-process handlers."""
    raw_chars = len(raw_json)
    data = json.loads(raw_json)
    kept_channels = []
    collapsed_vendor = 0
    for ch in data.get("ipc_channels", []):
        if ch.get("scope") in ("main_process", "preload_bridge", "sqlite_sync"):
            kept_channels.append(ch)
        else:
            collapsed_vendor += 1
    out = json.dumps(
        {
            "bundle": data.get("bundle"),
            "collapsed_ui_vendor_channels": collapsed_vendor,
            "critical_ipc_channels": kept_channels,
        },
        separators=(",", ":"),
    )
    comp_chars = len(out)
    return {
        "compressor": "rea_ipc_bridge_filter",
        "raw_chars": raw_chars,
        "compressed_chars": comp_chars,
        "reduction_pct": round(100.0 * (1.0 - comp_chars / max(raw_chars, 1)), 1),
        "detail": f"collapsed {collapsed_vendor} UI/vendor IPC channels; preserved {len(kept_channels)} preload & main-process handlers",
        "body": out,
    }


def filter_binary_symbol_table(raw_json: str) -> dict:
    """Strip stdlib/runtime symbols from a Go/Rust binary dump while keeping crypto, auth, and sync symbols."""
    raw_chars = len(raw_json)
    data = json.loads(raw_json)
    kept_syms = []
    stripped_runtime = 0
    for sym in data.get("symbols", []):
        if sym.get("module") in ("sync_engine", "crypto_keystore", "wal_replicator"):
            kept_syms.append(sym)
        else:
            stripped_runtime += 1
    out = json.dumps(
        {
            "binary": data.get("binary"),
            "stripped_runtime_symbols": stripped_runtime,
            "domain_symbols": kept_syms,
        },
        separators=(",", ":"),
    )
    comp_chars = len(out)
    return {
        "compressor": "rea_symbol_table_sieve",
        "raw_chars": raw_chars,
        "compressed_chars": comp_chars,
        "reduction_pct": round(100.0 * (1.0 - comp_chars / max(raw_chars, 1)), 1),
        "detail": f"stripped {stripped_runtime} stdlib/runtime symbols; preserved {len(kept_syms)} domain & crypto symbols",
        "body": out,
    }


def inspect_rea_pipeline(files: list[dict], question: str) -> dict:
    """Layer 1 + Layer 2: select relevant REA evidence dumps and filter runtime/vendor noise."""
    raw_total_chars = sum(len(f["content"]) for f in files)
    q_low = question.lower()
    selected = []
    for f in files:
        p = f["path"]
        if "ipc" in q_low and "ipc" in p:
            selected.append(f)
        elif ("symbol" in q_low or "binary" in q_low or "kdf" in q_low) and "symbol" in p:
            selected.append(f)
        elif "sqlite" in q_low and "sqlite" in p:
            selected.append(f)
    if len(selected) < 2:
        selected = files

    layer1_chars = sum(len(f["content"]) for f in selected)
    actions = []
    chunks = []
    for f in selected:
        p = f["path"]
        if "ipc" in p:
            info = filter_electron_ipc_dump(f["content"])
        elif "symbol" in p:
            info = filter_binary_symbol_table(f["content"])
        else:
            info = filter_electron_ipc_dump(f["content"])
            info["compressor"] = "rea_sqlite_schema_compact"
        info["path"] = p
        actions.append({k: v for k, v in info.items() if k != "body"})
        chunks.append(f"=== REA EVIDENCE: {p} ===\n{info['body']}")

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


def select_rea_route(question_item: dict, use_regolo_routing: bool) -> tuple[str, str]:
    """Layer 3: route symbol/IPC triage to brick-complexity-pro (none) and spec reconstruction to qwen3.5-122b (high)."""
    if not use_regolo_routing:
        return ("qwen3.5-122b", "high")
    if question_item["category"] == "triage":
        return ("brick-complexity-pro", "none")
    return ("qwen3.5-122b", "high")
