"""Local wiki consolidation, FTS5/BM25 retrieval, and claim-once handoff helper (ai-memory pattern)."""
import json
import math
import re
from collections import Counter

STOPWORDS = {
    "in", "the", "what", "is", "are", "of", "and", "to", "for", "on", "with",
    "why", "does", "how", "when", "if", "by", "from", "which", "table", "file",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if t not in STOPWORDS]


def sanitize_and_consolidate_file(file_entry: dict) -> dict:
    """Layer 1 & 2: strip boilerplate/secrets and consolidate raw repo file into a compact wiki card."""
    path = file_entry["path"]
    raw = file_entry["content"]
    raw_chars = len(raw)

    # Strip repeated compliance banners and redact inline bearer secrets
    redacted_lines = []
    stripped_count = 0
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("# AUDIT-BANNER") or s.startswith("Enterprise memory note:"):
            stripped_count += 1
            continue
        line = re.sub(r"sk-[a-zA-Z0-9]{16,}", "[REDACTED_SECRET]", line)
        redacted_lines.append(line)

    body = "\n".join(redacted_lines).strip()
    # Strip leading triple-quote docstring block if present
    if body.startswith('"""') and '"""' in body[3:]:
        end_idx = body.find('"""', 3) + 3
        stripped_count += body[:end_idx].count("\n") + 1
        body = body[end_idx:].strip()

    wiki_slug = f"wiki/{path.replace('/', '_').replace('.', '_')}.md"
    comp_chars = len(body)
    return {
        "path": path,
        "wiki_page": wiki_slug,
        "compressor": "wiki_consolidator_fts5",
        "raw_chars": raw_chars,
        "compressed_chars": comp_chars,
        "reduction_pct": round(100.0 * (1.0 - comp_chars / max(raw_chars, 1)), 1),
        "detail": f"consolidated into {wiki_slug}; stripped {stripped_count} banner/docstring lines & sanitized secrets",
        "body": body,
    }


def inspect_memory_handoff(corpus: dict, question: str, top_k: int = 2) -> dict:
    """Select top-k consolidated wiki pages via FTS5/BM25 + attach the claim-once handoff brief."""
    files = corpus["files"]
    handoff_brief = corpus["handoff_brief"]
    raw_total_chars = sum(len(f["content"]) for f in files) + len(corpus["raw_session_transcript"])

    consolidated = [sanitize_and_consolidate_file(f) for f in files]
    q_tokens = tokenize(question)
    n_docs = len(consolidated)
    doc_tokens = [tokenize(c["path"] + " " + c["body"]) for c in consolidated]
    avgdl = sum(len(t) for t in doc_tokens) / max(n_docs, 1)

    df = Counter()
    for toks in doc_tokens:
        for term in set(toks):
            df[term] += 1

    scores = []
    for idx, c in enumerate(consolidated):
        tf = Counter(doc_tokens[idx])
        dl = len(doc_tokens[idx])
        score = 0.0
        for term in q_tokens:
            if term not in tf:
                continue
            idf = math.log(1.0 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * ((tf[term] * 2.5) / (tf[term] + 1.5 * (0.25 + 0.75 * (dl / max(avgdl, 1.0)))))
        stem = c["path"].rsplit("/", 1)[-1].split(".")[0].lower()
        if stem in question.lower():
            score += 12.0
        scores.append((score, idx))

    top_indices = [idx for _, idx in sorted(scores, reverse=True)[:top_k]]
    selected = [consolidated[i] for i in sorted(top_indices)]
    layer1_chars = sum(c["raw_chars"] for c in selected)

    chunks = [f"=== CLAIM-ONCE HANDOFF BRIEF ===\n{handoff_brief}"]
    actions = [
        {
            "path": "session_transcript.log -> handoff_brief.md",
            "compressor": "claim_once_handoff",
            "raw_chars": len(corpus["raw_session_transcript"]),
            "compressed_chars": len(handoff_brief),
            "reduction_pct": round(100.0 * (1.0 - len(handoff_brief) / max(len(corpus["raw_session_transcript"]), 1)), 1),
            "detail": "condensed 90-turn Claude Code transcript into typed cross-agent handoff brief",
        }
    ]
    for c in selected:
        actions.append({k: v for k, v in c.items() if k != "body"})
        chunks.append(f"=== WIKI PAGE: {c['wiki_page']} (source: {c['path']}) ===\n{c['body']}")

    compressed_prompt = "\n\n".join(chunks)
    layer2_chars = len(compressed_prompt)
    return {
        "raw_total_chars": raw_total_chars,
        "layer1_selected_paths": [c["wiki_page"] for c in selected],
        "layer1_chars": layer1_chars + len(corpus["raw_session_transcript"]),
        "layer2_chars": layer2_chars,
        "layer2_step_reduction_pct": round(
            100.0 * (1.0 - layer2_chars / max(layer1_chars + len(corpus["raw_session_transcript"]), 1)), 1
        ),
        "layer2_reduction_pct": round(100.0 * (1.0 - layer2_chars / max(raw_total_chars, 1)), 1),
        "actions": actions,
        "compressed_prompt": compressed_prompt,
    }


def select_memory_route(question_item: dict, use_regolo_routing: bool) -> tuple[str, str]:
    """Route memory recall and wiki consolidation to brick-complexity-pro (none) and deep refactor to qwen3.5-122b (high)."""
    if not use_regolo_routing:
        return ("qwen3.5-122b", "high")
    if question_item["category"] == "recall":
        return ("brick-complexity-pro", "none")
    return ("qwen3.5-122b", "high")
