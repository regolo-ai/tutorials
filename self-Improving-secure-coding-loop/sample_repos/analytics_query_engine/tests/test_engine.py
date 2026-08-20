import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from engine import app

client = TestClient(app)

def test_calculate_simple_formula():
    response = client.post(
        "/analytics/calculate",
        json={"formula": "revenue - cost", "variables": {"revenue": 100.0, "cost": 40.0}}
    )
    assert response.status_code == 200
    assert response.json()["result"] == 60.0
