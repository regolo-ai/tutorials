import asyncio
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _cwd_and_key(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("FRAUDCLEF_HMAC_KEY", "test-key")


def run(coro):
    return asyncio.run(coro)
