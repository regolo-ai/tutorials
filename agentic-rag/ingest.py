import re
from pathlib import Path
from storage import (
    init_database,
    store_baseline_document,
    store_hierarchical_document,
)


def parse_raw_document(file_path) -> dict:
    path_obj = Path(file_path)
    content = path_obj.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    title = path_obj.stem.replace("_", " ")
    metadata = {"source": path_obj.name}

    # parse metadata from initial document lines
    body_lines = []
    for line in lines:
        if line.startswith("title:"):
            title = line.replace("title:", "").strip()
        elif line.startswith("version:"):
            metadata["version"] = line.replace("version:", "").strip()
        elif line.startswith("date:"):
            metadata["date"] = line.replace("date:", "").strip()
        else:
            body_lines.append(line)

    body_text = "\n".join(body_lines)

    # partition sections for hierarchical child table
    raw_sections = re.split(
        r"(?=section:|sezione:|##\s+)", body_text, flags=re.IGNORECASE
    )
    sections = []
    for section_idx, raw_sec in enumerate(raw_sections):
        cleaned = raw_sec.strip()
        if not cleaned:
            continue
        first_line = cleaned.splitlines()[0]
        section_title = first_line.replace("##", "").strip()
        sections.append({
            "section_title": section_title,
            "content": cleaned,
            "index": section_idx,
        })

    if not sections:
        sections = [{
            "section_title": f"initial excerpt of {title}",
            "content": body_text,
            "index": 0,
        }]

    # generate high-level parent summary
    summary_excerpt = sections[0]["content"][:300].replace("\n", " ")
    summary = f"document {title} containing {len(sections)} sections: {summary_excerpt}"

    # prepare flat baseline chunks
    baseline_chunks = []
    for sec in sections:
        baseline_chunks.append({
            "content": f"{title} - {sec['section_title']}\n{sec['content']}"
        })

    return {
        "document_id": path_obj.stem.lower(),
        "document_name": path_obj.name,
        "title": title,
        "summary": summary,
        "metadata": metadata,
        "sections": sections,
        "baseline_chunks": baseline_chunks,
    }


def ingest_path(target_path: str) -> dict:
    init_database()
    path_obj = Path(target_path).expanduser().resolve()

    if not path_obj.exists():
        raise Exception(f"path not found: {target_path}")

    files = []
    if path_obj.is_file():
        files = [path_obj]
    elif path_obj.is_dir():
        files = [
            p
            for p in path_obj.glob("*")
            if p.suffix in [".txt", ".md", ".json"]
        ]

    if not files:
        raise Exception(
            f"no readable documents (.txt, .md, .json) found in: {target_path}"
        )

    processed_docs = []
    total_baseline_chunks = 0
    total_child_chunks = 0

    for file_path in files:
        parsed = parse_raw_document(file_path)

        # store flat baseline version
        b_ids = store_baseline_document(
            document_name=parsed["document_name"],
            chunks=parsed["baseline_chunks"],
        )
        total_baseline_chunks += len(b_ids)

        # store structured hierarchical parent and children
        parent_id, c_ids = store_hierarchical_document(
            document_id=parsed["document_id"],
            document_name=parsed["document_name"],
            title=parsed["title"],
            summary=parsed["summary"],
            metadata=parsed["metadata"],
            sections=parsed["sections"],
        )
        total_child_chunks += len(c_ids)

        processed_docs.append({
            "document_id": parent_id,
            "title": parsed["title"],
            "sections_count": len(c_ids),
        })

    return {
        "status": "completed",
        "documents_count": len(processed_docs),
        "total_baseline_chunks": total_baseline_chunks,
        "total_child_chunks": total_child_chunks,
        "documents": processed_docs,
    }
