"""Unit tests for Deepsec Security Harness and AST SAST scanner."""

import pytest
from unittest.mock import MagicMock
import config
from core.deepsec import ASTSecurityScanner, DeepsecSecurityHarness
from core.sandbox import SandboxEnvironment


def test_ast_scanner_vulnerabilities():
    vulnerable_code = """
import sqlite3
import jwt
import subprocess
import pickle
import random

DATABASE = "test.db"
MASTER_PRIVATE_KEY = "0x1234567890abcdef1234567890abcdef"

def unsafe_operations(user_input, token, data):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # SQLi
    cursor.execute(f"SELECT * FROM users WHERE username = '{user_input}'")
    
    # JWT bypass
    jwt.decode(token, "secret", algorithms=["none"], options={"verify_signature": False})
    
    # Command injection
    subprocess.run(f"ping -c 1 {user_input}", shell=True)
    
    # Insecure deserialization
    pickle.loads(data)
    
    # eval RCE
    eval(user_input)
    
    # Weak random for key
    key = random.randint(1000, 9999)
    return key
"""
    scanner = ASTSecurityScanner(filename="test_vuln.py", source_code=vulnerable_code)
    findings = scanner.scan()

    cwes = [f["cwe"] for f in findings]
    assert "CWE-89" in cwes  # SQLi
    assert "CWE-287" in cwes  # JWT
    assert "CWE-78" in cwes  # Command Injection
    assert "CWE-502" in cwes  # Pickle
    assert "CWE-94" in cwes  # Eval RCE
    assert "CWE-798" in cwes  # Hardcoded key
    assert "CWE-338" in cwes  # Weak PRNG


def test_deepsec_scan_and_revalidate():
    auth_repo = config.SAMPLE_REPOS_DIR / "auth_service"
    sandbox = SandboxEnvironment(source_repo_path=str(auth_repo))

    mock_client = MagicMock()
    mock_client.evaluate_complexity.return_value = {
        "complexity_score": 7.5,
        "recommended_tier": "REASONING",
        "recommended_model": "qwen3.5-122b",
        "routing_reasoning": "High security audit complexity",
    }
    mock_client.chat_completion.return_value = {
        "content": '{"findings": [{"id": "SEC-001", "severity": "CRITICAL", "cwe": "CWE-89", "title": "SQL Injection", "file": "app.py", "line": 64, "status": "VULNERABLE"}], "security_score": 38, "gate_status": "FAILED_VULNERABILITIES_PRESENT"}',
        "prompt_tokens": 200,
        "completion_tokens": 100,
        "latency_sec": 0.2,
    }
    mock_client.parse_json_response.side_effect = lambda t: {
        "findings": [{"id": "SEC-001", "severity": "CRITICAL", "cwe": "CWE-89", "title": "SQL Injection", "file": "app.py", "line": 64, "status": "VULNERABLE"}],
        "security_score": 38,
        "gate_status": "FAILED_VULNERABILITIES_PRESENT",
    }

    deepsec = DeepsecSecurityHarness(client=mock_client)

    try:
        # Initial scan on vulnerable repo
        scan = deepsec.run_security_scan(sandbox)
        assert len(scan["findings"]) >= 1
        assert any(f["cwe"] == "CWE-89" for f in scan["findings"])
        assert scan["security_score"] < 70

        # Now simulate fixed file with parameterized queries
        secure_code = """
import sqlite3
try:
    import jwt
except ImportError:
    from jose import jwt
from fastapi import FastAPI, HTTPException, Header, Query
from pydantic import BaseModel

app = FastAPI()
DATABASE = "users.db"

@app.get("/users/search")
def search_users(query: str = Query(...)):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role FROM users WHERE username LIKE ?", (f"%{query}%",))
    results = cursor.fetchall()
    conn.close()
    return results

@app.get("/auth/verify")
def verify_token(authorization: str = Header(None)):
    payload = jwt.decode("token", "secret", algorithms=["HS256"], options={"verify_signature": True})
    return payload
"""
        sandbox.write_file("app.py", secure_code)

        # Revalidation
        mock_client.parse_json_response.side_effect = lambda t: {
            "findings": [],
            "security_score": 98,
            "gate_status": "PASSED_CLEAN_SECURITY_GATE",
            "evidence": "Deepsec re-scan confirmed all vulnerabilities resolved.",
        }
        reval = deepsec.revalidate_patch(sandbox, scan["findings"])
        assert reval["revalidation_passed"] is True
        assert len(reval["residual_findings"]) == 0
        assert reval["security_score"] >= 90
    finally:
        sandbox.cleanup()
