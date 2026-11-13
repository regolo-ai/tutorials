"""Pseudonymisation of personal data before it leaves the process (model call, audit log)."""

from __future__ import annotations

import copy
import hashlib
import hmac
import os
import warnings
from typing import Any

_DEV_KEY = "fraudclef-dev-only"


class Pseudonymizer:
    """Keyed HMAC-SHA256: equal inputs map to equal tokens, so "is this IBAN new?" still works
    downstream, but the raw value cannot be recovered without the key."""

    def __init__(self, key: str | None = None):
        key = key or os.environ.get("FRAUDCLEF_HMAC_KEY")
        if not key or key == "change-me":
            warnings.warn("FRAUDCLEF_HMAC_KEY not set: using an insecure development key", stacklevel=2)
            key = _DEV_KEY
        self._key = key.encode()

    def token(self, value: str) -> str:
        digest = hmac.new(self._key, value.encode(), hashlib.sha256).hexdigest()
        return f"h:{digest[:16]}"

    def apply(self, data: dict[str, Any], pseudonymize: list[str], drop: list[str]) -> dict[str, Any]:
        """Return a deep copy of a transaction/customer dict with dotted paths hashed or removed."""
        out = copy.deepcopy(data)
        for path in pseudonymize:
            _transform(out, path.split("."), lambda v: self.token(str(v)) if v is not None else None)
        for path in drop:
            _transform(out, path.split("."), None)
        return out


def _transform(node: Any, parts: list[str], fn) -> None:
    if not isinstance(node, dict) or parts[0] not in node:
        return
    if len(parts) == 1:
        if fn is None:
            del node[parts[0]]
        else:
            node[parts[0]] = fn(node[parts[0]])
    else:
        _transform(node[parts[0]], parts[1:], fn)
