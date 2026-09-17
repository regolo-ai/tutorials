"""
Targeted AST Context Intelligence Engine
Extracts enclosing function scopes, cross-file interface skeletons, and associated test contracts
using exclusively Python's standard library `ast` module.
"""

import ast
import re
from pathlib import Path
from typing import Optional

MAX_AST_SKELETON_CHARS = 4000
MAX_ENCLOSING_SCOPE_CHARS = 4000
MAX_ASSOCIATED_TESTS_CHARS = 3000

def parse_diff_modified_lines(diff_text: str) -> dict[str, set[int]]:
    """
    Parses unified git diff output to map each modified file to the set of
    added/modified line numbers in the new version of the file.
    """
    files_to_lines: dict[str, set[int]] = {}
    current_file: Optional[str] = None
    current_line = 0

    diff_file_re = re.compile(r"^\+\+\+ b/(.+)$")
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    for line in diff_text.splitlines():
        file_match = diff_file_re.match(line)
        if file_match:
            current_file = file_match.group(1).strip()
            if current_file != "/dev/null":
                files_to_lines.setdefault(current_file, set())
            continue

        if not current_file:
            continue

        hunk_match = hunk_re.match(line)
        if hunk_match:
            current_line = int(hunk_match.group(1))
            continue

        if line.startswith("+") and not line.startswith("+++"):
            files_to_lines.setdefault(current_file, set()).add(current_line)
            current_line += 1
        elif not line.startswith("-"):
            current_line += 1

    return files_to_lines

def extract_called_symbols_from_diff(diff_text: str) -> set[str]:
    """
    Extracts identifiers, function calls, class instantiations, and attributes
    called inside the added/modified lines of a git diff.
    """
    symbols = set()
    added_lines = [
        line[1:].strip()
        for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]

    # Pattern for function calls: foo(...) or obj.foo(...)
    call_pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
    # Pattern for CamelCase classes: e.g. AuthService, RateLimiter
    class_pattern = re.compile(r"\b([A-Z][a-zA-Z0-9_]+)\b")
    # Pattern for attribute accesses: obj.method_or_attr
    attr_pattern = re.compile(r"\.([a-zA-Z_][a-zA-Z0-9_]*)\b")

    for code_line in added_lines:
        for m in call_pattern.finditer(code_line):
            sym = m.group(1)
            if sym not in ("if", "for", "while", "with", "return", "print", "len", "range", "str", "int", "float", "bool", "dict", "list", "set"):
                symbols.add(sym)
        for m in class_pattern.finditer(code_line):
            symbols.add(m.group(1))
        for m in attr_pattern.finditer(code_line):
            sym = m.group(1)
            if len(sym) > 2 and sym not in ("get", "append", "items", "keys", "values", "pop"):
                symbols.add(sym)

    return symbols

def extract_enclosing_scopes(file_path: Path, modified_lines: set[int]) -> str:
    """
    Finds the full FunctionDef or ClassDef AST nodes enclosing the modified lines,
    allowing the LLM to inspect local locks, context managers, and local definitions.
    """
    if not file_path.is_file() or not modified_lines:
        return ""

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)
    except Exception:
        return ""

    matched_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start_line = getattr(node, "lineno", None)
            end_line = getattr(node, "end_lineno", None)
            if start_line and end_line:
                # Check if any modified line falls inside this node
                node_line_range = range(start_line, end_line + 1)
                if any(m in node_line_range for m in modified_lines):
                    matched_nodes.append((start_line, end_line, node))

    if not matched_nodes:
        return ""

    # Sort nodes by size (start_line, -end_line) and filter redundant inner ones
    matched_nodes.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    scopes_text = []
    seen_ranges = []
    for s_line, e_line, node in matched_nodes:
        # Avoid duplicating scopes already covered by an enclosing scope
        if any(s_line >= s and e_line <= e for s, e in seen_ranges):
            continue
        seen_ranges.append((s_line, e_line))

        segment = ast.get_source_segment(content, node)
        if segment:
            scope_header = f"# Enclosing scope in {file_path.name} (lines {s_line}-{e_line}):\n{segment}\n"
            scopes_text.append(scope_header)

    full_text = "\n".join(scopes_text).strip()
    if len(full_text) > MAX_ENCLOSING_SCOPE_CHARS:
        return full_text[:MAX_ENCLOSING_SCOPE_CHARS] + "\n# ... [enclosing scope truncated for brevity]"
    return full_text

def _format_function_signature(func_node: ast.FunctionDef | ast.AsyncFunctionDef, indent: str = "") -> str:
    """Formats a FunctionDef node into its clean signature string."""
    args_list = []
    for arg in func_node.args.args:
        arg_str = arg.arg
        if arg.annotation:
            try:
                arg_str += f": {ast.unparse(arg.annotation)}"
            except Exception:
                pass
        args_list.append(arg_str)

    ret_annotation = ""
    if func_node.returns:
        try:
            ret_annotation = f" -> {ast.unparse(func_node.returns)}"
        except Exception:
            pass

    async_prefix = "async " if isinstance(func_node, ast.AsyncFunctionDef) else ""
    return f"{indent}{async_prefix}def {func_node.name}({', '.join(args_list)}){ret_annotation}: ..."

def extract_file_ast_skeleton(file_path: Path) -> dict[str, str]:
    """
    Extracts class and function definitions from a Python file into an AST skeleton map.
    Returns: {symbol_name: formatted_skeleton_string}
    """
    symbol_map = {}
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)
    except Exception:
        return symbol_map

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_lines = [f"class {node.name}:"]
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig = _format_function_signature(item, indent="    ")
                    class_lines.append(sig)
                    symbol_map[item.name] = sig
            class_skeleton = "\n".join(class_lines)
            symbol_map[node.name] = class_skeleton

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = _format_function_signature(node, indent="")
            symbol_map[node.name] = sig

    return symbol_map

def build_project_symbol_index(repo_root: Path, exclude_rel_files: set[str] = None) -> dict[str, dict]:
    """
    Scans repository Python modules to index exported classes and functions.
    Returns: {symbol_name: {"file": rel_path, "skeleton": str}}
    """
    exclude = exclude_rel_files or set()
    index = {}

    try:
        for py_file in repo_root.glob("**/*.py"):
            rel_path = str(py_file.relative_to(repo_root))
            parts = py_file.parts

            # Skip hidden dirs, virtual environments, tests, build artifacts
            if any(p.startswith((".", "build", "dist")) for p in parts):
                continue
            if ".venv" in parts or "tests" in parts or rel_path in exclude:
                continue

            symbols = extract_file_ast_skeleton(py_file)
            for sym, skel in symbols.items():
                if sym not in index:
                    index[sym] = {"file": rel_path, "skeleton": skel}
    except Exception:
        pass

    return index

def resolve_targeted_skeletons(
    repo_root: Path,
    diff_text: str,
    modified_files: list[str],
    max_chars: int = MAX_AST_SKELETON_CHARS
) -> str:
    """
    Cross-references called symbols in the diff against project symbols,
    returning a compact Markdown code block containing only the referenced interfaces.
    """
    called_symbols = extract_called_symbols_from_diff(diff_text)
    if not called_symbols:
        return ""

    index = build_project_symbol_index(repo_root, exclude_rel_files=set(modified_files))
    matched_skeletons: dict[str, set[str]] = {}
    total_chars = 0

    for sym in sorted(called_symbols):
        if sym in index:
            entry = index[sym]
            file_name = entry["file"]
            skel = entry["skeleton"]
            matched_skeletons.setdefault(file_name, set()).add(skel)

    if not matched_skeletons:
        return ""

    blocks = []
    for file_name, skels in sorted(matched_skeletons.items()):
        block_text = f"# --- {file_name} ---\n" + "\n".join(sorted(skels))
        if total_chars + len(block_text) > max_chars:
            blocks.append("# ... [additional interfaces truncated for brevity]")
            break
        blocks.append(block_text)
        total_chars += len(block_text)

    return "\n\n".join(blocks).strip()

def find_associated_tests(repo_root: Path, modified_files: list[str], max_chars: int = MAX_ASSOCIATED_TESTS_CHARS) -> str:
    """
    Locates unit tests corresponding to modified files (e.g. test_<file>.py)
    and extracts test signatures and assertions to establish the expected behavior.
    """
    test_blocks = []
    total_chars = 0

    for rel_file in modified_files:
        p = Path(rel_file)
        base_stem = p.stem.replace("test_", "")
        candidate_patterns = [
            f"**/test_{base_stem}.py",
            f"**/{base_stem}_test.py",
            f"tests/test_{base_stem}.py",
            f"test_{base_stem}.py",
        ]

        found_tests = []
        for pat in candidate_patterns:
            for t_file in repo_root.glob(pat):
                if t_file.is_file() and ".venv" not in t_file.parts:
                    found_tests.append(t_file)

        for test_file in sorted(set(found_tests)):
            try:
                content = test_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content)
                test_sigs = []
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                        # Extract docstring if present
                        doc = ast.get_docstring(node)
                        doc_str = f" # {doc}" if doc else ""
                        test_sigs.append(f"def {node.name}(): ...{doc_str}")

                if test_sigs:
                    rel_test = str(test_file.relative_to(repo_root))
                    block = f"# Test Contract: {rel_test}\n" + "\n".join(test_sigs[:10])
                    if total_chars + len(block) > max_chars:
                        break
                    test_blocks.append(block)
                    total_chars += len(block)
            except Exception:
                continue

    return "\n\n".join(test_blocks).strip()
