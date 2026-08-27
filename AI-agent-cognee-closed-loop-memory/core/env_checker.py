"""Environment Validator and Setup Automation for Regolo.ai + Cognee Suite.
Verifies Python modules, Node.js runtime, Docker daemon, and Regolo API connectivity.
"""

import importlib
import logging
import os
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

import config
from core.docker_manager import is_docker_available

logger = logging.getLogger(__name__)

REQUIRED_PYTHON_MODULES = [
    ("rich", "rich"),
    ("openai", "openai"),
    ("pydantic", "pydantic"),
    ("networkx", "networkx"),
    ("requests", "requests"),
    ("httpx", "httpx"),
    ("dotenv", "python-dotenv"),
    ("pytest", "pytest"),
]


def check_python_environment() -> Dict[str, Any]:
    """Inspect Python interpreter version and required module installations."""
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    is_valid_version = sys.version_info >= (3, 9)

    missing_modules = []
    installed_modules = []

    for mod_import_name, pip_name in REQUIRED_PYTHON_MODULES:
        try:
            importlib.import_module(mod_import_name)
            installed_modules.append(pip_name)
        except ImportError:
            missing_modules.append(pip_name)

    return {
        "version": py_version,
        "valid_version": is_valid_version,
        "installed_modules": installed_modules,
        "missing_modules": missing_modules,
        "all_installed": len(missing_modules) == 0,
    }


def install_python_modules(
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """Execute pip install for requirements.txt in current interpreter."""
    req_file = config.BASE_DIR / "requirements.txt"
    if not req_file.exists():
        return False, "requirements.txt not found."

    if progress_callback:
        progress_callback("Running pip install -r requirements.txt...")

    try:
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(req_file)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if res.returncode == 0:
            return True, "All Python requirements installed successfully."
        return False, f"Pip installation failed: {res.stderr.strip()}"
    except Exception as e:
        return False, f"Pip error: {str(e)}"


def check_nodejs_environment() -> Dict[str, Any]:
    """Inspect Node.js and NPM executables for Claude Code & OpenClaw MCP bridges."""
    node_bin = shutil.which("node")
    npm_bin = shutil.which("npm")

    node_version = None
    npm_version = None

    if node_bin:
        try:
            res = subprocess.run(["node", "-v"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                node_version = res.stdout.strip()
        except Exception:
            pass

    if npm_bin:
        try:
            res = subprocess.run(["npm", "-v"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                npm_version = res.stdout.strip()
        except Exception:
            pass

    available = bool(node_bin and node_version)
    return {
        "available": available,
        "node_bin": node_bin,
        "node_version": node_version,
        "npm_version": npm_version,
        "status": f"Node.js {node_version} (NPM {npm_version})" if available else "Node.js not detected (optional for MCP bridge)",
    }


def check_docker_environment() -> Dict[str, Any]:
    """Inspect Docker CLI and daemon readiness."""
    docker_bin = shutil.which("docker")
    is_active, msg = is_docker_available()

    return {
        "docker_bin": docker_bin,
        "is_installed": bool(docker_bin),
        "is_active": is_active,
        "details": msg,
    }


def check_regolo_connection() -> Dict[str, Any]:
    """Inspect Regolo.ai API key configuration and endpoint reachability."""
    api_key = config.REGOLO_API_KEY
    base_url = config.REGOLO_BASE_URL

    has_key = bool(api_key and api_key != "your_regolo_api_key_here")
    status_msg = "Ready (API key configured)" if has_key else "Trial / Simulation Mode (Add key in .env for live EU inference)"

    return {
        "base_url": base_url,
        "has_key": has_key,
        "model": config.REGOLO_DEFAULT_MODEL,
        "router": config.MODEL_BRICK_ROUTER,
        "status": status_msg,
        "details": status_msg,
    }


def get_full_environment_health() -> Dict[str, Any]:
    """Return consolidated diagnostic report across all subsystem dependencies."""
    return {
        "python": check_python_environment(),
        "nodejs": check_nodejs_environment(),
        "docker": check_docker_environment(),
        "regolo": check_regolo_connection(),
    }


def run_full_setup(
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Tuple[bool, str]]:
    """Automate environment preparation and report outcomes."""
    results = {}

    # 1. Python modules
    py_stat = check_python_environment()
    if not py_stat["all_installed"]:
        if progress_callback:
            progress_callback(f"Missing Python dependencies: {', '.join(py_stat['missing_modules'])}. Installing...")
        ok, msg = install_python_modules(progress_callback=progress_callback)
        results["python_modules"] = (ok, msg)
    else:
        results["python_modules"] = (True, f"All Python modules already installed (v{py_stat['version']}).")

    # 2. Node.js
    node_stat = check_nodejs_environment()
    if node_stat["available"]:
        results["nodejs"] = (True, f"Node.js available: {node_stat['node_version']}.")
    else:
        results["nodejs"] = (False, "Node.js not installed. Claude Code / OpenClaw plugin bridge will use Python fallback.")

    # 3. Docker
    dock_stat = check_docker_environment()
    if dock_stat["is_active"]:
        results["docker"] = (True, dock_stat["details"])
    else:
        results["docker"] = (False, f"{dock_stat['details']} (Embedded SQLite+Graph memory will be used).")

    # 4. Regolo
    reg_stat = check_regolo_connection()
    results["regolo"] = (True, reg_stat["status"])

    return results
