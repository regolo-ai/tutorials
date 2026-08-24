"""Sandbox Environment Manager for Deep Agent Tool Synthesis.
Provides isolated filesystem workspace and test execution harness.
"""

import difflib
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import config


class SandboxEnvironment:
    """Isolated sandbox directory for multi-agent synthesis and test execution."""

    def __init__(self, source_repo_path: Optional[str] = None):
        self.sandbox_id = f"sandbox_{uuid.uuid4().hex[:8]}"
        self.sandbox_path = config.SANDBOX_WORK_DIR / self.sandbox_id
        self.sandbox_path.mkdir(exist_ok=True, parents=True)
        
        cleaned_path = str(source_repo_path).strip().strip("'\"") if source_repo_path else None
        self.source_repo_path = Path(cleaned_path).expanduser().resolve() if cleaned_path else None
        
        if self.source_repo_path and self.source_repo_path.exists():
            self._copy_source_repo()

    def _copy_source_repo(self):
        """Copy files from source repo to isolated sandbox."""
        ignored_names = {
            "__pycache__", ".pytest_cache", ".git", ".venv", "venv",
            "node_modules", "dist", "build", ".DS_Store", ".ruff_cache", ".mypy_cache",
            "data", "sandboxes", "synthesized_harness", "sample_repos", ".coverage", "coverage"
        }
        if self.source_repo_path.is_dir():
            for item in self.source_repo_path.iterdir():
                if item.name in ignored_names:
                    continue
                dest = self.sandbox_path / item.name
                if item.is_dir():
                    shutil.copytree(
                        item, dest, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(*ignored_names)
                    )
                else:
                    shutil.copy2(item, dest)

    def list_files(self) -> List[str]:
        """List all files in the sandbox relative to sandbox root."""
        ignored_rel_parts = {
            "__pycache__", ".pytest_cache", ".git", ".venv", "venv",
            "node_modules", "dist", "build", ".DS_Store", ".ruff_cache", ".mypy_cache",
            "data", "sandboxes", "synthesized_harness", ".coverage", "coverage"
        }
        files = []
        for p in self.sandbox_path.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self.sandbox_path)
                if not any(part in rel.parts for part in ignored_rel_parts):
                    files.append(str(rel))
        return sorted(files)

    def get_tree_summary(self, max_entries: int = 30) -> str:
        """Return a concise summary of the workspace files for LLM planning context."""
        files = self.list_files()
        if not files:
            return "No source files found in workspace."
        if len(files) <= max_entries:
            return "\n".join(f"- {f}" for f in files)
        sample = files[:max_entries]
        return "\n".join(f"- {f}" for f in sample) + f"\n... and {len(files) - max_entries} more files (total: {len(files)})"

    def read_file(self, rel_path: str) -> Optional[str]:
        """Read content of a file in the sandbox safely."""
        file_path = self.sandbox_path / rel_path
        if file_path.exists() and file_path.is_file():
            try:
                return file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return None
        return None

    def write_file(self, rel_path: str, content: str) -> Path:
        """Write or overwrite a file in the sandbox."""
        file_path = self.sandbox_path / rel_path
        file_path.parent.mkdir(exist_ok=True, parents=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def run_tests(self, test_rel_path: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Execute pytest in the isolated sandbox environment."""
        start = time.time()
        cmd = ["python3", "-m", "pytest", "-v", "--tb=short"]
        if test_rel_path:
            cmd.append(test_rel_path)

        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.sandbox_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = round(time.time() - start, 2)
            return {
                "passed": res.returncode == 0,
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "duration_sec": duration,
            }
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Test execution timed out after {timeout} seconds.",
                "duration_sec": timeout,
            }
        except Exception as e:
            return {
                "passed": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e),
                "duration_sec": round(time.time() - start, 2),
            }

    def compute_diff(self) -> str:
        """Compute unified diff between original source repo and current sandbox state safely."""
        if not self.source_repo_path or not self.source_repo_path.exists():
            return ""

        diff_lines = []
        sandbox_files = set(self.list_files())

        for rel_file in sandbox_files:
            orig_file = self.source_repo_path / rel_file
            new_file = self.sandbox_path / rel_file

            orig_content = []
            if orig_file.exists():
                try:
                    orig_content = orig_file.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
                except Exception:
                    pass

            new_content = []
            if new_file.exists():
                try:
                    new_content = new_file.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
                except Exception:
                    pass

            if orig_content != new_content:
                diff = difflib.unified_diff(
                    orig_content,
                    new_content,
                    fromfile=f"a/{rel_file}",
                    tofile=f"b/{rel_file}",
                )
                diff_lines.extend(diff)

        return "".join(diff_lines)

    def cleanup(self):
        """Remove sandbox folder from disk."""
        if self.sandbox_path.exists():
            shutil.rmtree(self.sandbox_path, ignore_errors=True)
