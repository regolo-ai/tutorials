"""Unit tests for Deepsec Security Harness."""

import config
from core.deepsec import DeepsecSecurityHarness
from core.sandbox import SandboxEnvironment


def test_deepsec_scan_and_revalidate():
    auth_repo = config.SAMPLE_REPOS_DIR / "auth_service"
    sandbox = SandboxEnvironment(source_repo_path=str(auth_repo))
    deepsec = DeepsecSecurityHarness()

    try:
        # Initial scan on vulnerable repo
        scan = deepsec.run_security_scan(sandbox)
        assert len(scan["findings"]) >= 1
        assert any(f["cwe"] == "CWE-89" for f in scan["findings"])
        assert scan["security_score"] < 70

        # Now simulate fixed file
        secure_code = """
import sqlite3
import jwt
from fastapi import FastAPI
app = FastAPI()
DATABASE = "users.db"
@app.get("/users/search")
def search_users(query: str):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE username LIKE ?", (f"%{query}%",))
    return cursor.fetchall()
"""
        sandbox.write_file("app.py", secure_code)

        # Revalidation
        reval = deepsec.revalidate_patch(sandbox, scan["findings"])
        assert reval["revalidation_passed"] is True
        assert len(reval["residual_findings"]) == 0
        assert reval["security_score"] >= 90
    finally:
        sandbox.cleanup()
