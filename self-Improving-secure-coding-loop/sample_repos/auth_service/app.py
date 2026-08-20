"""Vulnerable Authentication Microservice (Demo Target for Open SWE + Deepsec).
Contains:
1. SQL Injection in `/users/search`
2. JWT Insecure Verification / Algorithm Confusion in `/auth/verify`
3. Missing Rate Limiting on `/login`
"""

import sqlite3
try:
    import jwt
except ImportError:
    from jose import jwt
from fastapi import FastAPI, HTTPException, Header, Query
from pydantic import BaseModel

app = FastAPI(title="AuthService API", version="1.0.0")

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
    # Vulnerability: No rate limiting, simple auth
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
def search_users(query: str = Query(..., description="Search username filter")):
    """Search users by name.
    CRITICAL SECURITY VULNERABILITY: Raw SQL String Formatting (CWE-89 SQL Injection)
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # VULNERABLE CODE: Direct string interpolation into SQL query!
    sql = f"SELECT id, username, role FROM users WHERE username LIKE '%{query}%'"
    cursor.execute(sql)
    
    results = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "role": r[2]} for r in results]


@app.get("/auth/verify")
def verify_token(authorization: str = Header(None)):
    """Verify incoming JWT token.
    HIGH SECURITY VULNERABILITY: Insecure algorithm whitelist allows 'none' algorithm (CWE-327 / CWE-287)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    raw_token = authorization.split(" ")[1]
    try:
        # VULNERABLE CODE: accepts 'none' algorithm and lacks strict validation
        payload = jwt.decode(
            raw_token,
            JWT_SECRET,
            algorithms=["HS256", "none", "RS256"],
            options={"verify_signature": False}  # VULNERABILITY: signature verification bypassed!
        )
        return {"valid": True, "user": payload.get("sub"), "role": payload.get("role")}
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Token verification failed: {str(e)}")
