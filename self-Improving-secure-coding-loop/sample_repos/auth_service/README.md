# Auth Service Microservice

FastAPI-based Authentication and User Management microservice.

## Current Open Issue #104:
- **Title**: `Security Audit: Fix SQL Injection in /users/search and enforce strict JWT signature verification`
- **Description**: Security report identified that `/users/search` uses unsanitized SQL string formatting which is vulnerable to SQL injection (CWE-89). Furthermore, `/auth/verify` disables signature verification and accepts the `none` algorithm, leading to full authentication bypass (CWE-287).
- **Target**: Sanitize queries using parameterized SQL and enforce `algorithms=["HS256"]` with `verify_signature=True`.
