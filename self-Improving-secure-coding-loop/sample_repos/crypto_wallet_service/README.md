# Custodial Crypto Wallet Microservice

Service managing address generation and custodial asset transfers.

## Current Open Issue #91:
- **Title**: `Security Remediation: Remove hardcoded private key secrets and enforce CSPRNG for address generation`
- **Description**: Security review flagged a hardcoded master private key in the codebase (CWE-798) and identified that `/wallet/generate` uses Python's standard `random` module rather than a cryptographically secure pseudo-random number generator (CWE-338).
- **Target**: Load private keys strictly from environment variables or vault, and replace `random` with `secrets.token_hex(16)`.
