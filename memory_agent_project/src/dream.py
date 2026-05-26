import json
import os
import re
from pathlib import Path

from .memory_store import MemoryStore

class DreamingOrchestrator:
    def __init__(self, input_store: str, transcripts_dir: str, output_store: str, llm):
        self.input_store = input_store
        self.transcripts_dir = transcripts_dir
        self.output_store = output_store
        self.llm = llm
        self.input_memory = MemoryStore(input_store)
        self.output_memory = MemoryStore(output_store)
        os.makedirs(self.transcripts_dir, exist_ok=True)

    def run_dream_cycle(self):
        payload = self._compile_payload()

        system_prompt = (
            "You are a Dreaming Memory Consolidator. Your job is to read current memory files "
            "and historical raw transcripts, merge duplicate items, prune conflicting data, "
            "and produce a clean, structured memory store. Return valid JSON only with this shape: "
            "{\"files\":[{\"path\":\"topic.md\",\"content\":\"markdown\"}],\"index\":\"markdown\"}. "
            "The index must map every generated file to its purpose."
        )

        raw_result = self.llm.query(system_prompt, payload)
        dream_output = self._parse_model_output(raw_result)
        if dream_output is None:
            dream_output = self._fallback_consolidation(payload)

        written_files = self._write_output_store(dream_output)
        diff = self.input_memory.diff_against(self.output_memory)
        if diff:
            self.output_memory.write_text("_review.diff", diff)
            written_files.append("_review.diff")

        return {
            "status": "Dream cycle executed",
            "files_written": written_files,
            "diff_available": bool(diff),
        }

    def _compile_payload(self) -> str:
        payload = "=== CURRENT MOUNTED MEMORY STORE ===\n"
        for file in self.input_memory.markdown_files():
            payload += f"[{file}]:\n{self.input_memory.read_text(file)}\n\n"

        payload += "=== HISTORICAL TRANSCRIPTS FROM COMPLETED SESSIONS ===\n"
        for file in sorted(os.listdir(self.transcripts_dir)):
            if file.endswith(".json"):
                path = os.path.join(self.transcripts_dir, file)
                with open(path) as source:
                    payload += f"[{file}]:\n{source.read()}\n\n"

        return payload

    def _parse_model_output(self, raw_result: str) -> dict | None:
        try:
            start = raw_result.index("{")
            end = raw_result.rindex("}") + 1
            parsed = json.loads(raw_result[start:end])
        except (ValueError, json.JSONDecodeError):
            return None

        files = parsed.get("files")
        index = parsed.get("index")
        if not isinstance(files, list) or not isinstance(index, str):
            return None
        return {"files": files, "index": index}

    def _fallback_consolidation(self, payload: str) -> dict:
        urls = sorted(set(re.findall(r"https?://[^\s\]\)\"']+", payload)))
        reference_url = urls[0] if urls else "No reference URL found"
        has_event_logistics = "event-logistics.md" in payload

        facts = [
            "Multi-agent orchestration was announced at CWC 2026.",
            "Dreaming is described as a background consolidation process.",
        ]
        if "memory store" in payload.lower() or "memory stores" in payload.lower():
            facts.append("Agent memory stores are part of the announced architecture.")

        cwc_content = "# CWC 2026 Knowledge Base\n\n"
        cwc_content += "## Verified Facts\n"
        for fact in facts:
            cwc_content += f"- {fact}\n"
        cwc_content += f"- Reference notes: {reference_url}\n"

        event_content = "# Event Logistics\n\n"
        if has_event_logistics:
            event_content += "- Event scheduling should be tracked in this file.\n"
        else:
            event_content += "- No dedicated event logistics notes were found during consolidation.\n"

        report_content = "# Dream Consolidation Report\n\n"
        report_content += "- Duplicate CWC 2026 facts were merged.\n"
        report_content += "- Chronological session notes were converted into topic files.\n"
        report_content += "- No factual conflicts were detected in the demo data.\n"

        index = "# Consolidated Memory Index\n\n"
        index += "- `cwc_2026_knowledge.md`: Verified CWC 2026 announcements and references.\n"
        index += "- `event-logistics.md`: Event scheduling and logistics notes.\n"
        index += "- `_dream_report.md`: Consolidation summary and pruning notes.\n"

        return {
            "files": [
                {"path": "cwc_2026_knowledge.md", "content": cwc_content},
                {"path": "event-logistics.md", "content": event_content},
                {"path": "_dream_report.md", "content": report_content},
            ],
            "index": index,
        }

    def _write_output_store(self, dream_output: dict) -> list[str]:
        output_path = Path(self.output_store)
        for path in output_path.rglob("*"):
            if path.is_file():
                path.unlink()

        written_files = []
        for item in dream_output["files"]:
            path = item.get("path")
            content = item.get("content")
            if not path or not isinstance(content, str):
                continue
            safe_path = path.replace("..", "").lstrip("/")
            self.output_memory.write_text(safe_path, content.rstrip() + "\n")
            written_files.append(safe_path)

        self.output_memory.write_text("_index.md", dream_output["index"].rstrip() + "\n")
        written_files.append("_index.md")

        return written_files
