from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from langchain_core.tools import tool

REPO_ROOT = Path(os.environ.get("TARGET_REPO_PATH", "./target-repo")).resolve()

BLOCKED_PREFIXES = (".github/", "infra/", "terraform/", "migrations/")


def _run(command: list[str]) -> dict:
    cmd_str = " ".join(command)
    print(f"     [Tool Command] Running: {cmd_str}", flush=True)
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    passed = result.returncode == 0
    print(f"     [Tool Command] Finished with exit code {result.returncode} (Passed: {passed})", flush=True)

    return {
        "command": cmd_str,
        "exit_code": result.returncode,
        "passed": passed,
        "stdout": result.stdout[-12000:],
        "stderr": result.stderr[-12000:],
    }


def _resolve_safe_path(path: str) -> Path:
    file_path = (REPO_ROOT / path).resolve()

    if REPO_ROOT != file_path and REPO_ROOT not in file_path.parents:
        raise ValueError(f"Path escapes repository root: {path}")

    return file_path


@tool
def read_file(path: str) -> str:
    """Read a UTF-8 file under the repository root."""
    print(f"     [Tool] Reading file: {path}", flush=True)
    file_path = _resolve_safe_path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return file_path.read_text(encoding="utf-8")


@tool
def write_file(path: str, content: str) -> str:
    """Write a UTF-8 source file under the repository root."""
    print(f"     [Tool] Writing file: {path}", flush=True)
    normalized = path[2:] if path.startswith("./") else path

    if normalized.startswith(BLOCKED_PREFIXES):
        raise ValueError(f"Protected path: {path}")

    file_path = _resolve_safe_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"Wrote {path}"


@tool
def run_pytest(target: str = "tests") -> dict:
    """Run pytest inside the target repository. Returns exit code and compact stdout/stderr."""
    return _run([sys.executable, "-m", "pytest", target, "-q", "--maxfail=1"])


@tool
def run_ruff() -> dict:
    """Run ruff checks on the target repository."""
    return _run([sys.executable, "-m", "ruff", "check", "."])


@tool
def run_typecheck() -> dict:
    """Run mypy when configured. Remove this tool if the repo does not use mypy."""
    return _run([sys.executable, "-m", "mypy", "src"])


@tool
def git_diff() -> str:
    """Return the current uncommitted diff in the target repository."""
    return _run(["git", "diff", "--"])["stdout"]
