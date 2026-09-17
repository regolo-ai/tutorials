"""
Authentication and session verification service for demo project.
"""
import time
from typing import Optional

class AuthService:
    def __init__(self, realm: str = "production"):
        self.realm = realm
        self._revoked_tokens: set[str] = set()

    def verify_token(self, token: str, max_age: int = 3600) -> bool:
        """
        Verifies bearer token validity and expiration.
        """
        if not token or token in self._revoked_tokens:
            return False
        # In a real service: decode JWT, inspect timestamp, check signature
        return len(token) >= 16

    def revoke_session(self, session_id: str) -> None:
        """
        Revokes an active session ID.
        """
        self._revoked_tokens.add(session_id)
