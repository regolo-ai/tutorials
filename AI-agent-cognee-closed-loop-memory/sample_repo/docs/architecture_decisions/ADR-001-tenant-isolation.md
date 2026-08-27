# ADR-001: Tenant Isolation via Explicit Context Session

## Status
APPROVED (2026-06-15)

## Context
Our SaaS platform serves multi-tenant enterprise customers sharing the same underlying database clusters. Passing `tenant_id` via HTTP request payloads or URL parameters created severe IDOR risks (CWE-639) and allowed users to query data from competitor organizations.

## Decision
1. All database and service queries must obtain `tenant_id` exclusively from the cryptographically verified JWT session context (`core.context.get_current_tenant_id()`).
2. Endpoints are forbidden from accepting `tenant_id` as a client-controlled URL parameter or request body field.
3. Database queries must enforce row-level security or explicit `User.tenant_id == get_current_tenant_id()` filter.

## Consequences
- Prevents cross-tenant data leaks.
- Requires all coding agents to use session context helpers instead of method arguments.
