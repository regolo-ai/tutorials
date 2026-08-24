"""Docker Service Manager for Deep Agents Infrastructure.
Manages required background services (Qdrant vector engine, MCP Runtime Service).
Features:
- Incremental port discovery (finds next free port if default is occupied)
- Auto-pull and container start/stop lifecycle management
- Health status inspection
"""

import json
import shutil
import socket
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import config

REQUIRED_SERVICES: Dict[str, Dict[str, Any]] = {
    "qdrant": {
        "service_key": "qdrant",
        "name": "Qdrant Vector Database",
        "container_name": "deepagents-qdrant",
        "image": "qdrant/qdrant:latest",
        "default_port": 6333,
        "container_port": 6333,
        "description": "High-performance vector engine for semantic tool discovery & embedding retrieval",
        "health_path": "/healthz",
    },
    "mcp_sandbox": {
        "service_key": "mcp_sandbox",
        "name": "MCP Tool Runtime Sandbox",
        "container_name": "deepagents-mcp-sandbox",
        "image": "python:3.14-slim",
        "default_port": 8900,
        "container_port": 8900,
        "description": "Isolated container runtime for executing and stress-testing synthesized MCP tools",
        "health_path": "/status",
    },
}


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is currently occupied on the host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False


def find_available_port(start_port: int, max_attempts: int = 100, host: str = "127.0.0.1") -> int:
    """Find the first available free port starting from start_port, incrementing by 1."""
    curr = start_port
    while curr < start_port + max_attempts:
        if not is_port_in_use(curr, host=host):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((host, curr))
                    return curr
            except OSError:
                pass
        curr += 1
    return start_port


def is_docker_available() -> Tuple[bool, str]:
    """Check if Docker CLI is installed and Docker daemon is active."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False, "Docker executable not found in PATH."

    try:
        res = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return True, f"Docker daemon active (v{res.stdout.strip()})"
        return False, f"Docker daemon is not running: {res.stderr.strip()}"
    except Exception as e:
        return False, f"Docker check failed: {str(e)}"


def get_container_info(container_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve detailed container state from Docker."""
    try:
        res = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            data = json.loads(res.stdout)
            if data and isinstance(data, list):
                return data[0]
    except Exception:
        pass
    return None


def get_services_status() -> List[Dict[str, Any]]:
    """Get status overview of all required services."""
    docker_ok, _ = is_docker_available()
    results = []

    for key, spec in REQUIRED_SERVICES.items():
        entry = {
            "key": key,
            "name": spec["name"],
            "container_name": spec["container_name"],
            "image": spec["image"],
            "default_port": spec["default_port"],
            "assigned_port": spec["default_port"],
            "status": "STOPPED",
            "docker_available": docker_ok,
            "url": f"http://127.0.0.1:{spec['default_port']}",
        }

        if docker_ok:
            info = get_container_info(spec["container_name"])
            if info:
                state = info.get("State", {})
                is_running = state.get("Running", False)
                entry["status"] = "RUNNING" if is_running else "STOPPED"

                # Extract bound host port
                ports = info.get("NetworkSettings", {}).get("Ports", {})
                port_key = f"{spec['container_port']}/tcp"
                if port_key in ports and ports[port_key]:
                    host_port = int(ports[port_key][0].get("HostPort", spec["default_port"]))
                    entry["assigned_port"] = host_port
                    entry["url"] = f"http://127.0.0.1:{host_port}"
            else:
                entry["status"] = "NOT_CREATED"

        results.append(entry)

    return results


def start_service(
    service_key: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Start or create a service container with incremental port discovery."""
    def log(msg: str):
        if log_callback:
            log_callback(msg)

    if service_key not in REQUIRED_SERVICES:
        return {"success": False, "error": f"Unknown service: {service_key}"}

    spec = REQUIRED_SERVICES[service_key]
    docker_ok, reason = is_docker_available()
    if not docker_ok:
        log(f"⚠ Docker unavailable: {reason}")
        return {"success": False, "error": reason}

    container_name = spec["container_name"]
    info = get_container_info(container_name)

    # 1. Container already exists
    if info:
        state = info.get("State", {})
        if state.get("Running", False):
            ports = info.get("NetworkSettings", {}).get("Ports", {})
            port_key = f"{spec['container_port']}/tcp"
            assigned_port = spec["default_port"]
            if port_key in ports and ports[port_key]:
                assigned_port = int(ports[port_key][0].get("HostPort", spec["default_port"]))
            log(f"✔ Container '{container_name}' is already running on port {assigned_port}.")
            return {
                "success": True,
                "status": "RUNNING",
                "container_name": container_name,
                "port": assigned_port,
                "url": f"http://127.0.0.1:{assigned_port}",
            }

        # Container exists but is stopped -> start it
        log(f"Starting existing container '{container_name}'...")
        res = subprocess.run(["docker", "start", container_name], capture_output=True, text=True)
        if res.returncode == 0:
            updated_info = get_container_info(container_name)
            ports = updated_info.get("NetworkSettings", {}).get("Ports", {}) if updated_info else {}
            port_key = f"{spec['container_port']}/tcp"
            assigned_port = spec["default_port"]
            if port_key in ports and ports[port_key]:
                assigned_port = int(ports[port_key][0].get("HostPort", spec["default_port"]))
            log(f"✔ Started container '{container_name}' on port {assigned_port}.")
            return {
                "success": True,
                "status": "STARTED",
                "container_name": container_name,
                "port": assigned_port,
                "url": f"http://127.0.0.1:{assigned_port}",
            }
        else:
            log(f"Failed to start existing container: {res.stderr.strip()}")

    # 2. Container does not exist -> find available port incrementally
    default_port = spec["default_port"]
    log(f"Checking port availability starting at {default_port}...")
    target_host_port = find_available_port(default_port)

    if target_host_port != default_port:
        log(f"⚠ Default port {default_port} in use! Incrementally bound to next available port: {target_host_port}")
    else:
        log(f"✔ Port {target_host_port} is available.")

    # 3. Pull image if needed
    log(f"Checking Docker image '{spec['image']}'...")
    subprocess.run(["docker", "pull", spec["image"]], capture_output=True, text=True)

    # 4. Create and run container
    log(f"Creating and starting container '{container_name}' on port {target_host_port}:{spec['container_port']}...")
    
    if service_key == "mcp_sandbox":
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{target_host_port}:{spec['container_port']}",
            spec["image"],
            "python3", "-m", "http.server", str(spec["container_port"]),
        ]
    else:
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{target_host_port}:{spec['container_port']}",
            spec["image"],
        ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        log(f"✔ Container '{container_name}' successfully launched on http://127.0.0.1:{target_host_port}")
        return {
            "success": True,
            "status": "CREATED_AND_RUNNING",
            "container_name": container_name,
            "port": target_host_port,
            "url": f"http://127.0.0.1:{target_host_port}",
        }
    else:
        log(f"❌ Failed to run container: {res.stderr.strip()}")
        return {"success": False, "error": res.stderr.strip()}


def start_all_services(log_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Start all required Docker services with incremental port discovery."""
    results = {}
    for key in REQUIRED_SERVICES:
        results[key] = start_service(key, log_callback=log_callback)
    return results


def stop_service(service_key: str, log_callback: Optional[Callable[[str], None]] = None) -> bool:
    """Stop a specific container service."""
    def log(msg: str):
        if log_callback:
            log_callback(msg)

    if service_key not in REQUIRED_SERVICES:
        return False

    spec = REQUIRED_SERVICES[service_key]
    container_name = spec["container_name"]
    log(f"Stopping container '{container_name}'...")
    res = subprocess.run(["docker", "stop", container_name], capture_output=True, text=True)
    return res.returncode == 0


def stop_all_services(log_callback: Optional[Callable[[str], None]] = None) -> Dict[str, bool]:
    """Stop all running managed containers."""
    results = {}
    for key in REQUIRED_SERVICES:
        results[key] = stop_service(key, log_callback=log_callback)
    return results
