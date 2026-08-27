# Repository Coding Standards

## 1. Async-First FastAPI Architecture
- All API route handlers must be defined as `async def`.
- Database I/O must use `AsyncSession` with `await session.execute(...)`.

## 2. Input Validation & Strict Typing
- Every endpoint payload must be typed using Pydantic V2 `BaseModel`.
- Type annotations (`mypy` strict) are required for all function arguments and returns.

## 3. JWT & Security
- Strict algorithm whitelisting: `jwt.decode(..., algorithms=['HS256'], options={'verify_signature': True})`.
- Never disable signature verification in production or test helpers.
