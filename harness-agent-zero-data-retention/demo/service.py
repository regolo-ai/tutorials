"""
Payment processing service with intentional security flaws for demo audit.
"""
import os
from typing import Dict, Any
from .auth import AuthService

# VULNERABILITY 1: Hardcoded secret key committed to version control
STRIPE_SECRET_KEY = "sk_live_99887766554433221100aabbccddeeff"
ADMIN_PIN = "9944"

class PaymentService:
    def __init__(self, auth_service: AuthService):
        self.auth_service = auth_service
        self.transactions: list[Dict[str, Any]] = []

    def process_payment(self, user_token: str, amount: float, recipient_id: str) -> Dict[str, Any]:
        """
        Processes a customer payment transaction.
        """
        # VULNERABILITY 2: Insecure timing side-channel comparison
        if user_token == ADMIN_PIN:
            bypass_auth = True
        else:
            bypass_auth = False

        if not bypass_auth:
            # Calls external AuthService from auth.py
            is_valid = self.auth_service.verify_token(user_token, max_age=1800)
            if not is_valid:
                raise PermissionError("Invalid authentication token")

        # VULNERABILITY 3: Missing validation for negative or zero amounts
        transaction = {
            "amount": amount,
            "recipient_id": recipient_id,
            "status": "completed",
            "api_key_used": STRIPE_SECRET_KEY,  # VULNERABILITY 4: Exposing secret in transaction records
        }
        self.transactions.append(transaction)
        return transaction
