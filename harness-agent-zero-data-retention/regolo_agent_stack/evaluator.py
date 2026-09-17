import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .config import BENCHMARK_DIR

def is_docker_available() -> bool:
    """Checks if Docker daemon is running and reachable."""
    try:
        res = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return res.returncode == 0
    except Exception:
        return False

def evaluate_code(solution_code: str, task_dir: Path = None, prefer_docker: bool = False) -> dict:
    task_dir = task_dir or (BENCHMARK_DIR / "task_01")
    test_file = task_dir / "test_problem.py"
    start = time.time()

    with tempfile.TemporaryDirectory() as tmp:
        prob = Path(tmp) / "problem.py"
        test_dest = Path(tmp) / "test_problem.py"
        prob.write_text(solution_code, encoding="utf-8")
        test_dest.write_text(test_file.read_text(encoding="utf-8"), encoding="utf-8")

        # Level 1: Docker Sandbox (if requested and Docker is active)
        if prefer_docker and is_docker_available():
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{tmp}:/workspace:ro",
                "-w", "/workspace",
                "--network", "none",
                "--memory", "256m",
                "python:3.11-slim",
                "pytest", "test_problem.py", "-q"
            ]
            sandbox_type = "docker"
        else:
            # Level 2: Ephemeral Local Sandbox with strict timeout
            cmd = [sys.executable, "-m", "pytest", str(test_dest), "-q"]
            sandbox_type = "tempfile"

        try:
            res = subprocess.run(
                cmd,
                cwd=tmp,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
            )
            passed = res.returncode == 0
            output = res.stdout if passed else (res.stdout + "\n" + res.stderr)
        except subprocess.TimeoutExpired:
            passed = False
            output = "Execution timed out after 15s in sandbox."
        except Exception as exc:
            passed = False
            output = str(exc)

        duration = round(time.time() - start, 2)
        return {
            "success": passed,
            "output": output,
            "duration_sec": duration,
            "sandbox": sandbox_type,
        }
