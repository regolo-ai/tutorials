import stat

import pytest
from fastapi.testclient import TestClient

from app import account, main

api = TestClient(main.app)
HEADER = {"X-RRC": "1"}


class Resp:
    def __init__(self, code):
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_hint_never_shows_the_whole_key():
    assert account.hint("sk-abcdef123456") == "····3456"
    assert account.hint("") is None and account.hint("replace_me") is None


def test_save_requires_the_custom_header():
    assert api.post("/api/account/key", json={"key": "whatever-key-1"}).status_code == 403


def test_a_rejected_key_is_not_saved(monkeypatch):
    monkeypatch.setattr(account.requests.Session, "get", lambda self, *a, **k: Resp(401))
    before = account.status()
    response = api.post("/api/account/key", json={"key": "bad-key-0000"}, headers=HEADER)
    assert response.status_code == 400 and "did not accept" in response.json()["detail"]
    assert account.status() == before


def test_a_valid_key_is_saved_with_owner_only_permissions(monkeypatch):
    monkeypatch.setattr(account.requests.Session, "get", lambda self, *a, **k: Resp(200))
    response = api.post("/api/account/key", json={"key": "good-key-WXYZ"}, headers=HEADER)
    assert response.status_code == 200 and response.json() == {"key_set": True, "key_hint": "····WXYZ", "stored_in": ".env on this computer"}
    assert "good-key-WXYZ" in account.env_path().read_text()
    assert stat.S_IMODE(account.env_path().stat().st_mode) == 0o600
    assert "good-key-WXYZ" not in api.get("/api/account").text and "good-key-WXYZ" not in api.get("/api/health").text
    assert main.client.settings.regolo_api_key == "good-key-WXYZ"


@pytest.mark.parametrize("key", ["", "short", "has space inside"])
def test_malformed_keys_are_refused_before_any_request(key):
    assert api.post("/api/account/key", json={"key": key}, headers=HEADER).status_code == 400
