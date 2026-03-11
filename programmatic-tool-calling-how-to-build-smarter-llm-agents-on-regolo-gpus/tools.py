"""Demo business tools used by classic and programmatic agents."""

from __future__ import annotations


def get_user_orders(user_id: str, limit: int = 10) -> list[dict[str, float | str]]:
    catalog = [
        {"id": "order_123", "user_id": "user_789", "total": 42.5},
        {"id": "order_456", "user_id": "user_789", "total": 19.9},
        {"id": "order_457", "user_id": "user_789", "total": 109.0},
        {"id": "order_811", "user_id": "user_001", "total": 12.0},
    ]
    safe_limit = int(limit) if str(limit).strip().isdigit() else 10
    filtered = [o for o in catalog if o["user_id"] == user_id]
    return filtered[:safe_limit]


def filter_by_min_total(orders: list[dict[str, float | str]], min_total: float) -> list[dict[str, float | str]]:
    return [o for o in orders if float(o["total"]) >= min_total]


def summarize_orders(orders: list[dict[str, float | str]]) -> dict[str, float | int]:
    return {
        "count": len(orders),
        "total_amount": round(sum(float(o["total"]) for o in orders), 2),
    }


def search_knowledge_base(query: str) -> list[dict[str, str]]:
    docs = [
        {
            "title": "Refund policy",
            "content": "Refunds above EUR 100 must be approved by support lead.",
        },
        {
            "title": "Escalation policy",
            "content": "Escalate to human when customer asks legal/compliance exceptions.",
        },
        {
            "title": "SLA",
            "content": "Priority tickets should receive first response in under 30 minutes.",
        },
    ]
    q = query.lower()
    return [d for d in docs if any(word in d["content"].lower() for word in q.split())] or docs[:1]


def escalate_to_human(ticket_id: str, summary: str) -> dict[str, str]:
    return {"status": "created", "ticket_id": ticket_id, "summary": summary}
