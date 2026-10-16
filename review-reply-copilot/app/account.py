"""Save and verify the Regolo API key from the interface.

The key is checked against the authenticated catalog (no inference is run), then written to the
local .env file with owner-only permissions. It is never sent back to the browser, only a hint with
its last four characters. The app listens on localhost, and the write endpoint also requires a
custom header so that a page on another site cannot call it.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import set_key

from app.config import ROOT, get_settings


class KeyError_(ValueError):
    """The key was empty, malformed or rejected by Regolo."""


def env_path() -> Path:
    return Path(os.getenv("ENV_FILE", ROOT / ".env"))


def hint(key: str) -> str | None:
    key = (key or "").strip()
    if not key or key == "replace_me":
        return None
    return "····" + key[-4:]


def status() -> dict:
    key = get_settings().regolo_api_key
    return {"key_set": hint(key) is not None, "key_hint": hint(key), "stored_in": ".env on this computer"}


def verify(key: str, session: requests.Session | None = None) -> None:
    """Raises KeyError_ unless Regolo accepts the key. Uses the catalog, which runs no inference."""
    if not key or len(key) < 8 or any(c.isspace() for c in key):
        raise KeyError_("This does not look like a Regolo API key. Paste the whole key, without spaces.")
    http = session or requests.Session()
    response = http.get(f"{get_settings().regolo_admin_url}/model_group/info", headers={"Authorization": f"Bearer {key}"}, timeout=20)
    if response.status_code in (401, 403):
        raise KeyError_("Regolo did not accept this key. Check it in your dashboard and try again.")
    response.raise_for_status()


def save(key: str) -> None:
    path = env_path()
    if not path.exists():
        example = ROOT / ".env.example"
        path.write_text(example.read_text() if example.exists() else "")
    set_key(str(path), "REGOLO_API_KEY", key, quote_mode="never")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    os.environ["REGOLO_API_KEY"] = key
