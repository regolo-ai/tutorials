import subprocess
from pathlib import Path
from typing import Optional

from .policy import redact_text, filter_files, scan_for_secrets
from .ast_engine import (
    parse_diff_modified_lines,
    extract_enclosing_scopes,
    resolve_targeted_skeletons,
    find_associated_tests,
)

MAX_DIFF_CHARS = 12000

def _is_git_repo(repo_root: Path) -> bool:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False

def _enrich_context_with_ast(repo_root: Path, diff_text: str, files: list[Path]) -> tuple[str, str, str]:
    """
    Extracts enclosing function scopes, cross-file AST skeletons, and associated tests
    to provide the LLM with surgical contextual awareness.
    """
    rel_files = [str(p.relative_to(repo_root)) for p in files]

    # 1. Enclosing Scopes (full function/class wrapping the changes)
    line_map = parse_diff_modified_lines(diff_text)
    scopes = []
    for rel_f in rel_files:
        if rel_f.endswith(".py"):
            f_path = repo_root / rel_f
            mod_lines = line_map.get(rel_f, set())
            sc = extract_enclosing_scopes(f_path, mod_lines)
            if sc:
                scopes.append(sc)
    enclosing_scopes = "\n\n".join(scopes).strip()

    # 2. Targeted AST Skeletons for called external classes and methods
    ast_skeletons = resolve_targeted_skeletons(repo_root, diff_text, rel_files)

    # 3. Associated Test Contracts (expected behavior)
    associated_tests = find_associated_tests(repo_root, rel_files)

    return (
        redact_text(enclosing_scopes) if enclosing_scopes else "",
        redact_text(ast_skeletons) if ast_skeletons else "",
        redact_text(associated_tests) if associated_tests else "",
    )

def select_staged_context(repo_root: Path, allowed_extensions: Optional[set[str]] = None) -> dict:
    allowed_extensions = allowed_extensions or {".py", ".toml", ".yaml", ".yml", ".json", ".md"}
    if not _is_git_repo(repo_root):
        # Direct project audit fallback for non-git directories (e.g. demo/ or unversioned folders)
        py_files = sorted([f for f in repo_root.glob("*.py") if not f.name.startswith(".")])
        if py_files:
            diff_lines = []
            for pf in py_files:
                rel_name = pf.name
                content = pf.read_text(encoding="utf-8", errors="ignore")
                diff_lines.append(f"diff --git a/{rel_name} b/{rel_name}")
                diff_lines.append(f"--- /dev/null\n+++ b/{rel_name}")
                for ln in content.splitlines():
                    diff_lines.append(f"+{ln}")
            diff = "\n".join(diff_lines)
            diff_type = "project files (direct audit)"
            files = filter_files(py_files)
            secrets = scan_for_secrets(diff)
            redacted_diff = redact_text(diff) if secrets else diff
            enclosing_scopes, ast_skeletons, associated_tests = _enrich_context_with_ast(repo_root, diff, files)
            return {
                "diff": redacted_diff[:MAX_DIFF_CHARS],
                "files": [str(p.relative_to(repo_root)) for p in files],
                "enclosing_scopes": enclosing_scopes,
                "ast_skeletons": ast_skeletons,
                "associated_tests": associated_tests,
                "redacted": bool(secrets),
                "secrets": secrets,
                "diff_type": diff_type,
            }

        return {
            "diff": "",
            "files": [],
            "enclosing_scopes": "",
            "ast_skeletons": "",
            "associated_tests": "",
            "redacted": False,
            "secrets": [],
            "error": f"Folder '{repo_root}' has no git tracking or Python files to inspect."
        }

    diff_type = "staged (git add)"
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--cached", "--no-color"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
        )
        if not diff.strip():
            # Fallback to unstaged working tree changes
            diff = subprocess.check_output(
                ["git", "diff", "--no-color"],
                cwd=repo_root,
                text=True,
                stderr=subprocess.PIPE,
            )
            if diff.strip():
                diff_type = "unstaged (working tree)"
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"git diff failed: {exc.stderr}") from exc

    if not diff.strip():
        return {
            "diff": "",
            "files": [],
            "enclosing_scopes": "",
            "ast_skeletons": "",
            "associated_tests": "",
            "redacted": False,
            "secrets": [],
            "diff_type": diff_type
        }

    files = []
    for line in diff.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            rel = line[6:]
            if rel != "/dev/null":
                p = repo_root / rel
                if p.suffix in allowed_extensions:
                    files.append(p)
    files = sorted(set(files))
    files = filter_files(files)

    secrets = scan_for_secrets(diff)
    redacted_diff = redact_text(diff) if secrets else diff

    enclosing_scopes, ast_skeletons, associated_tests = _enrich_context_with_ast(repo_root, diff, files)

    return {
        "diff": redacted_diff[:MAX_DIFF_CHARS],
        "files": [str(p.relative_to(repo_root)) for p in files],
        "enclosing_scopes": enclosing_scopes,
        "ast_skeletons": ast_skeletons,
        "associated_tests": associated_tests,
        "redacted": bool(secrets),
        "secrets": secrets,
        "diff_type": diff_type,
    }

def select_pr_context(repo_root: Path, base: str, head: str, allowed_extensions: Optional[set[str]] = None) -> dict:
    allowed_extensions = allowed_extensions or {".py", ".toml", ".yaml", ".yml", ".json", ".md"}
    if not _is_git_repo(repo_root):
        return {
            "diff": "",
            "files": [],
            "enclosing_scopes": "",
            "ast_skeletons": "",
            "associated_tests": "",
            "redacted": False,
            "secrets": [],
            "error": "Directory corrente non è un repository Git."
        }

    try:
        diff = subprocess.check_output(
            ["git", "diff", f"{base}...{head}", "--no-color"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"git diff failed: {exc.stderr}") from exc

    if not diff.strip():
        return {
            "diff": "",
            "files": [],
            "enclosing_scopes": "",
            "ast_skeletons": "",
            "associated_tests": "",
            "redacted": False,
            "secrets": []
        }

    files = []
    for line in diff.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            rel = line[6:]
            if rel != "/dev/null":
                p = repo_root / rel
                if p.suffix in allowed_extensions:
                    files.append(p)
    files = sorted(set(files))
    files = filter_files(files)

    secrets = scan_for_secrets(diff)
    redacted_diff = redact_text(diff) if secrets else diff

    enclosing_scopes, ast_skeletons, associated_tests = _enrich_context_with_ast(repo_root, diff, files)

    return {
        "diff": redacted_diff[:MAX_DIFF_CHARS],
        "files": [str(p.relative_to(repo_root)) for p in files],
        "enclosing_scopes": enclosing_scopes,
        "ast_skeletons": ast_skeletons,
        "associated_tests": associated_tests,
        "redacted": bool(secrets),
        "secrets": secrets,
    }

def list_git_branches(repo_root: Path) -> tuple[str, list[str]]:
    if not _is_git_repo(repo_root):
        return "", []
    try:
        curr = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except Exception:
        curr = ""

    try:
        out = subprocess.check_output(
            ["git", "branch", "-a", "--format=%(refname:short)"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
        )
        branches = []
        for line in out.splitlines():
            b = line.strip()
            if not b or "HEAD" in b:
                continue
            if b not in branches:
                branches.append(b)
        return curr, branches
    except Exception:
        return curr, []

def select_branch_context(repo_root: Path, base_branch: str, allowed_extensions: Optional[set[str]] = None) -> dict:
    allowed_extensions = allowed_extensions or {".py", ".toml", ".yaml", ".yml", ".json", ".md"}
    if not _is_git_repo(repo_root):
        return {
            "diff": "",
            "files": [],
            "enclosing_scopes": "",
            "ast_skeletons": "",
            "associated_tests": "",
            "redacted": False,
            "secrets": [],
            "error": f"Folder '{repo_root}' is not a Git repository."
        }

    curr_branch, _ = list_git_branches(repo_root)

    diff = ""
    # Try direct git diff <base_branch> (includes branch commits + uncommitted changes)
    try:
        diff = subprocess.check_output(
            ["git", "diff", base_branch, "--no-color"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        # Fallback to triple-dot notation
        try:
            diff = subprocess.check_output(
                ["git", "diff", f"{base_branch}...HEAD", "--no-color"],
                cwd=repo_root,
                text=True,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            return {
                "diff": "",
                "files": [],
                "enclosing_scopes": "",
                "ast_skeletons": "",
                "associated_tests": "",
                "redacted": False,
                "secrets": [],
                "error": f"git diff against '{base_branch}' failed: {exc.stderr}"
            }

    if not diff.strip():
        return {
            "diff": "",
            "files": [],
            "enclosing_scopes": "",
            "ast_skeletons": "",
            "associated_tests": "",
            "redacted": False,
            "secrets": [],
            "base_branch": base_branch,
            "current_branch": curr_branch,
            "diff_type": f"diff vs {base_branch}",
        }

    files = []
    for line in diff.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            rel = line[6:]
            if rel != "/dev/null":
                p = repo_root / rel
                if p.suffix in allowed_extensions:
                    files.append(p)
    files = sorted(set(files))
    files = filter_files(files)

    secrets = scan_for_secrets(diff)
    redacted_diff = redact_text(diff) if secrets else diff

    enclosing_scopes, ast_skeletons, associated_tests = _enrich_context_with_ast(repo_root, diff, files)

    return {
        "diff": redacted_diff[:MAX_DIFF_CHARS],
        "files": [str(p.relative_to(repo_root)) for p in files],
        "enclosing_scopes": enclosing_scopes,
        "ast_skeletons": ast_skeletons,
        "associated_tests": associated_tests,
        "redacted": bool(secrets),
        "secrets": secrets,
        "base_branch": base_branch,
        "current_branch": curr_branch,
        "diff_type": f"diff vs '{base_branch}'",
    }
