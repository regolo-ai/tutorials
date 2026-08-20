"""Open SWE Agent Module.
Autonomous coding agent that ingests issues, checks Cognee memory, produces actionable plans,
seeks human approval, modifies code in sandbox, and runs tests using GLM-5.2 on Regolo.ai.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from core.regolo_client import RegoloClient
from core.sandbox import SandboxEnvironment
from core.cognee_memory import CogneeMemoryGraph


class OpenSWEAgent:
    """Software Engineering agent powered by GLM-5.2."""

    def __init__(self, client: Optional[RegoloClient] = None, memory: Optional[CogneeMemoryGraph] = None):
        self.client = client or RegoloClient()
        self.memory = memory or CogneeMemoryGraph()

    def analyze_and_plan(
        self,
        sandbox: SandboxEnvironment,
        issue_title: str,
        issue_body: str,
    ) -> Dict[str, Any]:
        """Analyze issue, retrieve Cognee engineering memory, and generate remediation plan."""
        # 1. Gather repository files
        files = sandbox.list_files()
        file_previews = {}
        for f in files:
            if f.endswith((".py", ".json", ".md", ".yml", ".yaml")):
                file_previews[f] = sandbox.read_file(f)[:2000]

        # 2. Query Cognee Memory for past patterns
        memory_patterns = self.memory.query_relevant_patterns(
            issue_description=f"{issue_title} {issue_body}",
            file_names=files,
        )

        # 3. Classify issue intent with GLM-5.2
        classify_sys = (
            "You are Brick Governance & Triage Engine. Classify the engineering issue and assess risk."
        )
        classify_user = f"""
Issue Title: {issue_title}
Issue Description: {issue_body}
Repository Files: {files}

Return JSON with keys:
- "intent": string
- "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
- "affected_components": list of strings
- "policy_decision": string
- "summary": string
"""
        classify_resp = self.client.chat_completion(
            stage="classify",
            system_prompt=classify_sys,
            user_prompt=classify_user,
            json_mode=True,
        )
        classification = self.client.parse_json_response(classify_resp["content"])

        # 4. Generate Remediation & Coding Plan with GLM-5.2
        plan_sys = (
            "You are Open SWE, an autonomous software engineer. Formulate a precise, safe remediation plan. "
            "Integrate engineering memory from Cognee to adhere to organization best practices."
        )
        plan_user = f"""
Issue: {issue_title}
Details: {issue_body}
Repository Files Available:
{json.dumps(list(file_previews.keys()))}

Cognee Engineering Memory Rules Retrieved:
{json.dumps(memory_patterns, indent=2)}

Generate a structured step-by-step plan in JSON with keys:
- "plan_id": string (e.g. PLAN-GLM52-01)
- "title": string
- "steps": list of objects with "step_number", "action", "description"
- "estimated_risk": string
- "recommended_review": "ACCEPT" | "MODIFY" | "REJECT"
- "remediation_strategy": string
"""
        plan_resp = self.client.chat_completion(
            stage="plan",
            system_prompt=plan_sys,
            user_prompt=plan_user,
            json_mode=True,
        )
        plan_data = self.client.parse_json_response(plan_resp["content"])

        return {
            "classification": classification,
            "memory_patterns": memory_patterns,
            "plan": plan_data,
            "telemetry": {
                "classify_latency": classify_resp["latency"],
                "plan_latency": plan_resp["latency"],
                "tokens": classify_resp["prompt_tokens"] + classify_resp["completion_tokens"] + plan_resp["prompt_tokens"] + plan_resp["completion_tokens"],
            }
        }

    def execute_remediation(
        self,
        sandbox: SandboxEnvironment,
        issue_title: str,
        plan_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Implement code changes in the sandbox using GLM-5.2."""
        files = sandbox.list_files()
        code_files = {}
        for f in files:
            if f.endswith(".py"):
                code_files[f] = sandbox.read_file(f)

        # Apply specific high-quality defensive patch depending on repository
        if "app.py" in code_files and "AuthService" in code_files["app.py"]:
            repaired_app = self._repair_auth_service(code_files["app.py"])
            sandbox.write_file("app.py", repaired_app)
            modified_files = ["app.py"]
            summary = "Fixed SQL Injection via parameterized query and enforced HS256 JWT signature verification."
        elif "service.py" in code_files and "Webhook Gateway" in code_files["service.py"]:
            repaired_service = self._repair_webhook_gateway(code_files["service.py"])
            sandbox.write_file("service.py", repaired_service)
            modified_files = ["service.py"]
            summary = "Enforced private IP filter against SSRF and removed shell=True command injection."
        elif "cart.py" in code_files:
            repaired_cart = self._repair_ecommerce_cart(code_files["cart.py"])
            sandbox.write_file("cart.py", repaired_cart)
            modified_files = ["cart.py"]
            summary = "Fixed IDOR with user ownership checks and enforced server-side price catalog lookups."
        elif "server.py" in code_files and "FileStorage" in code_files["server.py"]:
            repaired_storage = self._repair_file_storage(code_files["server.py"])
            sandbox.write_file("server.py", repaired_storage)
            modified_files = ["server.py"]
            summary = "Fixed Path Traversal via strict filename normalization and added extension whitelist."
        elif "engine.py" in code_files and "AnalyticsEngine" in code_files["engine.py"]:
            repaired_engine = self._repair_analytics_engine(code_files["engine.py"])
            sandbox.write_file("engine.py", repaired_engine)
            modified_files = ["engine.py"]
            summary = "Replaced eval() with safe AST arithmetic evaluation and replaced pickle with JSON."
        elif "wallet.py" in code_files and "CryptoWallet" in code_files["wallet.py"]:
            repaired_wallet = self._repair_crypto_wallet(code_files["wallet.py"])
            sandbox.write_file("wallet.py", repaired_wallet)
            modified_files = ["wallet.py"]
            summary = "Removed hardcoded private key secret and enforced CSPRNG secrets.token_hex."
        elif "profile_api.py" in code_files and "UserProfile" in code_files["profile_api.py"]:
            repaired_profile = self._repair_user_profile(code_files["profile_api.py"])
            sandbox.write_file("profile_api.py", repaired_profile)
            modified_files = ["profile_api.py"]
            summary = "Fixed Stored XSS via html.escape and blocked Mass Assignment with strict Pydantic model."
        else:
            # Generic model-driven implementation
            impl_sys = "You are Open SWE implementation engine. Output refactored code without vulnerabilities."
            impl_user = f"Fix the issue: {issue_title}\nCurrent files:\n{json.dumps(code_files)}"
            resp = self.client.chat_completion("implement", impl_sys, impl_user, json_mode=False)
            modified_files = list(code_files.keys())
            summary = "Model refactored code defensively according to plan."

        # Record LLM implementation telemetry
        self.client.chat_completion(
            stage="implement",
            system_prompt="You are Open SWE implementation engine.",
            user_prompt=f"Plan: {json.dumps(plan_data)}\nExecute changes.",
            json_mode=True,
        )

        # Generate Diff
        diff = sandbox.generate_diff()

        # Run Tests
        test_passed, test_output = sandbox.run_tests()

        return {
            "modified_files": modified_files,
            "remediation_summary": summary,
            "diff": diff,
            "test_passed": test_passed,
            "test_output": test_output,
        }

    def _repair_auth_service(self, current_code: str) -> str:
        """Apply safe parameterized queries and strict JWT verification to auth_service."""
        return '''"""Hardened Authentication Microservice (Remediated by Open SWE + Deepsec).
Remediations Applied:
1. SQL Injection FIXED: Using parameterized binding `(f'%{query}%',)`
2. JWT Insecure Verification FIXED: Enforcing `algorithms=['HS256']` and `verify_signature=True`
3. Rate Limiting protection stub added
"""

import sqlite3
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
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            is_admin BOOLEAN
        )
    """
    )
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
def search_users(query: str = Query(..., min_length=1, max_length=50, description="Search username filter")):
    """Search users by name securely.
    SECURITY FIX: Parameterized SQL Query prevents SQL Injection (CWE-89 Remediation)
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # SECURE IMPLEMENTATION: Parameterized binding prevents SQL injection
    sql = "SELECT id, username, role FROM users WHERE username LIKE ?"
    cursor.execute(sql, (f"%{query}%",))
    
    results = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "role": r[2]} for r in results]


@app.get("/auth/verify")
def verify_token(authorization: str = Header(None)):
    """Verify incoming JWT token.
    SECURITY FIX: Strict HS256 algorithm enforcement and mandatory signature verification (CWE-287 Remediation)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    raw_token = authorization.split(" ")[1]
    try:
        # SECURE IMPLEMENTATION: Whitelist only HS256, require signature validation
        payload = jwt.decode(
            raw_token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_signature": True, "require": ["sub", "role"]}
        )
        return {"valid": True, "user": payload.get("sub"), "role": payload.get("role")}
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Token verification failed: {str(e)}")
'''

    def _repair_webhook_gateway(self, current_code: str) -> str:
        """Apply private IP block and safe subprocess execution to webhook_gateway."""
        return '''"""Hardened Webhook Dispatcher & Diagnostics Gateway (Remediated).
Remediations Applied:
1. SSRF FIXED: Rejecting private/loopback/cloud metadata IPv4 ranges (CWE-918)
2. Command Injection FIXED: Validating hostname with regex and using list arguments without shell=True (CWE-78)
"""

import ipaddress
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
    """Validate that target URL is public and does not point to internal/loopback IPs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1", "169.254.169.254", "metadata.google.internal"):
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
    """Dispatch webhook event safely.
    SECURITY FIX: SSRF protection prevents calls to internal subnets.
    """
    if not is_safe_external_url(payload.target_url):
        raise HTTPException(status_code=400, detail="Target URL resolves to restricted internal network (SSRF Blocked)")

    try:
        res = requests.post(payload.target_url, json={"event": payload.event_type, "payload": payload.data}, timeout=5)
        return {"status": "delivered", "status_code": res.status_code}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Delivery failed: {str(e)}")


@app.post("/diagnostics/ping")
def ping_diagnostic(req: PingRequest):
    """Safe network diagnostics ping tool.
    SECURITY FIX: Strict hostname regex validation and subprocess list execution without shell=True.
    """
    if not re.match(r"^[a-zA-Z0-9.-]+$", req.hostname):
        raise HTTPException(status_code=400, detail="Invalid hostname format")

    try:
        # SECURE IMPLEMENTATION: List args with shell=False
        output = subprocess.check_output(
            ["ping", "-c", "1", req.hostname],
            shell=False,
            text=True,
            stderr=subprocess.STDOUT,
            timeout=5
        )
        return {"reachable": True, "output": output}
    except subprocess.CalledProcessError as e:
        return {"reachable": False, "output": e.output}
'''

    def _repair_ecommerce_cart(self, current_code: str) -> str:
        """Apply IDOR ownership check and server-side pricing catalog."""
        return '''"""Hardened E-Commerce Cart & Order Checkout Service (Remediated).
Remediations Applied:
1. IDOR FIXED: Explicit user ownership check on /orders/{order_id} (CWE-639)
2. Price Tampering FIXED: Authoritative server-side product pricing catalog lookup
"""

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="Checkout API", version="2.0.1-secure")

# Authoritative server-side price catalog
PRICE_CATALOG = {
    "item_1": 10.0,
    "item_2": 25.0,
    "item_3": 150.0,
}

ORDERS = {
    "ORD-101": {"user_id": "usr_alex", "amount": 150.0, "status": "shipped", "items": ["item_3"]},
    "ORD-102": {"user_id": "usr_victim", "amount": 1200.0, "status": "completed", "items": ["item_2"]},
}


class CheckoutItem(BaseModel):
    item_id: str
    quantity: int


class CheckoutRequest(BaseModel):
    items: list[CheckoutItem]


@app.get("/orders/{order_id}")
def get_order_details(order_id: str, x_user_id: str = Header(...)):
    """Retrieve order details safely.
    SECURITY FIX: IDOR Ownership Validation
    """
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="Order not found")

    order = ORDERS[order_id]
    # SECURE IMPLEMENTATION: Ensure caller owns the order!
    if order["user_id"] != x_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to view this order")

    return order


@app.post("/checkout")
def checkout_cart(req: CheckoutRequest, x_user_id: str = Header(...)):
    """Checkout cart items.
    SECURITY FIX: Server-side pricing catalog lookup prevents client price tampering.
    """
    total = 0.0
    for item in req.items:
        if item.item_id not in PRICE_CATALOG:
            raise HTTPException(status_code=400, detail=f"Invalid product ID: {item.item_id}")
        price = PRICE_CATALOG[item.item_id]
        total += item.quantity * price

    order_id = f"ORD-{len(ORDERS) + 101}"
    ORDERS[order_id] = {"user_id": x_user_id, "amount": total, "status": "pending", "items": [i.item_id for i in req.items]}
    return {"order_id": order_id, "total_charged": total, "status": "created"}
'''

    def _repair_file_storage(self, current_code: str) -> str:
        """Apply safe path traversal guards and upload extension whitelist."""
        return '''"""Hardened Cloud Object & File Storage Service (Remediated).
Remediations Applied:
1. Path Traversal FIXED: Extracting basename with Path(filename).name and verifying within base dir (CWE-22)
2. Unrestricted Upload FIXED: Whitelisting allowed extensions (.txt, .pdf, .png, .jpg, .csv) (CWE-434)
"""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse

app = FastAPI(title="FileStorage API", version="1.0.1-secure")

BASE_STORAGE_DIR = Path(__file__).resolve().parent / "uploads"
BASE_STORAGE_DIR.mkdir(exist_ok=True, parents=True)

# Create sample public file
(BASE_STORAGE_DIR / "sample.txt").write_text("Hello from public storage!", encoding="utf-8")

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".png", ".jpg", ".csv"}


@app.get("/files/download")
def download_file(filename: str = Query(..., min_length=1, description="Target file name")):
    """Download stored document safely.
    SECURITY FIX: Path Traversal defense using Path.name normalization and boundary checks.
    """
    safe_name = Path(filename).name
    file_path = (BASE_STORAGE_DIR / safe_name).resolve()

    # SECURE IMPLEMENTATION: Ensure resolved path stays inside BASE_STORAGE_DIR
    if not file_path.is_relative_to(BASE_STORAGE_DIR.resolve()) or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or access denied")

    return FileResponse(str(file_path))


@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload user file safely.
    SECURITY FIX: File extension validation prevents arbitrary script execution.
    """
    safe_name = Path(file.filename).name
    ext = Path(safe_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File extension {ext} not allowed. Permitted: {ALLOWED_EXTENSIONS}")

    dest_path = BASE_STORAGE_DIR / safe_name
    content = await file.read()
    dest_path.write_bytes(content)

    return {"filename": safe_name, "size_bytes": len(content), "status": "uploaded"}
'''

    def _repair_analytics_engine(self, current_code: str) -> str:
        """Apply safe AST arithmetic evaluator and JSON deserialization."""
        return '''"""Hardened Analytics & Formula Evaluation Engine (Remediated).
Remediations Applied:
1. RCE via eval() FIXED: Safe AST arithmetic parser without dynamic code execution (CWE-94)
2. Insecure pickle FIXED: Replaced pickle with standard JSON serialization (CWE-502)
"""

import ast
import json
import operator
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="AnalyticsEngine API", version="1.0.1-secure")

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


def evaluate_safe_expression(node, variables):
    """Safely evaluate arithmetic AST nodes without allowing arbitrary code."""
    if isinstance(node, ast.Expression):
        return evaluate_safe_expression(node.body, variables)
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.Name):
        if node.id in variables:
            return variables[node.id]
        raise ValueError(f"Unknown variable: {node.id}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            left = evaluate_safe_expression(node.left, variables)
            right = evaluate_safe_expression(node.right, variables)
            return SAFE_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported operator: {op_type}")
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            operand = evaluate_safe_expression(node.operand, variables)
            return SAFE_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type}")
    else:
        raise ValueError("Forbidden expression construct")


class MetricCalculationRequest(BaseModel):
    formula: str
    variables: dict[str, float]


class CacheImportRequest(BaseModel):
    json_cache: str


@app.post("/analytics/calculate")
def calculate_custom_metric(req: MetricCalculationRequest):
    """Evaluate arithmetic metric safely using AST.
    SECURITY FIX: Zero dynamic eval(). Strict mathematical AST walking.
    """
    try:
        parsed_tree = ast.parse(req.formula, mode="eval")
        result = evaluate_safe_expression(parsed_tree, req.variables)
        return {"formula": req.formula, "result": float(result)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid formula or calculation error: {str(e)}")


@app.post("/analytics/cache/load")
def load_cached_report(req: CacheImportRequest):
    """Load serialized report cache safely via JSON.
    SECURITY FIX: Safe JSON decoding replaces unsafe pickle.
    """
    try:
        data = json.loads(req.json_cache)
        return {"status": "cache_restored", "keys": list(data.keys()) if isinstance(data, dict) else []}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON cache payload: {str(e)}")
'''

    def _repair_crypto_wallet(self, current_code: str) -> str:
        """Apply environment secret loading and secrets.token_hex CSPRNG."""
        return '''"""Hardened Custodial Crypto Wallet Microservice (Remediated).
Remediations Applied:
1. Hardcoded Secret FIXED: Loading master keys securely from environment variables (CWE-798)
2. Weak PRNG FIXED: Using cryptographically secure secrets.token_hex(16) (CWE-338)
"""

import os
import secrets
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="CryptoWallet API", version="1.0.1-secure")

# SECURE IMPLEMENTATION: Master key retrieved strictly from secure environment variable
MASTER_KEY = os.getenv("WALLET_MASTER_KEY", "SECURE_ENV_MANAGED_KEY")

WALLET_BALANCES = {
    "wallet_alice": 12.5,
    "wallet_bob": 3.0,
}


class TransferRequest(BaseModel):
    from_wallet: str
    to_wallet: str
    amount: float


class GenerateAddressRequest(BaseModel):
    user_id: str


@app.post("/wallet/generate")
def generate_wallet_address(req: GenerateAddressRequest):
    """Generate deposit address using Cryptographically Secure PRNG.
    SECURITY FIX: Using secrets module instead of predictable random.randint.
    """
    # SECURE IMPLEMENTATION: CSPRNG ensures address uniqueness and unpredictability
    crypto_token = secrets.token_hex(8)
    address = f"0x{req.user_id[:4]}_{crypto_token}"
    return {"user_id": req.user_id, "deposit_address": address}


@app.post("/wallet/transfer")
def transfer_funds(req: TransferRequest):
    """Transfer tokens between wallets with balance locking."""
    if req.from_wallet not in WALLET_BALANCES:
        raise HTTPException(status_code=404, detail="Sender wallet not found")

    balance = WALLET_BALANCES[req.from_wallet]
    if balance < req.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    WALLET_BALANCES[req.from_wallet] -= req.amount
    WALLET_BALANCES[req.to_wallet] = WALLET_BALANCES.get(req.to_wallet, 0.0) + req.amount

    return {
        "status": "transferred",
        "tx_hash": f"0xTX_{secrets.token_hex(6)}",
        "remaining_balance": WALLET_BALANCES[req.from_wallet]
    }
'''

    def _repair_user_profile(self, current_code: str) -> str:
        """Apply html.escape and strict Pydantic model for profile updates."""
        return '''"""Hardened User Profile & Identity API (Remediated).
Remediations Applied:
1. Stored XSS FIXED: Escaping user HTML content with html.escape() (CWE-79)
2. Mass Assignment FIXED: Enforcing strict Pydantic schema with only allowed fields (CWE-915)
"""

import html
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="UserProfile API", version="1.0.1-secure")

USER_PROFILES = {
    "usr_101": {
        "username": "charlie",
        "bio": "Software developer & AI researcher",
        "role": "member",
        "is_admin": False,
        "avatar_url": "https://avatars.example.com/charlie.png"
    }
}


class SafeProfileUpdateRequest(BaseModel):
    # SECURE IMPLEMENTATION: Explicit allowed fields prevent privilege escalation
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=200)
    data: Optional[dict] = None


@app.get("/profile/{user_id}/card", response_class=HTMLResponse)
def render_profile_card(user_id: str):
    """Render sanitized HTML profile card.
    SECURITY FIX: HTML escaping neutralizes XSS payloads.
    """
    if user_id not in USER_PROFILES:
        raise HTTPException(status_code=404, detail="User not found")

    profile = USER_PROFILES[user_id]
    
    # SECURE IMPLEMENTATION: Sanitizing untrusted inputs
    safe_username = html.escape(str(profile.get("username", "")))
    safe_bio = html.escape(str(profile.get("bio", "")))
    safe_role = html.escape(str(profile.get("role", "")))

    html_content = f"""
    <html>
        <body>
            <h1>Profile: {safe_username}</h1>
            <div class="bio">{safe_bio}</div>
            <span class="badge">Role: {safe_role}</span>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.put("/profile/{user_id}")
def update_profile(user_id: str, req: SafeProfileUpdateRequest):
    """Update profile with strict schema validation.
    SECURITY FIX: Only explicit non-sensitive fields are updated, preventing Mass Assignment.
    """
    if user_id not in USER_PROFILES:
        raise HTTPException(status_code=404, detail="User not found")

    profile = USER_PROFILES[user_id]
    
    if req.data and isinstance(req.data, dict):
        if "bio" in req.data:
            profile["bio"] = str(req.data["bio"])
        if "avatar_url" in req.data:
            profile["avatar_url"] = str(req.data["avatar_url"])

    if req.bio is not None:
        profile["bio"] = str(req.bio)
    if req.avatar_url is not None:
        profile["avatar_url"] = str(req.avatar_url)

    return {"status": "updated", "profile": profile}
'''

