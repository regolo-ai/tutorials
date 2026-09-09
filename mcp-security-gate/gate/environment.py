"""
REGOLO MCP Security Gate - Environment & Dependency Manager
Automates setup, diagnostics, and verification for Python, Node.js, and Docker runtimes.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ComponentStatus:
    name: str
    installed: bool
    version: str
    details: str
    is_ready: bool


class EnvironmentManager:
    """Manages system dependencies and virtual environments for REGOLO."""

    BASE_DIR = Path(__file__).resolve().parent.parent
    VENV_DIR = BASE_DIR / ".venv"

    @classmethod
    def check_all(cls) -> Dict[str, ComponentStatus]:
        """Runs diagnostics across Python, Node.js, and Docker."""
        return {
            "python": cls.check_python(),
            "node": cls.check_node(),
            "docker": cls.check_docker(),
        }

    @classmethod
    def check_python(cls) -> ComponentStatus:
        ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        has_venv = cls.VENV_DIR.exists()
        venv_py = cls.VENV_DIR / "bin" / "python3"
        ready = sys.version_info >= (3, 9)
        details = f"Python {ver} ({sys.executable})"
        if has_venv and venv_py.exists():
            details += f" | Virtualenv active at .venv"
        return ComponentStatus(
            name="Python Runtime",
            installed=True,
            version=ver,
            details=details,
            is_ready=ready,
        )

    @classmethod
    def check_node(cls) -> ComponentStatus:
        node_bin = shutil.which("node")
        npm_bin = shutil.which("npm")
        if not node_bin:
            return ComponentStatus(
                name="Node.js Runtime",
                installed=False,
                version="Not found",
                details="Node.js is not installed or not in PATH.",
                is_ready=False,
            )
        try:
            res = subprocess.run([node_bin, "--version"], capture_output=True, text=True, timeout=3)
            ver = res.stdout.strip()
            npm_status = "with npm" if npm_bin else "missing npm"
            ready = True
            return ComponentStatus(
                name="Node.js Runtime",
                installed=True,
                version=ver,
                details=f"{node_bin} ({npm_status})",
                is_ready=ready,
            )
        except Exception as e:
            return ComponentStatus(
                name="Node.js Runtime",
                installed=False,
                version="Error",
                details=str(e),
                is_ready=False,
            )

    @classmethod
    def check_docker(cls) -> ComponentStatus:
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return ComponentStatus(
                name="Docker Engine",
                installed=False,
                version="Not found",
                details="Docker CLI is not installed or not in PATH.",
                is_ready=False,
            )
        try:
            res = subprocess.run([docker_bin, "--version"], capture_output=True, text=True, timeout=3)
            ver = res.stdout.strip()
            # Check daemon ping
            daemon_res = subprocess.run([docker_bin, "info"], capture_output=True, text=True, timeout=4)
            daemon_ok = daemon_res.returncode == 0
            details = f"{ver} | Daemon: {'Running' if daemon_ok else 'Stopped / Not Accessible'}"
            return ComponentStatus(
                name="Docker Engine",
                installed=True,
                version=ver,
                details=details,
                is_ready=daemon_ok,
            )
        except Exception as e:
            return ComponentStatus(
                name="Docker Engine",
                installed=False,
                version="Error",
                details=str(e),
                is_ready=False,
            )

    @classmethod
    def setup_python_environment(cls, log_callback=print) -> bool:
        """Creates virtualenv and installs project dependencies."""
        log_callback("Setting up Python virtual environment at .venv...")
        try:
            if not cls.VENV_DIR.exists():
                subprocess.run([sys.executable, "-m", "venv", str(cls.VENV_DIR)], check=True)
                log_callback("Virtual environment created.")

            venv_pip = cls.VENV_DIR / "bin" / "pip"
            req_file = cls.BASE_DIR / "requirements.txt"
            if req_file.exists():
                log_callback(f"Installing dependencies from requirements.txt...")
                subprocess.run([str(venv_pip), "install", "--upgrade", "pip"], check=True)
                subprocess.run([str(venv_pip), "install", "-r", str(req_file)], check=True)
                log_callback("Python dependencies successfully installed.")
            return True
        except Exception as e:
            log_callback(f"Python environment setup error: {e}")
            return False

    @classmethod
    def setup_node_environment(cls, log_callback=print) -> bool:
        """Installs npm dependencies in demo/nodejs_server."""
        npm_bin = shutil.which("npm")
        if not npm_bin:
            log_callback("npm is not installed or not in PATH.")
            return False

        node_demo_dir = cls.BASE_DIR / "demo" / "nodejs_server"
        if not node_demo_dir.exists():
            log_callback(f"Node demo directory {node_demo_dir} not found.")
            return False

        try:
            log_callback(f"Running npm install in {node_demo_dir.name}...")
            subprocess.run([npm_bin, "install"], cwd=str(node_demo_dir), check=True)
            log_callback("Node.js demo environment setup complete.")
            return True
        except Exception as e:
            log_callback(f"Node.js setup error: {e}")
            return False

    @classmethod
    def build_docker_image(cls, tag: str = "regolo-mcp-gate:latest", log_callback=print) -> bool:
        """Builds the Docker container for containerized MCP gate execution."""
        docker_bin = shutil.which("docker")
        if not docker_bin:
            log_callback("Docker is not installed.")
            return False

        dockerfile = cls.BASE_DIR / "Dockerfile"
        if not dockerfile.exists():
            log_callback("Dockerfile not found.")
            return False

        try:
            log_callback(f"Building Docker image '{tag}'...")
            subprocess.run([docker_bin, "build", "-t", tag, str(cls.BASE_DIR)], check=True)
            log_callback(f"Docker image '{tag}' successfully built.")
            return True
        except Exception as e:
            log_callback(f"Docker build error: {e}")
            return False
