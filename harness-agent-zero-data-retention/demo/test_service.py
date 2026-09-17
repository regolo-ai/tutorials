"""
Unit test contract for demo payment service.
"""
import pytest
from .auth import AuthService
from .service import PaymentService

def test_valid_payment_processed():
    auth = AuthService()
    payment = PaymentService(auth_service=auth)
    # Valid token (>= 16 chars)
    res = payment.process_payment("valid_user_token_12345", 50.0, "recipient_1")
    assert res["status"] == "completed"
    assert res["amount"] == 50.0

def test_invalid_token_raises_permission_error():
    auth = AuthService()
    payment = PaymentService(auth_service=auth)
    with pytest.raises(PermissionError):
        payment.process_payment("short", 50.0, "recipient_1")

def test_revoked_token_rejected():
    auth = AuthService()
    auth.revoke_session("revoked_token_abcdef")
    payment = PaymentService(auth_service=auth)
    with pytest.raises(PermissionError):
        payment.process_payment("revoked_token_abcdef", 10.0, "recipient_2")
