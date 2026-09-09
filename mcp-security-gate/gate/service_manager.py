"""
REGOLO MCP Security Gate - Service Manager
Manages background lifecycle of demo MCP servers and the gate proxy.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Dict, List, Optional


@dataclass
class ServiceInfo:
    id: str
    name: str
    command: List[str]
    workdir: Path
    port: Optional[int]
    status: str  # STOPPED, RUNNING, ERROR
    pid: Optional[int] = None
    log_file: Optional[Path] = None


class ServiceManager:
    """Controls background demo services and provides health/status telemetry."""

    BASE_DIR = Path(__file__).resolve().parent.parent
    LOG_DIR = BASE_DIR / ".mcp-gate" / "logs"
    PID_DIR = BASE_DIR / ".mcp-gate" / "pids"
    _active_procs: Dict[str, subprocess.Popen] = {}

    def __init__(self):
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.PID_DIR.mkdir(parents=True, exist_ok=True)

    def get_services(self) -> Dict[str, ServiceInfo]:
        """Returns the catalog of manageable MCP demo services."""
        py_exe = sys.executable

        services = {
            "safe_calculator": ServiceInfo(
                id="safe_calculator",
                name="Safe Calculator Server (Vetted)",
                command=[py_exe, str(self.BASE_DIR / "demo" / "safe_server" / "server.py")],
                workdir=self.BASE_DIR / "demo" / "safe_server",
                port=8001,
                status="STOPPED",
                log_file=self.LOG_DIR / "safe_calculator.log",
            ),
            "poisoned_server": ServiceInfo(
                id="poisoned_server",
                name="Poisoned Calculator Server (Malicious Tool)",
                command=[py_exe, str(self.BASE_DIR / "demo" / "poisoned_server" / "server.py")],
                workdir=self.BASE_DIR / "demo" / "poisoned_server",
                port=8002,
                status="STOPPED",
                log_file=self.LOG_DIR / "poisoned_server.log",
            ),
            "rugpull_v1": ServiceInfo(
                id="rugpull_v1",
                name="Rug-Pull Target Server v1.0 (Clean Baseline)",
                command=[py_exe, str(self.BASE_DIR / "demo" / "rugpull_server" / "v1" / "server.py")],
                workdir=self.BASE_DIR / "demo" / "rugpull_server" / "v1",
                port=8003,
                status="STOPPED",
                log_file=self.LOG_DIR / "rugpull_v1.log",
            ),
            "rugpull_v2": ServiceInfo(
                id="rugpull_v2",
                name="Rug-Pull Target Server v2.0 (Stealth Backdoor)",
                command=[py_exe, str(self.BASE_DIR / "demo" / "rugpull_server" / "v2" / "server.py")],
                workdir=self.BASE_DIR / "demo" / "rugpull_server" / "v2",
                port=8004,
                status="STOPPED",
                log_file=self.LOG_DIR / "rugpull_v2.log",
            ),
        }

        # Refresh PID and running state
        for s_id, s_info in services.items():
            pid = self._read_pid(s_id)
            if pid and self._is_pid_alive(pid):
                s_info.status = "RUNNING"
                s_info.pid = pid
            else:
                s_info.status = "STOPPED"
                s_info.pid = None

        return services

    def start_service(self, service_id: str) -> bool:
        """Starts a service by ID."""
        services = self.get_services()
        if service_id not in services:
            return False

        svc = services[service_id]
        if svc.status == "RUNNING":
            return True

        # Ensure log file
        log_f = open(svc.log_file, "a", encoding="utf-8")
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.BASE_DIR)
            proc = subprocess.Popen(
                svc.command,
                cwd=str(svc.workdir),
                stdin=subprocess.PIPE,
                stdout=log_f,
                stderr=log_f,
                env=env,
                start_new_session=True,
            )
            self._active_procs[service_id] = proc
            self._write_pid(service_id, proc.pid)
            time.sleep(0.3)
            return self._is_pid_alive(proc.pid)
        except Exception as e:
            return False

    def stop_service(self, service_id: str) -> bool:
        """Stops a service by ID."""
        if service_id in self._active_procs:
            p = self._active_procs.pop(service_id)
            try:
                if p.stdin:
                    p.stdin.close()
                p.terminate()
                p.wait(timeout=0.5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

        pid = self._read_pid(service_id)
        if not pid:
            return True

        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.3)
            if self._is_pid_alive(pid):
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception:
            return False
        finally:
            self._clear_pid(service_id)

        return True

    def restart_service(self, service_id: str) -> bool:
        self.stop_service(service_id)
        time.sleep(0.2)
        return self.start_service(service_id)

    def stop_all(self) -> None:
        for s_id in self.get_services().keys():
            self.stop_service(s_id)

    def _pid_file(self, service_id: str) -> Path:
        return self.PID_DIR / f"{service_id}.pid"

    def _read_pid(self, service_id: str) -> Optional[int]:
        pf = self._pid_file(service_id)
        if pf.exists():
            try:
                return int(pf.read_text(encoding="utf-8").strip())
            except Exception:
                return None
        return None

    def _write_pid(self, service_id: str, pid: int) -> None:
        self._pid_file(service_id).write_text(str(pid), encoding="utf-8")

    def _clear_pid(self, service_id: str) -> None:
        pf = self._pid_file(service_id)
        if pf.exists():
            try:
                pf.unlink()
            except Exception:
                pass

    def _is_pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
