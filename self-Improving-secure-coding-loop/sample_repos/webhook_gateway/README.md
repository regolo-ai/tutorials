# Webhook & Network Gateway

Microservice for managing outgoing webhooks and network diagnostics.

## Current Open Issue #42:
- **Title**: `Security Fix: Prevent SSRF in Webhook delivery and eliminate Command Injection in Ping endpoint`
- **Description**: Security team reported SSRF (CWE-918) in `/dispatch` allowing callers to reach internal IP ranges (127.0.0.1, 169.254.169.254). Also `/diagnostics/ping` executes shell commands with user-controlled input (CWE-78 Command Injection).
- **Target**: Add private IP blocking / URL validation and replace shell command with safe subprocess list arguments and regex hostname validation.
