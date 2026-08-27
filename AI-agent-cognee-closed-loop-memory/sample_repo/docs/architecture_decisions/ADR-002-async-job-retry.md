# ADR-002: Idempotent Webhook Processing & Async Retries

## Status
APPROVED (2026-07-02)

## Context
Payment providers (Stripe, SEPA) send duplicate webhook events during network retransmissions. Processing payments multiple times caused ledger inconsistencies and duplicate user invoice generation.

## Decision
1. All external webhook consumers must store incoming idempotency event IDs in Redis with a 72-hour TTL.
2. Background task handlers must be decorated with `@idempotent_task`.
3. Failed jobs must use exponential backoff with dead-letter queue escalation.
