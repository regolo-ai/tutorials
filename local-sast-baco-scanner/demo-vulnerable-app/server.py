"""
Vulnerable Demo Server — Target for BACO Security Scanner testing.
Demonstrates common security flaws (CWE-89, CWE-78, CWE-22, CWE-798).
"""

import os
import sqlite3
import subprocess

# CWE-798: Hardcoded Sensitive Credential
ADMIN_SECRET_KEY = "super_secret_production_admin_token_2026"
DATABASE_PATH = "demo.db"


def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT,
            email TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO users VALUES (1, 'admin', 'admin123', 'admin@example.com')")
    conn.commit()
    conn.close()


def authenticate_user(username: str, password_input: str):
    """
    CWE-89: SQL Injection Vulnerability
    User-supplied input is formatted directly into the SQL query string.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # VULNERABLE: Direct string formatting into raw SQL
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password_input}'"
    cursor.execute(query)
    user = cursor.fetchone()
    conn.close()
    return user


def ping_host(target_host: str):
    """
    CWE-78: Command Injection Vulnerability
    User-controlled host parameter passed directly to shell command.
    """
    # VULNERABLE: shell=True with unvalidated string concatenation
    command = f"ping -c 1 {target_host}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout


def read_user_file(file_name: str):
    """
    CWE-22: Path Traversal Vulnerability
    User-supplied file name allows accessing arbitrary system files via '../'.
    """
    base_dir = "/var/data/uploads"

    # VULNERABLE: Direct concatenation without resolving canonical path
    target_path = os.path.join(base_dir, file_name)
    with open(target_path, "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    init_db()
    print("Demo application initialized.")
