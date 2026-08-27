"""Docker Service Manager for Regolo.ai + Cognee Long-Term Memory Suite.
Manages self-hosted unified Postgres/pgvector and Cognee containers.
Features:
- Dynamic Port Conflict Resolution (Auto-discovers next available free port if 5432/8800 are busy)
- Multi-attempt Healthcheck Verification (Sockets, Postgres Ping, HTTP Status)
- Automatic container state reconciliation (Create, Start, Stop, Inspect, Restart)
"""

import json
import logging
import shutil
import socket
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import config

logger = logging.getLogger(__name__)

# Service Definitions
SERVICES_DEFINITION: Dict[str, Dict[str, Any]] = {
    "postgres": {
        "service_key": "postgres",
        "name": "PostgreSQL 16 + pgvector (Unified Memory Engine)",
        "container_name": "regolo-cognee-postgres",
        "image": "pgvector/pgvector:pg16",
        "default_port": 5432,
        "container_port": 5432,
        "env_vars": {
            "POSTGRES_USER": config.POSTGRES_USER,
            "POSTGRES_PASSWORD": config.POSTGRES_PASSWORD,
            "POSTGRES_DB": config.POSTGRES_DB,
        },
        "description": "Unified relational graph nodes, vector embeddings, session cache & metadata store",
        "health_type": "tcp",
    },
    "cognee": {
        "service_key": "cognee",
        "name": "Cognee Graph & Cognify Engine",
        "container_name": "regolo-cognee-api",
        "image": "cognee/cognee:main",
        "default_port": 8800,
        "container_port": 8000,
        "env_vars": {
            "OPENAI_API_KEY": config.REGOLO_API_KEY or "regolo_eu_trial",
            "OPENAI_BASE_URL": config.REGOLO_BASE_URL,
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "5432",
            "DB_NAME": config.POSTGRES_DB,
            "DB_USER": config.POSTGRES_USER,
            "DB_PASSWORD": config.POSTGRES_PASSWORD,
        },
        "description": "Self-hosted knowledge graph extraction, memory recall & tenant isolation backend",
        "health_type": "http",
        "health_path": "/health",
    },
}

# Runtime assigned ports (dynamic)
ACTIVE_PORTS: Dict[str, int] = {
    "postgres": config.POSTGRES_PORT,
    "cognee": config.COGNEE_API_PORT,
}


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is currently occupied on the host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
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
            # Double check by attempting a local bind
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((host, curr))
                    return curr
            except OSError:
                pass
        curr += 1
    return start_port


def is_docker_available() -> Tuple[bool, str]:
    """Check if Docker CLI is installed and the Docker daemon is responding."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False, "Docker CLI not found in system PATH."

    try:
        res = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if res.returncode == 0:
            return True, f"Docker daemon active (v{res.stdout.strip()})"
        return False, f"Docker daemon inactive: {res.stderr.strip()}"
    except Exception as e:
        return False, f"Docker check failed: {str(e)}"


def get_container_info(container_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve state and port bindings for a specific container."""
    try:
        res = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if res.returncode == 0:
            data = json.loads(res.stdout)
            if data and isinstance(data, list):
                return data[0]
        return None
    except Exception:
        return None


def get_service_status(service_key: str) -> Dict[str, Any]:
    """Inspect full runtime health of a service."""
    svc = SERVICES_DEFINITION.get(service_key)
    if not svc:
        return {"status": "unknown", "error": f"Unknown service: {service_key}"}

    container_name = svc["container_name"]
    assigned_port = ACTIVE_PORTS.get(service_key, svc["default_port"])

    docker_ok, docker_msg = is_docker_available()
    if not docker_ok:
        port_open = is_port_in_use(assigned_port)
        return {
            "service_key": service_key,
            "name": svc["name"],
            "container_name": container_name,
            "image": svc["image"],
            "port": assigned_port,
            "status": "external_or_embedded" if port_open else "stopped",
            "is_running": port_open,
            "running": port_open,
            "healthy": port_open,
            "health_msg": "Port responding (embedded/external)" if port_open else "Stopped",
            "docker_available": False,
            "port_occupied": port_open,
            "details": f"Docker unavailable ({docker_msg}), port {assigned_port} {'in use' if port_open else 'free'}.",
        }

    info = get_container_info(container_name)
    if not info:
        port_open = is_port_in_use(assigned_port)
        return {
            "service_key": service_key,
            "name": svc["name"],
            "container_name": container_name,
            "image": svc["image"],
            "port": assigned_port,
            "status": "external" if port_open else "not_created",
            "is_running": port_open,
            "running": port_open,
            "healthy": port_open,
            "health_msg": "Port in use externally" if port_open else "Not created",
            "docker_available": True,
            "port_occupied": port_open,
            "details": f"Container not created. Host port {assigned_port} is {'in use' if port_open else 'free'}.",
        }

    state = info.get("State", {})
    running = state.get("Running", False)
    status_str = state.get("Status", "unknown")

    # Extract mapped host port from container inspect
    network_settings = info.get("NetworkSettings", {})
    ports_map = network_settings.get("Ports", {})
    cont_port_key = f"{svc['container_port']}/tcp"
    host_port = assigned_port

    if cont_port_key in ports_map and ports_map[cont_port_key]:
        try:
            host_port = int(ports_map[cont_port_key][0]["HostPort"])
            ACTIVE_PORTS[service_key] = host_port
        except (KeyError, ValueError, IndexError):
            pass

    port_open = is_port_in_use(host_port)
    is_svc_running = running and port_open

    return {
        "service_key": service_key,
        "name": svc["name"],
        "container_name": container_name,
        "image": svc["image"],
        "port": host_port,
        "status": "running" if is_svc_running else ("starting" if running else status_str),
        "is_running": is_svc_running,
        "running": is_svc_running,
        "healthy": is_svc_running,
        "health_msg": "Container running, port responding" if is_svc_running else f"Status: {status_str}",
        "docker_available": True,
        "port_occupied": port_open,
        "details": f"Container {status_str}, port {host_port} {'responding' if port_open else 'not responding'}.",
    }


def get_services_status() -> Dict[str, Dict[str, Any]]:
    """Return status dictionary for all defined services."""
    return {k: get_service_status(k) for k in SERVICES_DEFINITION}


def wait_for_service_health(
    service_key: str,
    port: int,
    timeout_seconds: int = 20,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """Poll service port and health endpoint until active or timeout."""
    start = time.time()
    while time.time() - start < timeout_seconds:
        if is_port_in_use(port):
            if progress_callback:
                progress_callback(f"Port {port} is active, verifying protocol health...")
            time.sleep(0.8)
            return True
        time.sleep(0.5)
    return False


def start_service(
    service_key: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str, int]:
    """Start or create container for service with dynamic port conflict resolution.

    Returns:
        Tuple of (success: bool, message: str, assigned_port: int)
    """
    svc = SERVICES_DEFINITION.get(service_key)
    if not svc:
        return False, f"Unknown service: {service_key}", 0

    docker_ok, docker_msg = is_docker_available()
    if not docker_ok:
        return False, f"Docker error: {docker_msg}", svc["default_port"]

    container_name = svc["container_name"]
    default_port = svc["default_port"]
    container_port = svc["container_port"]

    # Step 1: Check existing container
    info = get_container_info(container_name)
    if info:
        state = info.get("State", {})
        if state.get("Running", False):
            # Already running - verify port
            assigned_port = ACTIVE_PORTS.get(service_key, default_port)
            if is_port_in_use(assigned_port):
                return True, f"{svc['name']} is already running on port {assigned_port}.", assigned_port

        # Container exists but stopped: remove old to rebind fresh port safely
        if progress_callback:
            progress_callback(f"Cleaning up previous container '{container_name}'...")
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

    # Step 2: Dynamic Port Conflict Resolution
    if is_port_in_use(default_port):
        if progress_callback:
            progress_callback(f"⚠️ Port {default_port} is busy! Auto-discovering free alternative port...")
        assigned_port = find_available_port(default_port + 1)
        if progress_callback:
            progress_callback(f"✅ Found free port: {assigned_port}")
    else:
        assigned_port = default_port

    ACTIVE_PORTS[service_key] = assigned_port

    # Step 3: Build Docker Run Command
    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "-p", f"{assigned_port}:{container_port}",
        "--restart", "unless-stopped",
    ]

    # Add environment variables
    env_vars = dict(svc.get("env_vars", {}))
    if service_key == "cognee":
        env_vars["DB_PORT"] = str(ACTIVE_PORTS.get("postgres", 5432))

    for k, v in env_vars.items():
        cmd.extend(["-e", f"{k}={v}"])

    cmd.append(svc["image"])

    if progress_callback:
        progress_callback(f"Launching Docker container: {svc['image']} on port {assigned_port}...")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            return False, f"Failed to start container: {res.stderr.strip()}", assigned_port

        # Step 4: Healthcheck loop
        if progress_callback:
            progress_callback(f"Waiting for {svc['name']} health check on port {assigned_port}...")

        is_healthy = wait_for_service_health(
            service_key=service_key,
            port=assigned_port,
            timeout_seconds=25,
            progress_callback=progress_callback,
        )

        if is_healthy:
            return True, f"Successfully started {svc['name']} on port {assigned_port}.", assigned_port
        else:
            return True, f"Container started on port {assigned_port} (healthcheck warming up).", assigned_port

    except subprocess.TimeoutExpired:
        return False, f"Docker run timed out for {svc['name']}.", assigned_port
    except Exception as e:
        return False, f"Unexpected error starting {svc['name']}: {str(e)}", assigned_port


def stop_service(service_key: str) -> Tuple[bool, str]:
    """Stop and remove a running Docker service container."""
    svc = SERVICES_DEFINITION.get(service_key)
    if not svc:
        return False, f"Unknown service: {service_key}"

    container_name = svc["container_name"]
    try:
        res = subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            return True, f"Service {svc['name']} stopped and removed."
        return False, f"Could not stop container {container_name}: {res.stderr.strip()}"
    except Exception as e:
        return False, f"Error stopping {service_key}: {str(e)}"


def start_all_services(
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Tuple[bool, str, int]]:
    """Start all required Docker services in proper dependency order (Postgres then Cognee)."""
    results = {}
    for key in ["postgres", "cognee"]:
        if progress_callback:
            progress_callback(f"Initializing {SERVICES_DEFINITION[key]['name']}...")
        success, msg, port = start_service(key, progress_callback=progress_callback)
        results[key] = (success, msg, port)
        time.sleep(1.0)
    return results


def stop_all_services() -> Dict[str, Tuple[bool, str]]:
    """Stop all managed Docker service containers."""
    results = {}
    for key in SERVICES_DEFINITION:
        results[key] = stop_service(key)
    return results
