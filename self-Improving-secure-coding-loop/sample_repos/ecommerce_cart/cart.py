"""E-Commerce Cart & Order Checkout Service.
Contains:
1. Insecure Direct Object Reference (IDOR - CWE-639) in order viewing
2. Client-Controlled Price Tampering vulnerability in checkout
"""

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="Checkout API", version="2.0.0")

# Mock database
ORDERS = {
    "ORD-101": {"user_id": "usr_alex", "amount": 150.0, "status": "shipped", "items": ["Mechanical Keyboard"]},
    "ORD-102": {"user_id": "usr_victim", "amount": 1200.0, "status": "completed", "items": ["MacBook Pro"]},
}


class CheckoutItem(BaseModel):
    item_id: str
    quantity: int
    unit_price: float  # VULNERABLE: Client sends the unit price!


class CheckoutRequest(BaseModel):
    items: list[CheckoutItem]


@app.get("/orders/{order_id}")
def get_order_details(order_id: str, x_user_id: str = Header(None)):
    """Retrieve order details.
    HIGH SECURITY VULNERABILITY: IDOR (CWE-639) - No check verifying that x_user_id owns order_id!
    """
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="Order not found")

    order = ORDERS[order_id]
    # VULNERABLE CODE: Returns order data regardless of who makes the request!
    return order


@app.post("/checkout")
def checkout_cart(req: CheckoutRequest, x_user_id: str = Header(...)):
    """Checkout cart items.
    HIGH SECURITY VULNERABILITY: Trusting client-supplied prices instead of server-side catalog lookup.
    """
    total = 0.0
    for item in req.items:
        # VULNERABLE CODE: trusts item.unit_price from payload
        total += item.quantity * item.unit_price

    order_id = f"ORD-{len(ORDERS) + 101}"
    ORDERS[order_id] = {"user_id": x_user_id, "amount": total, "status": "pending", "items": [i.item_id for i in req.items]}
    return {"order_id": order_id, "total_charged": total, "status": "created"}
