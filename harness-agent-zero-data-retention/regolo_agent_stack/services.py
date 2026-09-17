import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

from .config import REPORT_DIR, BASE_DIR, REGOLO_MODEL

SERVICE_PID_FILE = REPORT_DIR / ".service.pid"

def check_environment_health(root: Path = None) -> dict:
    root = root or BASE_DIR
    venv_dir = root / ".venv"

    # Verify if running inside a virtualenv or .venv exists
    in_venv = sys.prefix != sys.base_prefix or venv_dir.is_dir()

    required_modules = [
        ("openai", "openai"),
        ("rich", "rich"),
        ("pydantic", "pydantic"),
        ("dotenv", "python-dotenv"),
        ("pytest", "pytest"),
        ("requests", "requests"),
        ("psutil", "psutil"),
    ]
    missing = []
    for mod_name, pkg_name in required_modules:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pkg_name)

    # Check Docker and Node
    docker = shutil.which("docker")
    docker_running = False
    if docker:
        res = subprocess.run(["docker", "info"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        docker_running = res.returncode == 0

    node = shutil.which("node")

    return {
        "root": str(root),
        "in_venv": in_venv,
        "venv_dir_exists": venv_dir.is_dir(),
        "modules_healthy": len(missing) == 0,
        "missing_modules": missing,
        "env_file_exists": (root / ".env").is_file(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "docker_active": docker_running,
        "node_installed": node is not None,
        "node_version": subprocess.getoutput("node --version") if node else "not installed",
    }

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

def find_available_port(start_port: int = 8080, max_attempts: int = 20) -> int:
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(port):
            return port
    raise RuntimeError(f"No free port in range {start_port}-{start_port + max_attempts}")

def check_system_environment() -> dict:
    env = {}
    env["python"] = {
        "installed": True,
        "version": subprocess.getoutput("python3 --version"),
    }
    node = shutil.which("node")
    env["nodejs"] = {
        "installed": node is not None,
        "version": subprocess.getoutput("node --version") if node else "not installed",
    }
    docker = shutil.which("docker")
    docker_running = False
    if docker:
        res = subprocess.run(["docker", "info"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        docker_running = res.returncode == 0
    env["docker"] = {
        "installed": docker is not None,
        "daemon_active": docker_running,
    }
    return env

def generate_dashboard_html(reports_dir: Path) -> Path:
    """Generates an elegant, Regolo-branded dark mode dashboard in reports/index.html."""
    index_file = reports_dir / "index.html"
    md_reports = sorted([f for f in reports_dir.glob("*.md") if f.name != "README.md"], reverse=True)

    rows_html = []
    for r in md_reports:
        name = r.name
        is_review = "review" in name
        badge = '<span class="badge badge-review">Code Review</span>' if is_review else '<span class="badge badge-benchmark">Benchmark</span>'
        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(r.stat().st_mtime))
        size_kb = round(r.stat().st_size / 1024, 1)
        rows_html.append(f"""
        <tr>
            <td>{badge}</td>
            <td><a href="{name}" target="_blank">{name}</a></td>
            <td>{mtime}</td>
            <td>{size_kb} KB</td>
        </tr>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Regolo CodeOps ZDR — OpenHarness Dashboard</title>
    <style>
        :root {{
            --bg: #0d1117;
            --surface: #161b22;
            --border: #30363d;
            --accent: #00FF88;
            --text: #c9d1d9;
            --text-white: #f0f6fc;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 960px;
            margin: 0 auto;
        }}
        .header {{
            border-bottom: 1px solid var(--border);
            padding-bottom: 24px;
            margin-bottom: 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        h1 {{
            color: var(--text-white);
            margin: 0 0 8px 0;
            font-size: 26px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .badge-zdr {{
            background: rgba(0, 255, 136, 0.15);
            color: var(--accent);
            border: 1px solid var(--accent);
            font-size: 12px;
            padding: 4px 10px;
            border-radius: 20px;
            font-weight: 600;
        }}
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
        }}
        .card-title {{
            font-size: 13px;
            color: #8b949e;
            margin-bottom: 8px;
            text-transform: uppercase;
        }}
        .card-value {{
            font-size: 22px;
            font-weight: bold;
            color: var(--text-white);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}
        th, td {{
            padding: 14px 18px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background: #21262d;
            color: var(--text-white);
            font-size: 13px;
            font-weight: 600;
        }}
        a {{
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-benchmark {{
            background: #1f6feb22;
            color: #58a6ff;
            border: 1px solid #1f6feb;
        }}
        .badge-review {{
            background: #d2992222;
            color: #e3b341;
            border: 1px solid #d29922;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>🛡️ Regolo CodeOps ZDR — OpenHarness</h1>
                <div style="color: #8b949e; font-size: 14px;">Local Audit & Benchmark Reports Engine</div>
            </div>
            <span class="badge-zdr">● Zero Data Retention (EU)</span>
        </div>
        <div class="cards">
            <div class="card">
                <div class="card-title">Total Reports</div>
                <div class="card-value">{len(md_reports)}</div>
            </div>
            <div class="card">
                <div class="card-title">Active Model</div>
                <div class="card-value" style="font-size: 18px; color: var(--accent);">{REGOLO_MODEL}</div>
            </div>
            <div class="card">
                <div class="card-title">Inference Region</div>
                <div class="card-value" style="font-size: 18px;">European Union</div>
            </div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Report File</th>
                    <th>Date Generated</th>
                    <th>Size</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows_html) if rows_html else '<tr><td colspan="4" style="text-align:center; color:#8b949e;">No reports generated yet. Run a review or benchmark to generate data.</td></tr>'}
            </tbody>
        </table>
    </div>
</body>
</html>"""
    index_file.write_text(html, encoding="utf-8")
    return index_file

def get_running_service_info() -> Optional[dict]:
    """Returns information on the active dashboard server, or None if stopped."""
    if not SERVICE_PID_FILE.exists():
        return None
    try:
        data = SERVICE_PID_FILE.read_text(encoding="utf-8").strip().split(":")
        pid = int(data[0])
        port = int(data[1])
        if is_port_in_use(port):
            return {"pid": pid, "port": port, "url": f"http://127.0.0.1:{port}"}
        else:
            SERVICE_PID_FILE.unlink(missing_ok=True)
            return None
    except Exception:
        SERVICE_PID_FILE.unlink(missing_ok=True)
        return None

def start_local_report_service(port: int = 8080) -> dict:
    # Auto-resolve port conflicts
    port = find_available_port(port)
    script = Path(__file__).parent / "report_server.py"
    if not script.exists():
        raise FileNotFoundError("report_server.py not found.")

    # Generate or refresh dashboard index.html
    generate_dashboard_html(REPORT_DIR)

    proc = subprocess.Popen(
        [sys.executable, str(script), "--port", str(port), "--dir", str(REPORT_DIR)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.8)
    if not is_port_in_use(port):
        proc.terminate()
        raise RuntimeError("Report service failed to start.")

    SERVICE_PID_FILE.write_text(f"{proc.pid}:{port}", encoding="utf-8")
    return {"pid": proc.pid, "port": port, "url": f"http://127.0.0.1:{port}"}

def stop_local_report_service(pid: Optional[int] = None) -> bool:
    if pid is None:
        info = get_running_service_info()
        if info:
            pid = info["pid"]

    if pid is None:
        return False

    try:
        if psutil:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
        else:
            import os, signal
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    finally:
        SERVICE_PID_FILE.unlink(missing_ok=True)
    return True
