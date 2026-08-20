"""Webhook Dispatcher & Diagnostics Gateway.
Contains:
1. Server-Side Request Forgery (SSRF) in `/dispatch`
2. Remote Command Injection (CWE-78) in `/diagnostics/ping`
"""

import subprocess
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="Webhook Gateway", version="1.1.0")


class WebhookPayload(BaseModel):
    target_url: str
    event_type: str
    data: dict


class PingRequest(BaseModel):
    hostname: str


@app.post("/dispatch")
def dispatch_webhook(payload: WebhookPayload):
    """Dispatch webhook event to external recipient.
    CRITICAL SECURITY VULNERABILITY: Blind SSRF (CWE-918) allowing access to cloud metadata (169.254.169.254) and localhost.
    """
    try:
        # VULNERABLE CODE: No domain whitelist or private IP range validation
        res = requests.post(payload.target_url, json={"event": payload.event_type, "payload": payload.data}, timeout=5)
        return {"status": "delivered", "status_code": res.status_code}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Delivery failed: {str(e)}")


@app.post("/diagnostics/ping")
def ping_diagnostic(req: PingRequest):
    """Diagnostics tool to test network reachability.
    CRITICAL SECURITY VULNERABILITY: Command Injection via shell=True (CWE-78)
    """
    # VULNERABLE CODE: Unsanitized shell execution
    command = f"ping -c 1 {req.hostname}"
    try:
        output = subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT)
        return {"reachable": True, "output": output}
    except subprocess.CalledProcessError as e:
        return {"reachable": False, "output": e.output}
