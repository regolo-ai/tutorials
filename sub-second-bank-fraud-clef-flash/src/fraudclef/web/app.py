"""Local console: status, scenarios, benchmark, policy and audit. Bind to 127.0.0.1 only:
there is no authentication, and the Regolo key never reaches the browser."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import __version__
from ..audit import read_records, verify
from .. import benchmark, pricing
from ..benchmark import MAX_REMOTE_CONCURRENCY, BenchError, benchable, build_engine, item_type, list_runs, run_compare, save_run
from .. import generator, tabformer
from ..datagen import random_dataset, scenarios
from ..models import ScoringRequest
from ..policy import PolicyError, load_policy, load_policy_text
from ..pricing import cost_usd, model_price

load_dotenv(".env")

POLICY_DIR = Path("policies")
SCENARIO_DIR = Path("data/scenarios")
RANDOM_DATASET = Path("data/random_dataset.json")
AUDIT_LOG = Path("logs/decisions.jsonl")
ENV_FILE = Path(".env")
ENV_EXAMPLE = Path(".env.example")
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="fraudclef console", version=__version__, docs_url="/api/docs", redoc_url=None)
_jobs: dict[str, dict[str, Any]] = {}
POLICY_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
BATCH_ID = r"^[A-Za-z0-9_.:-]{1,64}$"


@app.middleware("http")
async def same_origin_writes(request: Request, call_next):
    """The console writes files (.env, policies). Refuse writes started by another web page:
    browsers send Origin on cross-site POST/PUT, and it must be this console."""
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != f"{request.url.scheme}://{request.url.netloc}":
            return JSONResponse({"detail": "cross-origin request refused"}, status_code=403)
        if "application/json" not in request.headers.get("content-type", ""):
            return JSONResponse({"detail": "send JSON"}, status_code=415)
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"  # revalidate: files change between versions
    return response


def _backend() -> str:
    return os.environ.get("FRAUDCLEF_UI_BACKEND", "regolo")


def _policy_files() -> list[Path]:
    return [p for p in sorted(POLICY_DIR.glob("*.yaml")) if not p.name.startswith(".")]


def _policy_path(name: str) -> Path:
    path = (POLICY_DIR / f"{name}.yaml").resolve()
    if path.parent != POLICY_DIR.resolve() or not path.exists():
        raise HTTPException(404, f"policy '{name}' not found")
    return path


def _scenario_items() -> list[dict]:
    if SCENARIO_DIR.exists() and any(SCENARIO_DIR.glob("*.json")):
        return [json.loads(p.read_text()) for p in sorted(SCENARIO_DIR.glob("*.json"))]
    return scenarios()


DATASET_ID = r"^(scenarios|random|sepa-transfers|random-ecommerce|random-instore|generated:[a-z0-9][a-z0-9_-]{0,39})$"

# Built-in sets: the European reference suite, and the 2,000-customer Eurozone portfolio whole or by rail.
BUILTIN_SETS: dict[str, dict[str, Any]] = {
    "scenarios": {"title": "European fraud & compliance reference suite", "how": "Curated multi-rail cases across IT, DE, FR, ES, and NL",
                  "detail": "Cards in shop and online, ATM, SEPA Instant (VoP and APP scams), interbank mule hits, SME invoice swaps, and direct debits. Three DORA outage and shadow checks run individually."},
    "sepa-transfers": {"title": "SEPA Instant & credit transfers (EU)", "how": "Eurozone retail & SME bank transfers across 6 hubs",
                       "detail": "Habitual rent and supplier transfers alongside spoofed bank-hotline APP scams, VoP mismatches, SIM-swap account takeovers, and flagged mule IBANs.",
                       "channels": ["sepa_instant", "sepa_credit_transfer"]},
    "random-ecommerce": {"title": "European e-commerce & remote cards", "how": "Card-not-present traffic across IT, DE, FR, and ES",
                         "detail": "Rail, airline, and retail e-commerce alongside stolen card spikes, unauthenticated micro-charge card testing, and foreign-IP digital asset ramps.",
                         "channels": ["card_not_present"]},
    "random-instore": {"title": "In-store POS & ATM card traffic", "how": "Contactless POS & ATM traffic across 6 European hubs",
                       "detail": "Everyday supermarket, pharmacy, fuel, and restaurant taps plus intra-EU travel, tested against cloned-card impossible travel and foreign ATM cash-outs.",
                       "channels": ["card_present", "atm"]},
    "random": {"title": "Eurozone multi-channel retail portfolio", "how": "2,000 customers with 30 localized past payments each",
               "detail": "Full retail and SME mix across Milan, Rome, Frankfurt, Munich, Paris, and Madrid: POS, e-commerce, ATM, SEPA Instant, credit transfers, and SDD mandates."},
}


def _random_items() -> list[dict]:
    return json.loads(RANDOM_DATASET.read_text()) if RANDOM_DATASET.exists() else random_dataset(2000)


def _dataset_items(dataset: str, n: int | None = None) -> list[dict]:
    """Items of a dataset: the named scenarios, the Eurozone portfolio (whole or by rail), or a generated set."""
    if dataset == "scenarios":
        return _scenario_items()
    if dataset in BUILTIN_SETS:
        channels = BUILTIN_SETS[dataset].get("channels")
        items = [i for i in _random_items() if not channels or i["request"]["candidate"]["channel"] in channels]
        return items[:n] if n else items
    name = dataset.removeprefix("generated:")
    path = (generator.GENERATED_DIR / f"{name}.json").resolve()
    if not dataset.startswith("generated:") or path.parent != generator.GENERATED_DIR.resolve() or not path.exists():
        raise HTTPException(404, f"dataset '{dataset}' not found")
    items = json.loads(path.read_text())
    return items[:n] if n else items


def _dataset_meta(dataset: str, items: list[dict]) -> dict[str, Any]:
    """What a set is made of, shown next to its results: title, how it was built, and the
    payments by type and label. Generated sets add the parameters they were written with."""
    items = benchable(items)
    types: dict[str, int] = {}
    for i in items:
        types[item_type(i)] = types.get(item_type(i), 0) + 1
    meta: dict[str, Any] = {
        "id": dataset, "n": len(items), "types": dict(sorted(types.items(), key=lambda kv: -kv[1])),
        "labels": {k: sum(i.get("label") == k for i in items) for k in ("fraud", "legit")},
        "history": max((len(i["request"]["history"]) for i in items), default=0),
    }
    if dataset in BUILTIN_SETS:
        b = BUILTIN_SETS[dataset]
        meta.update(title=b["title"], how=b["how"], detail=b["detail"])
    else:
        g = next((m for m in generator.list_sets() if f"generated:{m['name']}" == dataset), {})
        meta.update(title=g.get("title") or g.get("name") or dataset, how=g.get("how") or f"Written by {g.get('model') or 'a Regolo model'}",
                    detail="", model=g.get("model"), mix=g.get("mix"), history=g.get("history", meta["history"]),
                    vulnerable_pct=g.get("vulnerable_pct"), cost_usd=g.get("cost_usd"), created_at=g.get("created_at"))
    return meta


# ── status ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"ok": True, "version": __version__}


async def _regolo_status() -> dict[str, Any]:
    """Reachability, model listing and key check. Done in fake mode too: the sidebar shows
    whether the key is active. Never returns the key itself."""
    key = os.environ.get("REGOLO_API_KEY")
    base = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai")
    regolo: dict[str, Any] = {"key_present": bool(key), "base_url": base, "reachable": False, "model_listed": False}
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.get(f"{base}/models")
            regolo["reachable"] = r.status_code == 200
            regolo["model_listed"] = any(m.get("id") == "clef-flash" for m in r.json().get("data", []))
            if key:
                a = await c.get(f"{base}/key/info", headers={"Authorization": f"Bearer {key}"})
                regolo["key_valid"] = a.status_code == 200
    except Exception as e:  # network down, DNS, TLS…
        regolo["error"] = f"{type(e).__name__}: {e}"[:200]
    return regolo


@app.get("/api/status")
async def status():
    regolo = await _regolo_status()
    policies = []
    for p in _policy_files():
        try:
            pol = load_policy(p)
            policies.append({"name": p.stem, "ok": True, "ref": pol.ref, "mode": pol.governance.mode,
                             "extends": (yaml.safe_load(p.read_text()) or {}).get("extends"),
                             "questions": list(pol.questions), "rules": len(pol.hard_rules),
                             "history_payments": pol.history.payments, "description": pol.description,
                             "routing": pol.routing.mode, "timeouts_ms": pol.model.timeout_ms,
                             "example_rule": next(({"id": r.id, "when": r.when, "decision": r.decision, "reason": r.reason}
                                                   for r in pol.hard_rules), None)})
        except PolicyError as e:
            policies.append({"name": p.stem, "ok": False, "error": str(e)[:300]})

    audit = {"exists": AUDIT_LOG.exists()}
    if AUDIT_LOG.exists() and AUDIT_LOG.stat().st_size:
        ok, n, msg = verify(AUDIT_LOG)
        audit.update(ok=ok, records=n, message=msg)

    return {
        "version": __version__,
        "backend": _backend(),
        "regolo": regolo,
        "price": model_price() if _backend() == "regolo" else None,
        "policies": policies,
        "audit": audit,
        "data": {"scenarios": len(list(SCENARIO_DIR.glob("*.json"))) if SCENARIO_DIR.exists() else 0,
                 "random_dataset": RANDOM_DATASET.exists()},
        "max_concurrency": MAX_REMOTE_CONCURRENCY,
        "env_file": ENV_FILE.exists(),
    }


# ── policy ────────────────────────────────────────────────────────────────────
@app.get("/api/policies/{name}")
async def policy(name: str):
    path = _policy_path(name)
    pol = load_policy(path)
    return {
        "name": name,
        "ref": pol.ref,
        "yaml": path.read_text(),
        "extends": (yaml.safe_load(path.read_text()) or {}).get("extends"),
        "hard_rules": [{"id": r.id, "decision": r.decision, "reason": r.reason} for r in pol.hard_rules],
        "questions": {k: {"type": q.type, "weight": q.weight} for k, q in pol.questions.items()},
        "thresholds": {k: v.model_dump() for k, v in pol.decision.thresholds.items()},
        "routing": pol.routing.model_dump(),
        "timeouts_ms": pol.model.timeout_ms,
        "history_payments": pol.history.payments,
    }


class PolicyText(BaseModel):
    yaml: str = Field(max_length=200_000)
    name: str = "draft"


def _check(text: str, name: str):
    try:
        return load_policy_text(text, POLICY_DIR, name)
    except PolicyError as e:
        raise HTTPException(422, str(e))


@app.post("/api/policies/validate")
async def validate_policy(body: PolicyText):
    """Check unsaved YAML: schema, governance, weights, thresholds and a dry run of every rule."""
    pol = _check(body.yaml, body.name)
    return {"ok": True, "ref": pol.ref, "rules": len(pol.hard_rules), "questions": list(pol.questions),
            "history_payments": pol.history.payments}


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".part")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


@app.put("/api/policies/{name}")
async def save_policy(name: str, body: PolicyText):
    """Save a policy. The previous file is kept in policies/.history/, and the save is undone if
    a policy that extends this one stops loading."""
    path = _policy_path(name)
    _check(body.yaml, name)
    history = POLICY_DIR / ".history"
    history.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = history / f"{name}-{stamp}.yaml"
    shutil.copy2(path, backup)
    _atomic_write(path, body.yaml)
    broken = []
    for other in _policy_files():
        try:
            load_policy(other)
        except PolicyError as e:
            broken.append(f"{other.stem}: {e}")
    if broken:
        _atomic_write(path, backup.read_text())
        backup.unlink()
        raise HTTPException(422, "not saved: this change breaks a policy that extends it. " + " | ".join(broken)[:1500])
    return {"saved": name, "backup": str(backup)}


class NewPolicy(BaseModel):
    name: str
    base: str = "retail-eu"
    copy_content: bool = False


@app.post("/api/policies")
async def create_policy(body: NewPolicy):
    """Create a policy that inherits `base` (and overrides nothing yet), or a full copy of it."""
    if not POLICY_NAME.match(body.name):
        raise HTTPException(422, "use 1-40 lowercase letters, digits, '-' or '_', starting with a letter or digit")
    path = POLICY_DIR / f"{body.name}.yaml"
    if path.exists():
        raise HTTPException(409, f"policy '{body.name}' already exists")
    base = _policy_path(body.base)
    if body.copy_content:
        text = base.read_text()
    else:
        text = (f"# {body.name}: inherits every setting from {base.name}.\n"
                f"# Add here only what changes, for example:\n"
                f"#   decision:\n#     thresholds:\n#       default: {{step_up: 0.35, hold: 0.6, block: 0.8}}\n"
                f"extends: {base.name}\n"
                f"policy_id: {body.name}\n"
                f"description: Copy of {base.stem}. Say here what this policy is for.\n")
    _check(text, body.name)
    _atomic_write(path, text)
    return {"created": body.name}


# ── Regolo API key ────────────────────────────────────────────────────────────
class KeyIn(BaseModel):
    key: str = Field(min_length=8, max_length=400)


async def _key_accepted(key: str) -> bool:
    base = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai")
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.get(f"{base}/key/info", headers={"Authorization": f"Bearer {key}"})
    return r.status_code == 200


def _write_env(name: str, value: str) -> None:
    lines = (ENV_FILE.read_text() if ENV_FILE.exists() else ENV_EXAMPLE.read_text() if ENV_EXAMPLE.exists() else "").splitlines()
    out, done = [], False
    for line in lines:
        if line.split("=", 1)[0].strip() == name:
            if not done:
                out.append(f"{name}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{name}={value}")
    fd, tmp = tempfile.mkstemp(dir=ENV_FILE.resolve().parent, prefix=".env-", suffix=".part")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(out) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV_FILE)


@app.post("/api/settings/regolo-key")
async def set_regolo_key(body: KeyIn):
    """Check the key against Regolo, then store it in .env (mode 600). It is never sent back."""
    key = body.key.strip()
    if re.search(r"\s", key):
        raise HTTPException(422, "the key must not contain spaces or line breaks")
    try:
        accepted = await _key_accepted(key)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"could not reach Regolo to check the key: {type(e).__name__}")
    if not accepted:
        raise HTTPException(422, "Regolo rejected this key. Copy it again from your regolo.ai dashboard.")
    _write_env("REGOLO_API_KEY", key)
    os.environ["REGOLO_API_KEY"] = key
    pricing._cache.clear()
    return {"saved": True}


# ── scenarios and scoring ─────────────────────────────────────────────────────
@app.get("/api/scenarios")
async def list_scenarios(dataset: str = Query("scenarios", pattern=DATASET_ID)):
    out = []
    for s in _dataset_items(dataset):
        c = s["request"]["candidate"]
        out.append({
            "name": s["name"], "description": s.get("description") or s.get("type") or s["name"],
            "expected": s.get("expected") or [], "label": s.get("label"), "type": s.get("type"),
            "channel": c["channel"], "amount": c["amount"], "currency": c.get("currency", "EUR"),
            "demo": bool(s.get("simulate_backend_failure") or s.get("policy_overrides")),
            "request": s["request"],
        })
    return out


class ScoreIn(BaseModel):
    dataset: str = Field("scenarios", pattern=DATASET_ID)
    scenario: str | None = None
    request: dict | None = None
    policy: str = "retail-eu"
    routing: Literal["cascade", "always", "never"] | None = None
    batch: str | None = Field(None, pattern=BATCH_ID)


@app.post("/api/score")
async def score(body: ScoreIn):
    item: dict[str, Any] = {}
    if body.scenario:
        item = next((s for s in _dataset_items(body.dataset) if s["name"] == body.scenario), None)
        if item is None:
            raise HTTPException(404, f"scenario '{body.scenario}' not found")
    elif body.request:
        item = {"name": "custom", "request": body.request}
    else:
        raise HTTPException(422, "send a scenario name or a request")
    policy_path = _policy_path(body.policy)  # 404 for unknown names or paths outside policies/
    try:
        pol = load_policy(policy_path, item.get("policy_overrides"))
        req = ScoringRequest.model_validate(item["request"])
    except PolicyError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(422, f"invalid request: {e}")
    engine = build_engine(pol, _backend(), str(AUDIT_LOG), fail=bool(item.get("simulate_backend_failure")))
    try:
        routing = body.routing or item.get("routing")
        d = await engine.score(req, routing=routing, context={
            "source": "console-scenario" if body.scenario else "console-request", "scenario": item["name"] if body.dataset == "scenarios" else f"{body.dataset}/{item['name']}",
            "run_id": body.batch, "routing": routing or pol.routing.mode, "policy_name": body.policy})
    finally:
        await engine.aclose()
    price = model_price(pol.model.name) if _backend() == "regolo" else {"usd_per_input_token": 0.0}
    expected = item.get("expected")
    return {
        "decision": d.model_dump(mode="json"),
        "expected": expected,
        "pass": None if not expected else d.decision in expected,
        "cost_usd": cost_usd(d.input_tokens, price),
    }


# ── benchmark jobs ────────────────────────────────────────────────────────────
class BenchIn(BaseModel):
    dataset: str = Field("scenarios", pattern=DATASET_ID)
    n: int = Field(200, ge=5, le=6000)
    modes: list[Literal["always", "cascade", "never"]] = Field(["always", "cascade"], min_length=1)
    concurrency: int = Field(2, ge=1, le=MAX_REMOTE_CONCURRENCY)
    policy: str = "retail-eu"
    policies: list[str] | None = Field(None, min_length=1, max_length=3)  # compare up to three; `policy` if absent


@app.post("/api/bench")
async def start_bench(body: BenchIn):
    if any(j["status"] == "running" and j.get("kind", "bench") == "bench" for j in _jobs.values()):
        raise HTTPException(409, "a benchmark is already running; wait for it to finish")
    names = list(dict.fromkeys(body.policies or [body.policy]))
    pols = {name: load_policy(_policy_path(name)) for name in names}
    items = _dataset_items(body.dataset, None if body.dataset == "scenarios" else body.n)
    job_id = uuid.uuid4().hex[:10]
    job = {"id": job_id, "status": "running", "done": 0, "total": len(benchable(items)) * len(body.modes) * len(pols),
           "mode": None, "report": None, "error": None, "events": []}
    _jobs[job_id] = job

    def progress(mode, done, total):
        job.update(mode=mode, done=done, total=total)

    def on_item(policy, mode, item, d):
        # The last few payments checked, for the progress panel; the newest first.
        job["events"] = [{"policy": policy, "mode": mode, "name": item["name"], "description": item.get("description") or item["name"],
                          "type": item_type(item), "decision": d.decision, "decided_by": d.decided_by,
                          "total_ms": d.latency_ms["total"], "model_ms": d.latency_ms.get("model"),
                          "tokens": d.input_tokens}] + job["events"][:5]

    async def work():
        try:
            report = await run_compare(items, pols, _backend(), list(body.modes), body.concurrency,
                                       audit_path=str(AUDIT_LOG), progress=progress, source="console-bench",
                                       on_item=on_item)
            report["dataset"] = body.dataset
            report["dataset_meta"] = _dataset_meta(body.dataset, items)
            save_run(report)
            job.update(status="done", report=report)
        except BenchError as e:
            job.update(status="error", error=str(e))
        except Exception as e:
            job.update(status="error", error=f"{type(e).__name__}: {e}")

    asyncio.create_task(work())
    return {"job": job_id, "total": job["total"]}


def _measured_tokens(policy: str, history: int) -> int | None:
    """Input tokens per model call measured in the latest run of this policy with the same history."""
    for r in list_runs():
        try:
            rep = json.loads((benchmark.RUNS_DIR / f"{r['id']}.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for c in benchmark.cells(rep):
            if c.get("policy") == policy and c.get("input_tokens_per_call") and \
                    (c.get("history_payments") or rep.get("history_payments")) == history:
                return c["input_tokens_per_call"]
    return None


@app.post("/api/bench/estimate")
async def bench_estimate(body: BenchIn):
    """Before a run: how many payments reach Clef-Flash in each combination (counted offline),
    and what that costs at the Regolo price, with tokens per call from earlier runs."""
    names = list(dict.fromkeys(body.policies or [body.policy]))
    items = _dataset_items(body.dataset, None if body.dataset == "scenarios" else body.n)
    price = model_price() if _backend() == "regolo" else {"usd_per_input_token": 0.0, "source": "offline demo"}
    configs = []
    for name in names:
        pol = load_policy(_policy_path(name))
        measured = _measured_tokens(name, pol.history.payments)
        tokens = measured or round(len(pol.questions) * (500 + 73 * pol.history.payments))
        for mode, calls in (await benchmark.model_calls(items, pol, list(body.modes))).items():
            configs.append({"policy": name, "mode": mode, "model_calls": calls, "tokens_per_call": tokens,
                            "tokens_measured": measured is not None,
                            "usd": round(calls * tokens * price["usd_per_input_token"], 6)})
    return {"n": len(benchable(items)), "configs": configs, "usd": round(sum(c["usd"] for c in configs), 6),
            "model_calls": sum(c["model_calls"] for c in configs), "price": price}


@app.get("/api/bench/jobs/{job_id}")
async def bench_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    return job


@app.get("/api/bench/runs")
async def bench_runs():
    return list_runs()


@app.get("/api/bench/runs/{run_id}")
async def bench_run(run_id: str):
    path = (benchmark.RUNS_DIR / f"{run_id}.json").resolve()
    if path.parent != benchmark.RUNS_DIR.resolve() or not path.exists():
        raise HTTPException(404, "run not found")
    return benchmark.restat(json.loads(path.read_text()))


# ── generated datasets ────────────────────────────────────────────────────────
@app.get("/api/datasets")
async def datasets():
    out = []
    for key in BUILTIN_SETS:
        if key != "scenarios" and not RANDOM_DATASET.exists():
            continue
        items = _dataset_items(key)
        out.append({"id": key, "n": len(items), "builtin": True, **_dataset_meta(key, items)})
    for m in generator.list_sets():
        key = f"generated:{m['name']}"
        out.append({"id": key, "n": m["generated"], "builtin": False, "generation": m,
                    **_dataset_meta(key, _dataset_items(key))})
    return out


@app.get("/api/generate/models")
async def generation_models():
    try:
        models = await generator.chat_models()
    except generator.GenerationError as e:
        raise HTTPException(422, str(e))
    return {"models": models, "types": {k: {"title": v["title"], "label": v["label"], "brief": v["brief"]}
                                        for k, v in generator.TYPES.items()}}


class GenerateIn(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")
    title: str = Field("", max_length=60)
    model: str = Field(min_length=1, max_length=80)
    n: int = Field(20, ge=1, le=generator.MAX_ITEMS)
    history: int = Field(12, ge=3, le=30)
    vulnerable_pct: float = Field(5, ge=0, le=100)
    mix: dict[str, float]
    concurrency: int = Field(4, ge=1, le=8)


@app.post("/api/generate/estimate")
async def generation_estimate(body: GenerateIn):
    models = {m["id"]: m for m in await generator.chat_models()}
    if body.model not in models:
        raise HTTPException(422, f"model '{body.model}' is not available")
    try:
        plan = generator.allocate(body.mix, body.n)
    except generator.GenerationError as e:
        raise HTTPException(422, str(e))
    return {"counts": {k: plan.count(k) for k in dict.fromkeys(plan)},
            **generator.estimate(body.n, body.history, models[body.model])}


@app.post("/api/generate")
async def start_generation(body: GenerateIn):
    if any(j["status"] == "running" and j.get("kind") == "generate" for j in _jobs.values()):
        raise HTTPException(409, "a generation is already running; wait for it to finish")
    if (generator.GENERATED_DIR / f"{body.name}.json").exists():
        raise HTTPException(409, f"a dataset called '{body.name}' already exists: choose another name")
    try:
        generator.allocate(body.mix, body.n)
    except generator.GenerationError as e:
        raise HTTPException(422, str(e))
    job_id = uuid.uuid4().hex[:10]
    job = {"id": job_id, "kind": "generate", "status": "running", "done": 0, "total": body.n, "result": None, "error": None}
    _jobs[job_id] = job

    async def work():
        try:
            meta = await generator.generate_set(body.name, body.model, body.mix, body.n, body.history, body.vulnerable_pct,
                                                body.concurrency, progress=lambda d, t: job.update(done=d, total=t),
                                                title=body.title.strip())
            if not meta["generated"]:
                job.update(status="error", error="no valid payment was generated: " + "; ".join(f["error"] for f in meta["failed"][:3]))
            else:
                job.update(status="done", result=meta)
        except generator.GenerationError as e:
            job.update(status="error", error=str(e))
        except Exception as e:
            job.update(status="error", error=f"{type(e).__name__}: {e}")

    asyncio.create_task(work())
    return {"job": job_id, "total": body.n}


# ── TabFormer: download IBM's dataset, then sample it ────────────────────────
def _tabformer_status() -> dict[str, Any]:
    csv_path = tabformer.RAW_DIR / tabformer.CSV_NAME
    running = next((j for j in _jobs.values() if j.get("kind") == "tabformer" and j["status"] == "running"), None)
    return {"csv": csv_path.exists(), "csv_bytes": csv_path.stat().st_size if csv_path.exists() else 0,
            "archive_bytes": tabformer.ARCHIVE_BYTES, "periods": tabformer.PERIODS,
            "job": running["id"] if running else None}


@app.get("/api/tabformer")
async def tabformer_status():
    return _tabformer_status()


def _start_tabformer_job(stage: str, work) -> dict:
    if _tabformer_status()["job"]:
        raise HTTPException(409, "a TabFormer download or sample is already running; wait for it to finish")
    job_id = uuid.uuid4().hex[:10]
    job = {"id": job_id, "kind": "tabformer", "status": "running", "stage": stage, "done": 0, "total": 0,
           "result": None, "error": None}
    _jobs[job_id] = job

    async def run():
        try:
            job.update(status="done", result=await work(job))
        except Exception as e:
            job.update(status="error", error=f"{type(e).__name__}: {e}" if not isinstance(e, HTTPException) else e.detail)

    asyncio.create_task(run())
    return {"job": job_id}


@app.post("/api/tabformer/download")
async def tabformer_download():
    """Download IBM's archive (about 279 MB) from its public Box share, then extract only the CSV."""
    if _tabformer_status()["csv"]:
        raise HTTPException(409, "TabFormer is already downloaded")

    async def work(job):
        raw = tabformer.RAW_DIR
        raw.mkdir(parents=True, exist_ok=True)
        part = raw / f"{tabformer.ARCHIVE_NAME}.part"
        async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(60, read=120),
                                     headers={"User-Agent": "Mozilla/5.0 fraudclef"}) as c:
            async with c.stream("GET", tabformer.BOX_URL) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"Box answered HTTP {r.status_code}: download it by hand (docs/USING.md §9)")
                job["total"] = int(r.headers.get("content-length") or tabformer.ARCHIVE_BYTES)
                with part.open("wb") as f:
                    async for chunk in r.aiter_bytes(1 << 20):
                        f.write(chunk)
                        job["done"] += len(chunk)
        archive = raw / tabformer.ARCHIVE_NAME
        part.replace(archive)
        job.update(stage="extracting", done=0, total=0)
        csv_path = await asyncio.to_thread(tabformer.extract_csv, archive, raw)
        archive.unlink()  # the CSV is all that is used; keeping both would take 2.6 GB
        return {"csv_bytes": csv_path.stat().st_size}

    return _start_tabformer_job("downloading", work)


class TabformerSampleIn(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")
    title: str = Field("", max_length=60)
    period: Literal["train", "validation", "test"] = "test"
    fraud: int = Field(50, ge=1, le=500)
    legit: int = Field(1000, ge=10, le=10000)
    seed: int = Field(7, ge=0, le=10**6)


@app.post("/api/tabformer/sample")
async def tabformer_sample(body: TabformerSampleIn):
    csv_path = tabformer.RAW_DIR / tabformer.CSV_NAME
    if not csv_path.exists():
        raise HTTPException(409, "download TabFormer first")
    if (generator.GENERATED_DIR / f"{body.name}.json").exists():
        raise HTTPException(409, f"a dataset called '{body.name}' already exists: choose another name")

    async def work(job):
        loop = asyncio.get_running_loop()
        job["total"] = 24_386_900  # rows in card_transaction.v1.csv, read once per pass

        def progress(stage, rows):
            loop.call_soon_threadsafe(job.update, {"stage": stage, "done": rows})

        items, info = await asyncio.to_thread(tabformer.build_sample, csv_path, body.fraud, body.legit, body.period,
                                              body.seed, progress)
        return tabformer.save_sample(items, info, body.name, body.title.strip() or body.name)

    return _start_tabformer_job("selecting", work)


@app.get("/api/tabformer/jobs/{job_id}")
async def tabformer_job(job_id: str):
    job = _jobs.get(job_id)
    if not job or job.get("kind") != "tabformer":
        raise HTTPException(404, "unknown job")
    return job


@app.get("/api/generate/jobs/{job_id}")
async def generation_job(job_id: str):
    job = _jobs.get(job_id)
    if not job or job.get("kind") != "generate":
        raise HTTPException(404, "unknown job")
    return job


# ── audit ─────────────────────────────────────────────────────────────────────
def _group_key(rec: dict) -> str:
    ctx = rec.get("context") or {}
    if ctx.get("run_id"):
        return ctx["run_id"]
    if ctx.get("source"):
        return f"{ctx['source']}:{rec['ts'][:10]}"  # single runs, grouped per day
    return "before-run-tracking"


def _row(n: int, r: dict) -> dict:
    d, ctx = r["decision"], r.get("context") or {}
    return {"line": n, "ts": r["ts"], "transaction_id": r["transaction_id"], "scenario": ctx.get("scenario"),
            "source": ctx.get("source"), "mode": ctx.get("mode") or ctx.get("routing"), "group": _group_key(r),
            "decision": d["decision"], "decided_by": d["decided_by"], "enforced": d["enforced"], "risk": d["risk_score"],
            "policy": r["policy"], "tokens": r.get("model_input_tokens"), "total_ms": d["latency_ms"].get("total"),
            "record_hash": r.get("record_hash", "")[:16]}


@app.get("/api/audit")
async def audit(limit: int = Query(200, ge=1, le=5000), group: str | None = None):
    """Latest records, newest first, optionally only one group (a benchmark run, a 'Run all', ...)."""
    records = read_records(AUDIT_LOG)
    if not records:
        return {"records": [], "groups": [], "verify": None}
    rows = [_row(n, r) for n, r in enumerate(records, 1)]
    groups: dict[str, dict] = {}
    for row in rows:
        g = groups.setdefault(row["group"], {"id": row["group"], "source": row["source"], "first": row["ts"],
                                             "last": row["ts"], "count": 0, "modes": set(), "policies": set(),
                                             "decisions": {k: 0 for k in ("approve", "step_up", "hold", "block")}})
        g["count"] += 1
        g["last"] = row["ts"]
        g["decisions"][row["decision"]] += 1
        if row["mode"]:
            g["modes"].add(row["mode"])
        g["policies"].add(row["policy"])
    for g in groups.values():
        g["modes"], g["policies"] = sorted(g["modes"]), sorted(g["policies"])
    selected = [r for r in rows if r["group"] == group] if group else rows
    ok, n, msg = verify(AUDIT_LOG)
    return {"records": selected[::-1][:limit], "matching": len(selected),
            "groups": sorted(groups.values(), key=lambda g: g["last"], reverse=True),
            "verify": {"ok": ok, "records": n, "message": msg}}


@app.get("/api/audit/records/{line}")
async def audit_record(line: int):
    """One full record: features, the pseudonymised state sent to Regolo, answers and hashes."""
    records = read_records(AUDIT_LOG)
    if not 1 <= line <= len(records):
        raise HTTPException(404, "record not found")
    return records[line - 1]


# ── static UI ─────────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(STATIC / "brand" / "icon.svg", media_type="image/svg+xml")


def _asset_version(name: str) -> str:
    return hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:10]


@app.get("/")
async def index():
    """The page names its CSS and JS with a content hash, so a browser never pairs a new page
    with a cached old script or stylesheet."""
    html = (STATIC / "index.html").read_text()
    for name in ("styles.css", "app.js"):
        html = html.replace(f"/static/{name}\"", f"/static/{name}?v={_asset_version(name)}\"")
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})
