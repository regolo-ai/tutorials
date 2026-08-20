# E-Commerce Cart & Checkout Service

FastAPI service for shopping cart calculation and order viewing.

## Current Open Issue #77:
- **Title**: `Fix IDOR in /orders/{order_id} and enforce server-side price validation on /checkout`
- **Description**: Security review uncovered IDOR (CWE-639) allowing unauthorized users to view arbitrary customer orders without ownership validation. In addition, the checkout endpoint trusts client-sent unit prices.
- **Target**: Ensure `order["user_id"] == x_user_id` before returning details, and lookup unit prices from an authoritative catalog dictionary.
