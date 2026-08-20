# User Profile & Identity Service

FastAPI service for public profile card rendering and account profile updates.

## Current Open Issue #33:
- **Title**: `Security Vulnerability: Prevent Stored XSS in /profile/{id}/card and block Mass Assignment on /profile/{id}`
- **Description**: Stored XSS (CWE-79) was discovered because user bio HTML is rendered raw without sanitization. In addition, `/profile/{id}` accepts unconstrained dictionary input, allowing attackers to overwrite `is_admin=True` and `role="admin"` (Mass Assignment CWE-915).
- **Target**: Escape all user content with `html.escape()` and define a strict Pydantic model with allowed fields (`bio`, `avatar_url`) to block unauthorized privilege elevation.
