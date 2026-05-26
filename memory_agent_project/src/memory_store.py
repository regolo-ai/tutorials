import difflib
import os
import re
from pathlib import Path


class MemoryStore:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def markdown_files(self) -> list[str]:
        return sorted(
            str(path.relative_to(self.root))
            for path in self.root.rglob("*.md")
            if path.is_file()
        )

    def read_text(self, relative_path: str) -> str:
        return (self.root / relative_path).read_text()

    def write_text(self, relative_path: str, content: str) -> None:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def append_text(self, relative_path: str, content: str) -> None:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a") as file:
            file.write(content)

    def has_index(self) -> bool:
        return (self.root / "_index.md").exists()

    def load_index(self) -> str:
        if not self.has_index():
            return ""
        return self.read_text("_index.md")

    def load_context(self, query: str, max_files: int = 4, max_chars_per_file: int = 5000) -> tuple[str, list[str]]:
        query_terms = set(re.findall(r"[a-z0-9_/-]{3,}", query.lower()))
        files = [file for file in self.markdown_files() if file != "_index.md"]
        scored_files = []

        for file in files:
            content = self.read_text(file)
            haystack = f"{file}\n{content}".lower()
            score = sum(1 for term in query_terms if term in haystack)
            scored_files.append((score, file, content))

        scored_files.sort(key=lambda item: (-item[0], item[1]))
        selected = scored_files[:max_files]

        context_parts = []
        loaded_files = []
        index = self.load_index()
        if index:
            context_parts.append(f"[_index.md]:\n{index[:max_chars_per_file]}")
            loaded_files.append("_index.md")

        for _, file, content in selected:
            context_parts.append(f"[{file}]:\n{content[:max_chars_per_file]}")
            loaded_files.append(file)

        return "\n\n".join(context_parts), loaded_files

    def snapshot(self) -> dict[str, str]:
        return {file: self.read_text(file) for file in self.markdown_files()}

    def diff_against(self, other: "MemoryStore") -> str:
        before = self.snapshot()
        after = other.snapshot()
        paths = sorted(set(before) | set(after))
        chunks = []

        for path in paths:
            before_lines = before.get(path, "").splitlines(keepends=True)
            after_lines = after.get(path, "").splitlines(keepends=True)
            if before_lines == after_lines:
                continue
            chunks.extend(
                difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=f"input_memory/{path}",
                    tofile=f"output_memory/{path}",
                )
            )

        return "".join(chunks)