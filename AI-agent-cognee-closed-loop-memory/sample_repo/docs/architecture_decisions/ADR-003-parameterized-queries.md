# ADR-003: Mandatory Parameterized SQLAlchemy Core Queries

## Status
APPROVED (2026-07-20)

## Context
A critical vulnerability (CWE-89) was discovered in the user search filter where raw Python f-strings formatted user input into SQLite/Postgres query strings, causing CI Run #89 to fail.

## Decision
1. Never use raw string formatting (`f"SELECT ... {param}"` or `.format()`) inside any database query.
2. All database queries must use SQLAlchemy Core expressions (`select()`, `where()`, `and_()`) with automatic parameter binding.
3. PRs attempting to merge unparameterized SQL queries will be rejected by CI and Deepsec security gates.

## Related
- Fixed in: PR #142
- Regression Test: `tests/test_auth.py::test_tenant_search_isolation`
