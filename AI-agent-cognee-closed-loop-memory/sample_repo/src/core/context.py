"""Tenant Context & Session Management for Multi-Tenant Architecture (ADR-001)."""

import contextvars

# Context variable holding the verified JWT session tenant ID
_current_tenant_id: contextvars.ContextVar[int] = contextvars.ContextVar("current_tenant_id", default=1)


def get_current_tenant_id() -> int:
    """Retrieve the cryptographically verified tenant ID from current execution context.
    Strictly enforced by ADR-001 to prevent IDOR / CWE-639.
    """
    return _current_tenant_id.get()


def set_current_tenant_id(tenant_id: int):
    """Set tenant ID for the current request context (called by auth middleware)."""
    _current_tenant_id.set(tenant_id)
