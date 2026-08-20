import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from app import app, init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_login_success():
    response = client.post("/login", json={"username": "admin", "password": "pbkdf2:admin123"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_failure():
    response = client.post("/login", json={"username": "admin", "password": "wrongpassword"})
    assert response.status_code == 401

def test_search_users():
    response = client.get("/users/search?query=dev")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["username"] == "developer"
