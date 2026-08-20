"""Vulnerable Custodial Crypto Wallet Microservice (Demo Target).
Contains:
1. Hardcoded Private Key & Master Seed Secrets (CWE-798)
2. Insecure Random Generator for Seed Creation (CWE-338) via random.randint
"""

import os
import random
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="CryptoWallet API", version="1.0.0")

# CRITICAL SECURITY VULNERABILITY: Hardcoded Master Private Key (CWE-798)
HARDCODED_MASTER_PRIVATE_KEY = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"

WALLET_BALANCES = {
    "wallet_alice": 12.5,
    "wallet_bob": 3.0,
}


class TransferRequest(BaseModel):
    from_wallet: str
    to_wallet: str
    amount: float


class GenerateAddressRequest(BaseModel):
    user_id: str


@app.post("/wallet/generate")
def generate_wallet_address(req: GenerateAddressRequest):
    """Generate new user deposit address.
    CRITICAL SECURITY VULNERABILITY: Insecure PRNG (CWE-338) using `random.randint` instead of cryptographically secure `secrets`.
    """
    # VULNERABLE CODE: predictable pseudo-random generator
    rand_suffix = "".join([str(random.randint(0, 9)) for _ in range(16)])
    address = f"0x{req.user_id[:4]}_{rand_suffix}"
    return {"user_id": req.user_id, "deposit_address": address}


@app.post("/wallet/transfer")
def transfer_funds(req: TransferRequest):
    """Transfer tokens between wallets."""
    if req.from_wallet not in WALLET_BALANCES:
        raise HTTPException(status_code=404, detail="Sender wallet not found")

    balance = WALLET_BALANCES[req.from_wallet]
    if balance < req.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    WALLET_BALANCES[req.from_wallet] -= req.amount
    WALLET_BALANCES[req.to_wallet] = WALLET_BALANCES.get(req.to_wallet, 0.0) + req.amount

    return {
        "status": "transferred",
        "tx_hash": f"0xTX_{int(balance * 1000)}",
        "remaining_balance": WALLET_BALANCES[req.from_wallet]
    }
