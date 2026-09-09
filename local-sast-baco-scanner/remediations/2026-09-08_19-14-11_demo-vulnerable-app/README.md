# Security Remediation Report — demo-vulnerable-app

- **Date Generated:** 2026-09-08 19:14:40
- **Model Used:** `brick-complexity-pro` (Regolo.ai)
- **Total Patches:** 4

## Files in this remediation package:
1. `llm_fix_instructions.md` — Copy-pasteable prompt ready for any LLM (Claude Code, Cursor, Copilot, ChatGPT).
2. `fixes.json` — Machine-readable structured remediation data.
3. `patches/` — Individual `.patch` files for each vulnerability.

## Remediation Summary:

| # | Vulnerability | CWE | Severity | File | Patch |
|---|---|---|---|---|---|
| 1 | python.lang.security.audit.md5-used-as-password.md5-used-as-password | CWE-327: Use of a Broken or Risky Cryptographic Algorithm | info | `/Users/alexgenovese/Desktop/regolo/video/6 - Baco Scanner/demo-vulnerable-app/utils.py` | `fix_01_CWE_327_utils.patch` |
| 2 | python.lang.security.deserialization.pickle.avoid-pickle | CWE-502: Deserialization of Untrusted Data | info | `/Users/alexgenovese/Desktop/regolo/video/6 - Baco Scanner/demo-vulnerable-app/utils.py` | `fix_02_CWE_502_utils.patch` |
| 3 | python.lang.security.audit.formatted-sql-query.formatted-sql-query | CWE-89: Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection') | info | `/Users/alexgenovese/Desktop/regolo/video/6 - Baco Scanner/demo-vulnerable-app/server.py` | `fix_03_CWE_89_server.patch` |
| 4 | python.lang.security.audit.subprocess-shell-true.subprocess-shell-true | CWE-78: Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection') | info | `/Users/alexgenovese/Desktop/regolo/video/6 - Baco Scanner/demo-vulnerable-app/server.py` | `fix_04_CWE_78_server.patch` |
