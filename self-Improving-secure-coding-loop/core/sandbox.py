"""Sandbox Environment Manager.
Ensures Open SWE and Deepsec execute in an isolated workspace without modifying production/local source directly.
"""

import difflib
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import config


class SandboxEnvironment:
    """Isolated execution workspace for SWE agent and security scans."""

    def __init__(self, source_repo_path: str, session_id: Optional[str] = None):
        self.source_path = Path(source_repo_path).resolve()
        self.session_id = session_id or f"sandbox_{uuid.uuid4().hex[:8]}"
        self.sandbox_path = config.SANDBOX_WORK_DIR / self.session_id
        self._initialize_sandbox()

    def _initialize_sandbox(self):
        """Copy source repository into sandbox folder."""
        if self.sandbox_path.exists():
            shutil.rmtree(self.sandbox_path, ignore_errors=True)

        if self.source_path.exists():
            shutil.copytree(
                self.source_path,
                self.sandbox_path,
                ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git", "*.pyc"),
            )
        else:
            self.sandbox_path.mkdir(parents=True, exist_ok=True)

    def list_files(self) -> List[str]:
        """List relative paths of all files in sandbox."""
        files = []
        for root, _, filenames in os.walk(self.sandbox_path):
            for f in filenames:
                if not f.startswith(".") and not f.endswith(".pyc"):
                    rel = Path(root, f).relative_to(self.sandbox_path)
                    files.append(str(rel))
        return sorted(files)

    def read_file(self, relative_path: str) -> str:
        """Read content of a file in the sandbox."""
        target = self.sandbox_path / relative_path
        if not target.exists():
            return ""
        return target.read_text(encoding="utf-8", errors="ignore")

    def write_file(self, relative_path: str, content: str) -> None:
        """Write content to a file in the sandbox."""
        target = self.sandbox_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def generate_diff(self) -> str:
        """Calculate unified diff between original source and sandboxed version."""
        diff_lines = []
        original_files = set()
        if self.source_path.exists():
            for root, _, filenames in os.walk(self.source_path):
                for f in filenames:
                    if not f.startswith(".") and not f.endswith(".pyc"):
                        rel = str(Path(root, f).relative_to(self.source_path))
                        original_files.add(rel)

        sandbox_files = set(self.list_files())
        all_files = sorted(original_files.union(sandbox_files))

        for rel in all_files:
            orig_file = self.source_path / rel
            sand_file = self.sandbox_path / rel

            orig_content = orig_file.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True) if orig_file.exists() else []
            sand_content = sand_file.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True) if sand_file.exists() else []

            diff = list(difflib.unified_diff(
                orig_content,
                sand_content,
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
                n=3
            ))
            if diff:
                diff_lines.extend(diff)

        return "".join(diff_lines)

    def run_tests(self) -> Tuple[bool, str]:
        """Run pytest inside the sandbox workspace."""
        tests_dir = self.sandbox_path / "tests"
        if not tests_dir.exists():
            # Look for any test_*.py
            test_files = list(self.sandbox_path.glob("**/test_*.py"))
            if not test_files:
                return True, "No test suite found (Skipped)."

        try:
            res = subprocess.run(
                ["python3", "-m", "pytest", "-v"],
                cwd=str(self.sandbox_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            passed = res.returncode == 0
            output = res.stdout + "\n" + res.stderr
            return passed, output.strip()
        except Exception as e:
            return False, f"Test execution error: {str(e)}"

    def cleanup(self):
        """Remove temporary sandbox files."""
        if self.sandbox_path.exists():
            shutil.rmtree(self.sandbox_path, ignore_errors=True)
