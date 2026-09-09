"""
Helper Utilities — Target for BACO Security Scanner testing.
Demonstrates CWE-502 (Insecure Deserialization) and CWE-327 (Weak Cryptography).
"""

import base64
import hashlib
import pickle


def hash_password(plain_password: str) -> str:
    """
    CWE-327: Use of a Broken or Risky Cryptographic Algorithm
    MD5 is cryptographically broken and vulnerable to collision and rainbow table attacks.
    """
    # VULNERABLE: MD5 used for password storage
    return hashlib.md5(plain_password.encode("utf-8")).hexdigest()


def load_user_session(serialized_token: str):
    """
    CWE-502: Deserialization of Untrusted Data
    pickle.loads on untrusted user input can lead to arbitrary code execution.
    """
    # VULNERABLE: Unpickling untrusted payload
    raw_bytes = base64.b64decode(serialized_token)
    session_data = pickle.loads(raw_bytes)
    return session_data
