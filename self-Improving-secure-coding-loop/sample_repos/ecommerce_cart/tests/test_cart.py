import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from cart import app

client = TestClient(app)

def test_checkout_flow():
    response = client.post(
        "/checkout",
        json={"items": [{"item_id": "item_1", "quantity": 2, "unit_price": 10.0}]},
        headers={"x-user-id": "usr_alex"}
    )
    assert response.status_code == 200
    assert response.json()["total_charged"] == 20.0
