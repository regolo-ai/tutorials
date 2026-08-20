import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from wallet import app

client = TestClient(app)

def test_generate_address():
    response = client.post("/wallet/generate", json={"user_id": "alice_123"})
    assert response.status_code == 200
    assert "deposit_address" in response.json()

def test_transfer_success():
    response = client.post(
        "/wallet/transfer",
        json={"from_wallet": "wallet_alice", "to_wallet": "wallet_bob", "amount": 1.0}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "transferred"
