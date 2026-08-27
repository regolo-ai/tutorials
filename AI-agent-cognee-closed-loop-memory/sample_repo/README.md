# CloudPlatform SaaS Core Repository
Multi-tenant enterprise SaaS platform with microservices for authentication, subscription billing, and real-time data ingestion.

## Architecture
- **Framework**: FastAPI (Async-First)
- **Database**: PostgreSQL 16 + SQLAlchemy Core ORM
- **Isolation**: Tenant Context Session (ADR-001)
- **Security**: Mandatory Parameterized Queries (ADR-003) & PyJWT Algorithm Whitelisting (CONV-02)

## Directory Structure
- `src/api/`: REST Endpoints (Auth, Billing, Search)
- `src/db/`: Models & Database connections
- `src/services/`: Tenant and Payment services
- `docs/architecture_decisions/`: ADRs governing repository evolution
- `docs/conventions/`: Team coding standards
- `docs/runbooks/`: Incident response & CI triage
- `.history/`: Longitudinal records of past CI failures, PRs, and resolved CVEs
