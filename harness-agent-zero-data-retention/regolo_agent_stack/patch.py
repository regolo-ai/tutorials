import re
from pathlib import Path
from typing import Optional

DIFF_HEADER_RE = re.compile(r"^diff --git a/(?P<a>.+) b/(?P<b>.+)$", re.MULTILINE)
HUNK_HEADER_RE = re.compile(r"^@@ -(?P<a_start>\d+),(?P<a_len>\d+) \+(?P<b_start>\d+),(?P<b_len>\d+) @@", re.MULTILINE)

class PatchError(Exception):
    pass

def parse_unified_diff(diff_text: str) -> dict:
    files = {}
    current_file = None
    current_hunks = []
    current_hunk = None

    for line in diff_text.splitlines():
        m = DIFF_HEADER_RE.match(line)
        if m:
            if current_file and current_hunks:
                files[current_file] = {"hunks": current_hunks}
            current_file = m.group("b")
            current_hunks = []
            current_hunk = None
            continue
        if current_file is None:
            continue
        m = HUNK_HEADER_RE.match(line)
        if m:
            current_hunk = {
                "a_start": int(m.group("a_start")),
                "a_len": int(m.group("a_len")),
                "b_start": int(m.group("b_start")),
                "b_len": int(m.group("b_len")),
                "lines": [],
            }
            current_hunks.append(current_hunk)
            continue
        if current_hunk is not None and line.startswith(("+", "-", " ")):
            current_hunk["lines"].append(line)

    if current_file and current_hunks:
        files[current_file] = {"hunks": current_hunks}
    return files

def extract_patch_for_file(diff_text: str, target_file: str) -> Optional[str]:
    files = parse_unified_diff(diff_text)
    entry = files.get(target_file)
    if not entry:
        return None
    lines = [f"diff --git a/{target_file} b/{target_file}"]
    for hunk in entry["hunks"]:
        a_start = hunk["a_start"]
        a_len = hunk["a_len"]
        b_start = hunk["b_start"]
        b_len = hunk["b_len"]
        lines.append(f"@@ -{a_start},{a_len} +{b_start},{b_len} @@")
        for ln in hunk["lines"]:
            lines.append(ln)
    return "\n".join(lines)

def apply_patch_to_repo(repo_root: Path, patch_text: str) -> None:
    try:
        subprocess.run(
            ["git", "apply", "--index", patch_text],
            cwd=repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        raise PatchError(f"git apply failed: {exc.stderr.decode()}") from exc
