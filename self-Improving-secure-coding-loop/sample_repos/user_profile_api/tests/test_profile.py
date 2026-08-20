import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from profile_api import app

client = TestClient(app)

def test_render_profile():
    response = client.get("/profile/usr_101/card")
    assert response.status_code == 200
    assert "charlie" in response.text

def test_update_profile_basic():
    response = client.put("/profile/usr_101", json={"data": {"bio": "Updated bio text"}})
    assert response.status_code == 200
    assert response.json()["profile"]["bio"] == "Updated bio text"
