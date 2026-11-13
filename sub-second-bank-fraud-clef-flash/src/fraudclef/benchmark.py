"""Benchmark shared by the CLI and the web console: latency, throughput, routing, tokens and
cost per routing mode, plus decision agreement between modes."""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import audit as audit_mod
from .backends import FakeBackend, make_backend
from .engine import FraudEngine
from .models import Decision, ScoringRequest
from .policy import Policy
from .pricing import cost_usd, model_price

MAX_REMOTE_CONCURRENCY = 8  # Regolo rate limits are unpublished: stay gentle by default
RUNS_DIR = Path("logs/bench_runs")


class BenchError(Exception):
    pass


def build_engine(policy: Policy, backend: str | None, audit_path: str | None = None, fail: bool = False) -> FraudEngine:
    kind = backend or policy.model.backend
    primary = FakeBackend(fail=True) if fail else make_backend(kind, policy.model.name)
    audit = audit_mod.AuditLog(audit_path, policy.audit.hash_chain) if audit_path else None
    return FraudEngine(policy, primary, audit)


def benchable(items: list[dict]) -> list[dict]:
    """Scenarios that simulate outages or change the policy are demos to run one by one."""
    return [i for i in items if not i.get("simulate_backend_failure") and not i.get("policy_overrides")]


async def run_bench(
    items: list[dict],
    policy: Policy,
    backend: str,
    modes: list[str],
    concurrency: int = 1,
    allow_high_concurrency: bool = False,
    audit_path: str | None = None,
    progress: Callable[[str, int, int], None] | None = None,
    source: str = "cli-bench",
    run_id: str | None = None,
    policy_name: str | None = None,
    on_item: Callable[[str, dict, Decision], None] | None = None,
) -> dict[str, Any]:
    if backend == "regolo" and concurrency > MAX_REMOTE_CONCURRENCY and not allow_high_concurrency:
        raise BenchError(f"concurrency {concurrency} exceeds the Regolo limit of {MAX_REMOTE_CONCURRENCY} "
                         "(unpublished rate limits); agree limits with Regolo first")
    items = benchable(items)
    if not items:
        raise BenchError("dataset is empty")
    reqs = [(i, ScoringRequest.model_validate(i["request"])) for i in items]
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_id = run_id or new_run_id(started_at, backend)
    price = model_price(policy.model.name) if backend == "regolo" else {"usd_per_input_token": 0.0, "source": "fake backend"}
    total_steps = len(reqs) * len(modes)
    done = 0
    per_mode: dict[str, dict] = {}
    decisions_by_mode: dict[str, dict[str, str]] = {}

    for mode in modes:
        engine = build_engine(policy, backend, audit_path)
        sem = asyncio.Semaphore(concurrency)

        async def run(item, req):
            nonlocal done
            async with sem:
                d = await engine.score(req, routing=mode, context={
                    "source": source, "run_id": run_id, "mode": mode, "scenario": item.get("name"),
                    "routing": mode, "policy_name": policy_name})
            done += 1
            if on_item:
                on_item(mode, item, d)
            if progress:
                progress(mode, done, total_steps)
            return item, d

        t0 = time.perf_counter()
        try:
            results = await asyncio.gather(*(run(i, r) for i, r in reqs))
        finally:
            await engine.aclose()
        wall = time.perf_counter() - t0
        decisions_by_mode[mode] = {i["name"]: d.decision for i, d in results}
        per_mode[mode] = summarise(mode, results, wall, price)

    report = {
        "id": run_id,
        "started_at": started_at,
        "backend": backend,
        "model": policy.model.name,
        "policy": policy.ref,
        "questions": list(policy.questions),
        "history_payments": policy.history.payments,
        "concurrency": concurrency,
        "n": len(reqs),
        "price": price,
        "modes": per_mode,
    }
    if len(modes) >= 2:
        a, b = decisions_by_mode[modes[0]], decisions_by_mode[modes[1]]
        diff = [{"name": k, modes[0]: a[k], modes[1]: b[k]} for k in a if a[k] != b[k]]
        report["agreement"] = {"modes": modes[:2], "same": len(a) - len(diff), "total": len(a), "differences": diff}
    return report


def new_run_id(started_at: str, backend: str) -> str:
    return f"bench_{started_at.replace(':', '').replace('-', '').replace('+0000', '')}_{backend}"


async def run_compare(
    items: list[dict],
    policies: dict[str, Policy],
    backend: str,
    modes: list[str],
    concurrency: int = 1,
    audit_path: str | None = None,
    progress: Callable[[str, int, int], None] | None = None,
    source: str = "console-bench",
    on_item: Callable[[str, str, dict, Decision], None] | None = None,
) -> dict[str, Any]:
    """Every policy under every routing mode, on the same payments and under one run id: one
    `configs` entry per (policy, mode) pair, in the order given."""
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_id = new_run_id(started_at, backend)
    per_policy = len(benchable(items)) * len(modes)
    configs, first = [], None
    for k, (name, pol) in enumerate(policies.items()):
        offset = k * per_policy
        rep = await run_bench(items, pol, backend, modes, concurrency, audit_path=audit_path, source=source,
                              run_id=run_id, policy_name=name,
                              on_item=(lambda m, i, d, n=name: on_item(n, m, i, d)) if on_item else None,
                              progress=(lambda m, d, t, o=offset, n=name: progress(f"{n}|{m}", o + d, per_policy * len(policies)))
                              if progress else None)
        first = first or rep
        for m in modes:
            configs.append({"policy": name, "policy_ref": rep["policy"], "questions": rep["questions"],
                            "history_payments": rep["history_payments"], **rep["modes"][m]})
    return {
        "id": run_id, "started_at": started_at, "backend": backend, "model": first["model"],
        "policy": ", ".join(policies), "concurrency": concurrency, "n": first["n"], "price": first["price"],
        "history_payments": first["history_payments"], "configs": configs,
    }


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return round(values[min(len(values) - 1, int(round(q / 100 * (len(values) - 1))))], 1)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _bucket(p: float) -> str:
    for edge, name in ((0.01, "<0.01"), (0.1, "0.01-0.1"), (0.9, "0.1-0.9"), (0.99, "0.9-0.99")):
        if p < edge:
            return name
    return ">=0.99"


def item_type(item: dict) -> str:
    """The kind of payment an item stands for; sets without types fall back to their label."""
    return item.get("type") or item.get("label") or "unlabelled"


def cells(report: dict) -> list[dict]:
    """The (policy, mode) results of a run; runs saved before policy comparison have `modes` only."""
    if "configs" in report:
        return report["configs"]
    for m in report["modes"].values():  # the same dicts, so restat updates the report
        m.setdefault("policy", report.get("policy"))
    return list(report["modes"].values())


def summarise(mode: str, results: list[tuple[dict, Decision]], wall: float, price: dict) -> dict[str, Any]:
    n = len(results)
    ds = [d for _, d in results]
    # Attempts include timeouts and calls skipped by an open circuit breaker; latency, tokens and
    # cost per call are measured on the answered calls only, or skipped attempts read as 0 ms.
    model_calls = [d for d in ds if d.input_tokens is not None or "model" in d.latency_ms]
    answered = [d for d in model_calls if d.input_tokens is not None]
    tokens = [d.input_tokens for d in answered]
    total_cost = sum(cost_usd(t, price) for t in tokens)

    level_latency = {}
    for level in ("features", "rules", "prescore", "model"):
        vals = [d.latency_ms[level] for d in (answered if level == "model" else ds) if level in d.latency_ms]
        level_latency[level] = {"mean": _mean(vals), "p95": _pct(vals, 95)}

    by_level = Counter(d.decided_by for d in ds)
    expected = [(i, d) for i, d in results if i.get("expected")]
    fraud = [d for i, d in results if i.get("label") == "fraud"]
    legit = [d for i, d in results if i.get("label") == "legit"]

    buckets: Counter = Counter()
    for d in ds:
        for a in (d.model_answers or {}).values():
            for p in ([a["noul"]] if a["type"] == "noul" else a.get("probabilities", {}).values()):
                buckets[_bucket(p)] += 1

    by_type: dict[str, dict] = {}
    for i, d in results:
        t = by_type.setdefault(item_type(i), {"label": i.get("label"), "n": 0, "stopped": 0, "ms": [], "cost_usd": 0.0})
        t["n"] += 1
        t["stopped"] += d.decision != "approve"
        t["ms"].append(d.latency_ms["total"])
        t["cost_usd"] += cost_usd(d.input_tokens, price) if d.input_tokens is not None else 0.0
    for t in by_type.values():
        t["median_ms"] = _pct(t.pop("ms"), 50)
        t["cost_usd"] = round(t["cost_usd"], 6)

    totals = [d.latency_ms["total"] for d in ds]
    model_lat = [d.latency_ms["model"] for d in answered if "model" in d.latency_ms]
    return {
        "mode": mode,
        "n": n,
        "wall_s": round(wall, 2),
        "throughput_rps": round(n / wall, 2) if wall else None,
        "decided_by": {k: by_level.get(k, 0) for k in ("rule", "prescore", "model", "fail_mode")},
        "decisions": {k: sum(d.decision == k for d in ds) for k in ("approve", "step_up", "hold", "block")},
        "sent_to_model_pct": round(100 * len(model_calls) / n, 1) if n else 0.0,
        "latency_total_ms": {"p50": _pct(totals, 50), "p95": _pct(totals, 95), "p99": _pct(totals, 99)},
        "latency_model_ms": {"p50": _pct(model_lat, 50), "p95": _pct(model_lat, 95), "p99": _pct(model_lat, 99)},
        "latency_by_level_ms": level_latency,
        "model_calls": len(model_calls),
        "model_unanswered": len(model_calls) - len(answered),
        "input_tokens_total": sum(tokens),
        "input_tokens_per_call": round(sum(tokens) / len(tokens)) if tokens else 0,
        "cost_usd_total": round(total_cost, 6),
        "cost_usd_per_1k_payments": round(1000 * total_cost / n, 4) if n else 0.0,
        "cost_usd_per_model_call": round(total_cost / len(tokens), 6) if tokens else 0.0,
        "expected_pass": [sum(d.decision in i["expected"] for i, d in expected), len(expected)] if expected else None,
        "fraud_not_approved_pct": round(100 * sum(d.decision != "approve" for d in fraud) / len(fraud), 1) if fraud else None,
        "legit_friction_pct": round(100 * sum(d.decision != "approve" for d in legit) / len(legit), 1) if legit else None,
        "by_type": by_type,
        "probability_buckets": {k: buckets.get(k, 0) for k in ("<0.01", "0.01-0.1", "0.1-0.9", "0.9-0.99", ">=0.99")},
        "rows": [
            {"name": i["name"], "label": i.get("label"), "type": item_type(i), "decision": d.decision, "decided_by": d.decided_by,
             "risk": d.risk_score, "total_ms": d.latency_ms["total"], "model_ms": d.latency_ms.get("model"),
             "tokens": d.input_tokens, **_payment(i, d)}
            for i, d in results
        ],
    }


def _payment(item: dict, d: Decision) -> dict:
    """What the results table shows for one payment, and why it was decided that way."""
    c = item["request"]["candidate"]
    expected = item.get("expected")
    return {"description": item.get("description") or item.get("type") or item["name"], "channel": c["channel"],
            "amount": c["amount"], "currency": c.get("currency", "EUR"), "expected": expected,
            "pass": None if not expected else d.decision in expected,
            "reasons": [r.model_dump(mode="json") for r in d.reasons], "model_answers": d.model_answers,
            "history_used": d.history_used, "history_available": d.history_available, "enforced": d.enforced}


async def model_calls(items: list[dict], policy: Policy, modes: list[str]) -> dict[str, int]:
    """How many payments would reach the model under each mode. Routing never depends on the
    model's answer, so an offline dry run (fake backend, no audit) counts them exactly."""
    from .engine import FraudEngine
    reqs = [ScoringRequest.model_validate(i["request"]) for i in benchable(items)]
    out = {}
    for mode in modes:
        engine = FraudEngine(policy, FakeBackend(), None)
        try:
            out[mode] = sum(["model" in (await engine.score(r, routing=mode)).latency_ms for r in reqs])
        finally:
            await engine.aclose()
    return out


def restat(report: dict) -> dict:
    """Recompute the model-call figures of a saved run from its rows. Runs saved before
    `model_unanswered` existed averaged skipped attempts (0 ms, 0 tokens) into them."""
    price = report["price"]
    for m in cells(report):
        if "model_unanswered" in m:
            continue
        attempts = [r for r in m["rows"] if r["tokens"] is not None or r["model_ms"] is not None]
        answered = [r for r in attempts if r["tokens"] is not None]
        tokens = [r["tokens"] for r in answered]
        total = sum(cost_usd(t, price) for t in tokens)
        lat = [r["model_ms"] for r in answered if r["model_ms"] is not None]
        m.update(
            model_unanswered=len(attempts) - len(answered),
            latency_model_ms={"p50": _pct(lat, 50), "p95": _pct(lat, 95), "p99": _pct(lat, 99)},
            input_tokens_per_call=round(sum(tokens) / len(tokens)) if tokens else 0,
            cost_usd_total=round(total, 6),
            cost_usd_per_1k_payments=round(1000 * total / m["n"], 4) if m["n"] else 0.0,
            cost_usd_per_model_call=round(total / len(tokens), 6) if tokens else 0.0,
        )
        m["latency_by_level_ms"]["model"] = {"mean": _mean(lat), "p95": _pct(lat, 95)}
    return report


def save_run(report: dict, runs_dir: Path | None = None) -> Path:
    runs_dir = runs_dir or RUNS_DIR
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{report['id']}.json"
    path.write_text(json.dumps(report, indent=1))
    return path


def list_runs(runs_dir: Path | None = None) -> list[dict]:
    runs_dir = runs_dir or RUNS_DIR
    if not runs_dir.exists():
        return []
    out = []
    for p in sorted(runs_dir.glob("bench_*.json"), reverse=True):
        try:
            r = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        cs = cells(r)
        out.append({"id": p.stem, "started_at": r["started_at"], "backend": r["backend"], "n": r["n"],
                    "modes": list(dict.fromkeys(c["mode"] for c in cs)),
                    "policies": list(dict.fromkeys(c["policy"] for c in cs if c.get("policy"))),
                    "concurrency": r["concurrency"], "dataset": r.get("dataset"),
                    "dataset_title": (r.get("dataset_meta") or {}).get("title"),
                    "history_payments": r.get("history_payments")})
    return out
