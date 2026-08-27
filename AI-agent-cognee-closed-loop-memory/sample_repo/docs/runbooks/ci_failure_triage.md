# CI Failure Triage Runbook

## Protocol for Failing Builds
1. Inspect failing test node in `tests/`.
2. Check if the failure is related to a known architectural constraint (`ADR-001` or `ADR-003`).
3. Query Cognee Memory Graph to identify similar past PRs (`PR-142`).
4. Re-run security test harness before staging merge requests.
