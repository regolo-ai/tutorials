import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_download_legitimate_file():
    response = client.get("/files/download?filename=sample.txt")
    assert response.status_code == 200
    assert "Hello from public storage!" in response.text

def test_upload_file():
    response = client.post(
        "/files/upload",
        files={"file": ("test_doc.txt", b"Document content here", "text/plain")}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "uploaded"
