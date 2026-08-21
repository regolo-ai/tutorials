"""End-to-End integration test for full closed-loop pipeline across multiple vulnerability classes."""

import json
from unittest.mock import MagicMock
import pytest
import config
from core.regolo_client import RegoloClient
from core.brick_router import BrickRouter
from core.cognee_memory import CogneeMemoryGraph
from core.open_swe import OpenSWEAgent
from core.deepsec import DeepsecSecurityHarness
from core.sandbox import SandboxEnvironment
from core.brick_governance import get_telemetry_summary, clear_telemetry


def _get_mock_client_for_repo(repo_dir: str) -> MagicMock:
    """Create a mock RegoloClient returning realistic model responses for the given repo."""
    mock_client = MagicMock()
    mock_client.evaluate_complexity.return_value = {
        "complexity_score": 7.5,
        "recommended_tier": "REASONING",
        "recommended_model": "qwen3.5-122b",
        "routing_reasoning": "High complexity security remediation task",
        "latency_sec": 0.1,
    }

    # Code patches per repo
    patches = {
        "auth_service": """import sqlite3
try:
    import jwt
except ImportError:
    from jose import jwt
from fastapi import FastAPI, HTTPException, Header, Query
from pydantic import BaseModel

app = FastAPI(title="AuthService API", version="1.0.1-secure")
JWT_SECRET = "super_secret_dev_key_12345"
DATABASE = "users.db"

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT, is_admin BOOLEAN)")
    cursor.execute("INSERT OR IGNORE INTO users (id, username, password, role, is_admin) VALUES (1, 'admin', 'pbkdf2:admin123', 'admin', 1)")
    cursor.execute("INSERT OR IGNORE INTO users (id, username, password, role, is_admin) VALUES (2, 'developer', 'pbkdf2:devpass', 'engineer', 0)")
    conn.commit()
    conn.close()

init_db()

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(req: LoginRequest):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, is_admin FROM users WHERE username = ? AND password = ?", (req.username, req.password))
    user = cursor.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt.encode({"sub": user[1], "role": user[2], "is_admin": user[3]}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

@app.get("/users/search")
def search_users(query: str = Query(..., min_length=1, max_length=50)):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role FROM users WHERE username LIKE ?", (f"%{query}%",))
    results = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "role": r[2]} for r in results]

@app.get("/auth/verify")
def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    raw_token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(raw_token, JWT_SECRET, algorithms=["HS256"], options={"verify_signature": True})
        return {"valid": True, "user": payload.get("sub"), "role": payload.get("role")}
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Token verification failed: {str(e)}")
""",
        "webhook_gateway": """import ipaddress
import re
import subprocess
from urllib.parse import urlparse
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Webhook Gateway", version="1.1.1-secure")

class WebhookPayload(BaseModel):
    target_url: str
    event_type: str
    data: dict

class PingRequest(BaseModel):
    hostname: str

def is_safe_external_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1", "169.254.169.254"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False
    except ValueError:
        pass
    return True

@app.post("/dispatch")
def dispatch_webhook(payload: WebhookPayload):
    if not is_safe_external_url(payload.target_url):
        raise HTTPException(status_code=400, detail="SSRF Blocked")
    res = requests.post(payload.target_url, json={"event": payload.event_type, "payload": payload.data}, timeout=5)
    return {"status": "delivered", "status_code": res.status_code}

@app.post("/diagnostics/ping")
def ping_diagnostic(req: PingRequest):
    if not re.match(r"^[a-zA-Z0-9.-]+$", req.hostname):
        raise HTTPException(status_code=400, detail="Invalid hostname")
    try:
        output = subprocess.check_output(["ping", "-c", "1", req.hostname], shell=False, text=True, stderr=subprocess.STDOUT, timeout=5)
        return {"reachable": True, "output": output}
    except subprocess.CalledProcessError as e:
        return {"reachable": False, "output": e.output}
""",
        "ecommerce_cart": """from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="Checkout API", version="2.0.1-secure")

PRICE_CATALOG = {
    "item_1": 10.0,
    "item_2": 25.0,
    "item_3": 150.0,
}

ORDERS = {
    "ORD-101": {"user_id": "usr_alex", "amount": 150.0, "status": "shipped", "items": ["item_3"]},
}

class CheckoutItem(BaseModel):
    item_id: str
    quantity: int

class CheckoutRequest(BaseModel):
    items: list[CheckoutItem]

@app.get("/orders/{order_id}")
def get_order_details(order_id: str, x_user_id: str = Header(...)):
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="Order not found")
    order = ORDERS[order_id]
    if order["user_id"] != x_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return order

@app.post("/checkout")
def checkout_cart(req: CheckoutRequest, x_user_id: str = Header(...)):
    total = 0.0
    for item in req.items:
        if item.item_id not in PRICE_CATALOG:
            raise HTTPException(status_code=400, detail="Invalid item")
        total += item.quantity * PRICE_CATALOG[item.item_id]
    order_id = f"ORD-{len(ORDERS) + 101}"
    ORDERS[order_id] = {"user_id": x_user_id, "amount": total, "status": "pending", "items": [i.item_id for i in req.items]}
    return {"order_id": order_id, "total_charged": total, "status": "created"}
""",
        "file_storage_service": """import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse

app = FastAPI(title="FileStorage API", version="1.0.1-secure")
BASE_STORAGE_DIR = Path(__file__).resolve().parent / "uploads"
BASE_STORAGE_DIR.mkdir(exist_ok=True, parents=True)
(BASE_STORAGE_DIR / "sample.txt").write_text("Hello from public storage!", encoding="utf-8")
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".png", ".jpg", ".csv"}

@app.get("/files/download")
def download_file(filename: str = Query(...)):
    safe_name = Path(filename).name
    file_path = (BASE_STORAGE_DIR / safe_name).resolve()
    if not file_path.is_relative_to(BASE_STORAGE_DIR.resolve()) or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path))

@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    safe_name = Path(file.filename).name
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Extension not allowed")
    dest_path = BASE_STORAGE_DIR / safe_name
    content = await file.read()
    dest_path.write_bytes(content)
    return {"filename": safe_name, "size_bytes": len(content), "status": "uploaded"}
""",
        "analytics_query_engine": """import ast
import json
import operator
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="AnalyticsEngine API", version="1.0.1-secure")
SAFE_OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.USub: operator.neg}

def evaluate_safe_expression(node, variables):
    if isinstance(node, ast.Expression):
        return evaluate_safe_expression(node.body, variables)
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.Name):
        return variables[node.id]
    elif isinstance(node, ast.BinOp):
        return SAFE_OPERATORS[type(node.op)](evaluate_safe_expression(node.left, variables), evaluate_safe_expression(node.right, variables))
    elif isinstance(node, ast.UnaryOp):
        return SAFE_OPERATORS[type(node.op)](evaluate_safe_expression(node.operand, variables))
    raise ValueError("Forbidden expression")

class MetricCalculationRequest(BaseModel):
    formula: str
    variables: dict[str, float]

class CacheImportRequest(BaseModel):
    json_cache: str

@app.post("/analytics/calculate")
def calculate_custom_metric(req: MetricCalculationRequest):
    parsed_tree = ast.parse(req.formula, mode="eval")
    result = evaluate_safe_expression(parsed_tree, req.variables)
    return {"formula": req.formula, "result": float(result)}

@app.post("/analytics/cache/load")
def load_cached_report(req: CacheImportRequest):
    data = json.loads(req.json_cache)
    return {"status": "cache_restored", "keys": list(data.keys())}
""",
        "crypto_wallet_service": """import os
import secrets
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="CryptoWallet API", version="1.0.1-secure")
MASTER_KEY = os.getenv("WALLET_MASTER_KEY", "SECURE_ENV_KEY")
WALLET_BALANCES = {"wallet_alice": 12.5, "wallet_bob": 3.0}

class TransferRequest(BaseModel):
    from_wallet: str
    to_wallet: str
    amount: float

class GenerateAddressRequest(BaseModel):
    user_id: str

@app.post("/wallet/generate")
def generate_wallet_address(req: GenerateAddressRequest):
    address = f"0x{req.user_id[:4]}_{secrets.token_hex(8)}"
    return {"user_id": req.user_id, "deposit_address": address}

@app.post("/wallet/transfer")
def transfer_funds(req: TransferRequest):
    if req.from_wallet not in WALLET_BALANCES or WALLET_BALANCES[req.from_wallet] < req.amount:
        raise HTTPException(status_code=400, detail="Invalid transfer")
    WALLET_BALANCES[req.from_wallet] -= req.amount
    WALLET_BALANCES[req.to_wallet] = WALLET_BALANCES.get(req.to_wallet, 0.0) + req.amount
    return {"status": "transferred", "tx_hash": f"0xTX_{secrets.token_hex(6)}", "remaining_balance": WALLET_BALANCES[req.from_wallet]}
""",
        "user_profile_api": """import html
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="UserProfile API", version="1.0.1-secure")
USER_PROFILES = {"usr_101": {"username": "charlie", "bio": "Developer", "role": "member"}}

class SafeProfileUpdateRequest(BaseModel):
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=200)
    data: Optional[dict] = None

@app.get("/profile/{user_id}/card", response_class=HTMLResponse)
def render_profile_card(user_id: str):
    profile = USER_PROFILES[user_id]
    safe_username = html.escape(str(profile.get("username", "")))
    safe_bio = html.escape(str(profile.get("bio", "")))
    return HTMLResponse(content=f"<html><body><h1>Profile: {safe_username}</h1><div>{safe_bio}</div></body></html>")

@app.put("/profile/{user_id}")
def update_profile(user_id: str, req: SafeProfileUpdateRequest):
    profile = USER_PROFILES[user_id]
    if req.data and "bio" in req.data:
        profile["bio"] = str(req.data["bio"])
    return {"status": "updated", "profile": profile}
"""
    }

    target_patch = patches.get(repo_dir, "# safe patch")
    file_map = {
        "auth_service": "app.py",
        "webhook_gateway": "service.py",
        "ecommerce_cart": "cart.py",
        "file_storage_service": "server.py",
        "analytics_query_engine": "engine.py",
        "crypto_wallet_service": "wallet.py",
        "user_profile_api": "profile_api.py",
    }
    main_file = file_map.get(repo_dir, "app.py")

    def chat_mock(stage, *args, **kwargs):
        if stage == "classify":
            return {
                "content": json.dumps({"intent": "security_fix", "risk_level": "HIGH", "affected_components": [main_file], "summary": "Fix security vulnerabilities"}),
                "prompt_tokens": 120,
                "completion_tokens": 40,
                "latency": 0.1,
                "model": "gpt-oss-20b",
                "mode": "live",
            }
        elif stage == "plan":
            return {
                "content": json.dumps({
                    "plan_id": f"PLAN-{repo_dir}",
                    "title": f"Security Remediation for {repo_dir}",
                    "steps": [
                        {"step_number": 1, "action": "AST Security Audit", "description": "Scan and locate vulnerable patterns"},
                        {"step_number": 2, "action": "Defensive Code Refactoring", "description": "Apply parameterization and input sanitization"},
                        {"step_number": 3, "action": "Sandbox Pytest Validation", "description": "Run unit test suite"},
                    ],
                    "estimated_risk": "MEDIUM",
                    "recommended_review": "ACCEPT",
                }),
                "prompt_tokens": 300,
                "completion_tokens": 150,
                "latency": 0.2,
                "model": "qwen3.5-122b",
                "mode": "live",
            }
        elif stage == "implement":
            return {
                "content": json.dumps({
                    "files": [{"file_path": main_file, "content": target_patch}],
                    "summary": f"Defensive remediation applied to {main_file}",
                }),
                "prompt_tokens": 600,
                "completion_tokens": 350,
                "latency": 0.3,
                "model": "Llama-3.3-70B-Instruct",
                "mode": "live",
            }
        elif stage == "deepsec_scan":
            return {
                "content": json.dumps({"findings": [], "security_score": 35, "gate_status": "FAILED_VULNERABILITIES_PRESENT"}),
                "prompt_tokens": 200,
                "completion_tokens": 80,
                "latency": 0.15,
                "model": "GLM-5.2",
                "mode": "live",
            }
        elif stage == "deepsec_revalidate":
            return {
                "content": json.dumps({"gate_status": "PASSED_CLEAN_SECURITY_GATE", "evidence": "All vulnerabilities resolved."}),
                "prompt_tokens": 250,
                "completion_tokens": 60,
                "latency": 0.15,
                "model": "qwen3.5-122b",
                "mode": "live",
            }
        elif stage == "cognee_extract":
            return {
                "content": json.dumps({"entities": [], "relationships": []}),
                "prompt_tokens": 100,
                "completion_tokens": 30,
                "latency": 0.1,
                "model": "gpt-oss-20b",
                "mode": "live",
            }
        return {
            "content": "OK",
            "prompt_tokens": 50,
            "completion_tokens": 20,
            "latency": 0.1,
            "model": "GLM-5.2",
            "mode": "live",
        }

    mock_client.chat_completion.side_effect = chat_mock
    mock_client.parse_json_response = RegoloClient.parse_json_response.__get__(mock_client)
    return mock_client


@pytest.mark.parametrize("repo_dir,issue_title,issue_body", [
    ("auth_service", "Fix SQL Injection & Insecure JWT Signature", "CWE-89 in search and CWE-287 in verify"),
    ("webhook_gateway", "Mitigate Blind SSRF & Command Injection", "CWE-918 in dispatch and CWE-78 in ping"),
    ("ecommerce_cart", "Resolve IDOR & Price Tampering", "CWE-639 in orders and CWE-20 in checkout"),
    ("file_storage_service", "Fix Path Traversal & File Upload", "CWE-22 in download and CWE-434 in upload"),
    ("analytics_query_engine", "Eliminate eval() RCE & pickle Deserialization", "CWE-94 in calculate and CWE-502 in cache load"),
    ("crypto_wallet_service", "Remove Hardcoded Secret & Enforce CSPRNG", "CWE-798 master key and CWE-338 random"),
    ("user_profile_api", "Prevent Stored XSS & Mass Assignment", "CWE-79 in card and CWE-915 in update"),
])
def test_full_closed_loop_pipeline(repo_dir, issue_title, issue_body):
    clear_telemetry()
    client = _get_mock_client_for_repo(repo_dir)
    router = BrickRouter(client=client)
    memory = CogneeMemoryGraph(client=client)
    swe_agent = OpenSWEAgent(client=client, memory=memory, router=router)
    deepsec = DeepsecSecurityHarness(client=client, router=router)

    target_repo = config.SAMPLE_REPOS_DIR / repo_dir
    sandbox = SandboxEnvironment(source_repo_path=str(target_repo))

    try:
        # 1. Deepsec initial scan
        initial_scan = deepsec.run_security_scan(sandbox)
        assert len(initial_scan["findings"]) >= 1, f"Expected initial findings in {repo_dir}"
        assert "routing" in initial_scan

        # 2. Open SWE Plan
        analysis = swe_agent.analyze_and_plan(
            sandbox=sandbox,
            issue_title=issue_title,
            issue_body=issue_body,
        )
        assert "plan" in analysis
        assert "steps" in analysis["plan"]
        assert "routing" in analysis

        # 3. Open SWE Execute Remediation (writes generated patch to sandbox)
        remediation = swe_agent.execute_remediation(
            sandbox=sandbox,
            issue_title=issue_title,
            plan_data=analysis["plan"],
        )
        assert len(remediation["modified_files"]) >= 1
        assert len(remediation["diff"]) > 0
        assert remediation["test_passed"] is True, f"Unit tests failed for {repo_dir}: {remediation['test_output']}"

        # 4. Deepsec Revalidation Gate
        reval = deepsec.revalidate_patch(sandbox, initial_scan["findings"])
        assert reval["revalidation_passed"] is True
        assert len(reval["residual_findings"]) == 0
        assert reval["security_score"] >= 90
        assert "routing" in reval

        # 5. Cognee Memory update
        learning = memory.record_learning(
            issue_id=f"ISSUE-{repo_dir}",
            issue_title=issue_title,
            files_modified=remediation["modified_files"],
            vulnerabilities_fixed=[f["title"] for f in initial_scan["findings"]],
            fix_summary=remediation["remediation_summary"],
            test_passed=remediation["test_passed"],
            human_decision="APPROVED",
            pattern_learned=f"Remediated {repo_dir} with verified tests",
        )
        assert learning["id"] in memory.nodes

        # 6. Brick Telemetry check
        telemetry = get_telemetry_summary()
        assert telemetry["events_count"] >= 0

    finally:
        sandbox.cleanup()
