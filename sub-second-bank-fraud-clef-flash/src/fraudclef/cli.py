"""Command line: score | bench | generate | audit-verify."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import audit as audit_mod
from .benchmark import BenchError, build_engine, run_bench, save_run
from .datagen import random_dataset, write_scenarios
from .models import ScoringRequest
from .policy import PolicyError, load_policy
from .pricing import cost_usd, model_price


def load_items(path: str) -> list[dict]:
    p = Path(path)
    files = sorted(p.glob("*.json")) if p.is_dir() else [p]
    items = []
    for f in files:
        data = json.loads(f.read_text())
        for d in data if isinstance(data, list) else [data]:
            items.append(d if "request" in d else {"name": f.stem, "request": d})
    return items


# ── score ─────────────────────────────────────────────────────────────────────
async def cmd_score(args) -> int:
    failures = 0
    for item in load_items(args.input):
        policy = load_policy(args.policy, item.get("policy_overrides"))
        engine = build_engine(policy, args.backend, args.audit, fail=item.get("simulate_backend_failure", False))
        try:
            req = ScoringRequest.model_validate(item["request"])
            d = await engine.score(req, routing=args.routing or item.get("routing"),
                                   context={"source": "cli-score", "scenario": item.get("name")})
        finally:
            await engine.aclose()
        expected = item.get("expected")
        ok = expected is None or d.decision in expected
        failures += not ok
        if args.json:
            print(d.model_dump_json(indent=2, exclude_none=True))
        else:
            _print_decision(item.get("name", req.candidate.transaction_id), d, expected, ok, args.verbose)
    return 1 if failures else 0


def _ms_or_dash(v) -> str:
    return f"{v:7.1f}ms" if v is not None else "      -  "


def _print_decision(name, d, expected, ok, verbose):
    mark = "" if expected is None else ("PASS" if ok else f"FAIL (expected {'/'.join(expected)})")
    shadow = " [shadow: not enforced]" if not d.enforced else ""
    cost = f" tokens={d.input_tokens} ${cost_usd(d.input_tokens, model_price(d.model or 'clef-flash')):.5f}" if d.input_tokens else ""
    print(f"{name:<34} {d.decision.upper():<8} risk={d.risk_score:.3f} by={d.decided_by:<9} "
          f"total={d.latency_ms.get('total', 0):7.1f}ms model={_ms_or_dash(d.latency_ms.get('model'))}{cost}  {mark}{shadow}")
    for r in d.reasons[: (None if verbose else 3)]:
        val = "" if r.value is None else f" = {r.value}"
        print(f"    - {r.source}:{r.id}{val}" + (f"  ({r.detail})" if r.detail and verbose or r.source in ('rule', 'sca', 'fail_mode', 'override') else ""))


# ── bench ─────────────────────────────────────────────────────────────────────
async def cmd_bench(args) -> int:
    policy = load_policy(args.policy)
    backend = args.backend or policy.model.backend
    try:
        report = await run_bench(load_items(args.dataset), policy, backend, args.routing.split(","),
                                 args.concurrency, args.allow_high_concurrency, args.audit)
    except BenchError as e:
        print(f"bench error: {e}", file=sys.stderr)
        return 2
    report["dataset"] = args.dataset
    print(f"policy {policy.ref}, reading the last {policy.history.payments} past payments")
    for rep in report["modes"].values():
        _print_mode(rep, args.verbose)
    if "agreement" in report:
        ag = report["agreement"]
        a, b = ag["modes"]
        print(f"\nDecision agreement {a} vs {b}: {ag['same']}/{ag['total']} ({ag['same'] / ag['total']:.0%})")
        for row in ag["differences"][:15]:
            print(f"    {row['name']:<34} {a}={row[a]:<8} {b}={row[b]}")
    path = Path(args.out) if args.out else save_run(report)
    if args.out:
        path.write_text(json.dumps(report, indent=1))
    print(f"\nreport written to {path}  (price source: {report['price']['source']})")
    return 0


def _print_mode(rep, verbose):
    print(f"\n=== routing={rep['mode']}  n={rep['n']}  wall={rep['wall_s']}s  throughput={rep['throughput_rps']} req/s")
    print(f"decided_by: {rep['decided_by']}   sent to model: {rep['sent_to_model_pct']}%")
    print(f"decisions:  {rep['decisions']}")
    t, m = rep["latency_total_ms"], rep["latency_model_ms"]
    print(f"latency total ms p50/p95/p99: {t['p50']} / {t['p95']} / {t['p99']}")
    if rep["model_calls"]:
        print(f"latency model ms p50/p95/p99: {m['p50']} / {m['p95']} / {m['p99']}")
        print(f"tokens: {rep['input_tokens_total']} total, {rep['input_tokens_per_call']} per model call   "
              f"cost: ${rep['cost_usd_total']:.4f} total, ${rep['cost_usd_per_1k_payments']:.4f} per 1k payments")
    if rep["expected_pass"]:
        print(f"scenario expectations met: {rep['expected_pass'][0]}/{rep['expected_pass'][1]}")
    if rep["fraud_not_approved_pct"] is not None:
        print(f"fraud not approved: {rep['fraud_not_approved_pct']}%   legit with friction: {rep['legit_friction_pct']}%")
    if rep["model_calls"]:
        print(f"model probability distribution: {rep['probability_buckets']}")
    if verbose:
        for row in rep["rows"]:
            print(f"    {row['name']:<34} {row['decision']:<8} by={row['decided_by']:<9} risk={row['risk']:.3f} tokens={row['tokens']}")


# ── other commands ────────────────────────────────────────────────────────────
def cmd_generate(args) -> int:
    paths = write_scenarios(args.scenarios_dir)
    print(f"wrote {len(paths)} scenarios to {args.scenarios_dir}")
    if args.random:
        out = Path(args.random_out)
        out.write_text(json.dumps(random_dataset(args.random, args.fraud_rate, seed=args.seed), indent=1))
        print(f"wrote {args.random} random requests to {out}")
    return 0


def cmd_audit_verify(args) -> int:
    ok, n, msg = audit_mod.verify(args.log)
    print(f"{'OK' if ok else 'TAMPERED'}: {msg} ({n} records)")
    return 0 if ok else 1


def main(argv=None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="fraudclef", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="score a request or scenario file (or a directory of them)")
    s.add_argument("input")
    s.add_argument("--policy", default="policies/retail-eu.yaml")
    s.add_argument("--backend", choices=["regolo", "fake"])
    s.add_argument("--routing", choices=["cascade", "always", "never"])
    s.add_argument("--audit", default="logs/decisions.jsonl", help="audit log path ('' to disable)")
    s.add_argument("--json", action="store_true")
    s.add_argument("-v", "--verbose", action="store_true")

    b = sub.add_parser("bench", help="latency, routing and grey-zone report over a dataset")
    b.add_argument("--dataset", default="data/scenarios")
    b.add_argument("--policy", default="policies/retail-eu.yaml")
    b.add_argument("--backend", choices=["regolo", "fake"])
    b.add_argument("--routing", default="always,cascade", help="comma-separated modes to compare")
    b.add_argument("--concurrency", type=int, default=1)
    b.add_argument("--allow-high-concurrency", action="store_true")
    b.add_argument("--audit", default="")
    b.add_argument("--out", help="report path (default: logs/bench_runs/bench_<timestamp>.json)")
    b.add_argument("-v", "--verbose", action="store_true")

    g = sub.add_parser("generate", help="write the named scenarios and optionally a random dataset")
    g.add_argument("--scenarios-dir", default="data/scenarios")
    g.add_argument("--random", type=int, default=0, metavar="N")
    g.add_argument("--random-out", default="data/random_dataset.json")
    g.add_argument("--fraud-rate", type=float, default=0.15)
    g.add_argument("--seed", type=int, default=7)

    v = sub.add_parser("audit-verify", help="verify the audit log hash chain")
    v.add_argument("log", nargs="?", default="logs/decisions.jsonl")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "score":
            args.audit = args.audit or None
            return asyncio.run(cmd_score(args))
        if args.cmd == "bench":
            args.audit = args.audit or None
            return asyncio.run(cmd_bench(args))
        if args.cmd == "generate":
            return cmd_generate(args)
        return cmd_audit_verify(args)
    except PolicyError as e:
        print(f"policy error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
