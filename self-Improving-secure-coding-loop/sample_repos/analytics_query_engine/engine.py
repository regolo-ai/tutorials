"""Vulnerable Analytics & Formula Evaluation Engine (Demo Target).
Contains:
1. Arbitrary Code Execution via eval() (CWE-94) in `/analytics/calculate`
2. Insecure Object Deserialization via pickle (CWE-502) in `/analytics/cache/load`
"""

import base64
import pickle
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="AnalyticsEngine API", version="1.0.0")


class MetricCalculationRequest(BaseModel):
    formula: str
    variables: dict[str, float]


class CacheImportRequest(BaseModel):
    serialized_cache: str


@app.post("/analytics/calculate")
def calculate_custom_metric(req: MetricCalculationRequest):
    """Evaluate custom user arithmetic formula against dataset variables.
    CRITICAL SECURITY VULNERABILITY: Arbitrary Python Code Execution (CWE-94) via `eval()`.
    """
    try:
        # VULNERABLE CODE: eval() executes arbitrary Python code and imports!
        scope = dict(req.variables)
        result = eval(req.formula, {"__builtins__": __builtins__}, scope)
        return {"formula": req.formula, "result": float(result)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation error: {str(e)}")


@app.post("/analytics/cache/load")
def load_cached_report(req: CacheImportRequest):
    """Load serialized report cache into memory.
    CRITICAL SECURITY VULNERABILITY: Insecure Deserialization (CWE-502) via pickle.
    """
    try:
        # VULNERABLE CODE: pickle.loads allows arbitrary RCE upon payload deserialization
        raw_bytes = base64.b64decode(req.serialized_cache)
        unpickled_data = pickle.loads(raw_bytes)
        return {"status": "cache_restored", "keys": list(unpickled_data.keys()) if isinstance(unpickled_data, dict) else []}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to restore cache: {str(e)}")
