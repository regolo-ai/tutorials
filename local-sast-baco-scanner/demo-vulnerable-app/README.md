# Vulnerable Demo Target for BACO Scanner

This directory contains intentionally vulnerable code designed to test and showcase
**BACO Security Scanner** and **Regolo.ai AI Remediation**.

---

## Vulnerabilities Included

| File | Function / Line | CWE | Description |
|---|---|---|---|
| `server.py` | `authenticate_user()` | **CWE-89** | SQL Injection via raw string formatting in SQL queries |
| `server.py` | `ping_host()` | **CWE-78** | Command Injection via `subprocess.run(..., shell=True)` |
| `server.py` | `read_user_file()` | **CWE-22** | Path Traversal via unvalidated `os.path.join` |
| `server.py` | Top-level constant | **CWE-798** | Hardcoded Sensitive Credential (`ADMIN_SECRET_KEY`) |
| `utils.py` | `load_user_session()` | **CWE-502** | Insecure Deserialization via `pickle.loads` |
| `utils.py` | `hash_password()` | **CWE-327** | Weak Cryptographic Hash (MD5 for passwords) |

---

## How to Test with BACO Scanner

1. Launch the TUI:
   ```bash
   ./launch.sh
   ```
2. Select **[2] Scan Repository & View Findings + Cost**.
3. When prompted for the target path, enter:
   ```text
   demo-vulnerable-app
   ```
4. Observe:
   - Semgrep and Regolo LLM detecting the vulnerabilities.
   - The executive summary card displaying findings classified by severity.
   - The scan cost calculated in **EUR (€)** via **Brick Complexity Pro**.
5. Select **[3] Generate AI Fixes for Vulnerabilities** to automatically produce
   unified `.patch` files and LLM instructions using Regolo.ai.
