import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from service import app

client = TestClient(app)

def test_ping_validation():
    response = client.post("/diagnostics/ping", json={"hostname": "127.0.0.1"})
    assert response.status_code == 200
