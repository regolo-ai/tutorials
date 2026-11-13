"""Test payments written by a chat model on Regolo, in a mix of payment types chosen by the user.

The model never writes the engine's schema directly: it returns a compact format (minutes ago,
city key, device "home"/"new", beneficiary and creditor names), and this module turns it into a
validated ScoringRequest: timestamps, coordinates, IBANs, mandates and device ids are filled in
deterministically. Each item's label and expected decisions come from the type that was asked
for, never from the model: they are what the item is meant to be, not verified ground truth."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import httpx

from .datagen import CET, NOW
from .models import ScoringRequest

GENERATED_DIR = Path("data/generated")
NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
MAX_ITEMS = 100
FRAUD_EXPECTED = ["step_up", "hold", "block"]

# What the user can mix. `brief` goes into the prompt; `label`/`expected` into the dataset.
TYPES: dict[str, dict[str, Any]] = {
    "habitual": {
        "title": "Everyday payment", "label": "legit", "expected": ["approve"],
        "brief": "A normal payment, consistent with the history: a merchant or category the customer already uses, "
                 "a usual amount, in the home city, on the home device.",
    },
    "unusual_legit": {
        "title": "Unusual but genuine", "label": "legit", "expected": ["approve", "step_up"],
        "brief": "A genuine payment that looks unusual: card present while travelling abroad, a one-off larger "
                 "purchase at a new merchant, or a first transfer to a family member. Mixed signals, no fraud.",
    },
    "card_testing": {
        "title": "Card testing", "label": "fraud", "expected": FRAUD_EXPECTED,
        "brief": "A fraudster tests a stolen card: the history ends with 4 to 6 card_not_present charges of 0.50-2.00 "
                 "EUR at unknown online merchants in the last 10 minutes, from a new device and a foreign IP; the "
                 "candidate is another small online charge like those.",
    },
    "stolen_card_online": {
        "title": "Stolen card online", "label": "fraud", "expected": FRAUD_EXPECTED,
        "brief": "A card_not_present purchase far above the customer's usual amounts, at a new merchant in electronics "
                 "(mcc 5732), jewellery (5944) or crypto (6051), from a new device and a foreign IP, at an unusual hour.",
    },
    "account_takeover": {
        "title": "Account takeover", "label": "fraud", "expected": FRAUD_EXPECTED,
        "brief": "The phone number or e-mail on the account changed a few hours ago; the candidate is a large "
                 "sepa_instant transfer to a beneficiary never paid before, often with a foreign IBAN, from a new device.",
    },
    "impersonation_scam": {
        "title": "Impersonation scam", "label": "fraud", "expected": FRAUD_EXPECTED,
        "brief": "Someone posing as the bank or the police convinces the customer to move money: the customer, on the "
                 "home device, sends a large sepa_instant or sepa_credit_transfer to a new beneficiary; Verification "
                 "of Payee says no_match or close_match.",
    },
    "atm_cashout": {
        "title": "ATM cash-out abroad", "label": "fraud", "expected": FRAUD_EXPECTED,
        "brief": "A cloned card: a card_present payment in the home city less than an hour ago, then an atm "
                 "withdrawal of 300-1000 EUR in a foreign city that cannot be reached in that time.",
    },
    "rogue_direct_debit": {
        "title": "Unknown direct debit", "label": "fraud", "expected": FRAUD_EXPECTED,
        "brief": "A sepa_direct_debit from a creditor never seen before, with a mandate signed today, for an amount "
                 "much higher than the customer's usual direct debits.",
    },
}

CITIES: dict[str, dict[str, Any]] = {
    "milan": {"lat": 45.4642, "lon": 9.19, "country": "IT"}, "rome": {"lat": 41.9028, "lon": 12.4964, "country": "IT"},
    "naples": {"lat": 40.8518, "lon": 14.2681, "country": "IT"}, "turin": {"lat": 45.0703, "lon": 7.6869, "country": "IT"},
    "bologna": {"lat": 44.4949, "lon": 11.3426, "country": "IT"}, "madrid": {"lat": 40.4168, "lon": -3.7038, "country": "ES"},
    "barcelona": {"lat": 41.3874, "lon": 2.1686, "country": "ES"}, "paris": {"lat": 48.8566, "lon": 2.3522, "country": "FR"},
    "lyon": {"lat": 45.764, "lon": 4.8357, "country": "FR"}, "berlin": {"lat": 52.52, "lon": 13.405, "country": "DE"},
    "munich": {"lat": 48.1351, "lon": 11.582, "country": "DE"}, "amsterdam": {"lat": 52.3676, "lon": 4.9041, "country": "NL"},
    "brussels": {"lat": 50.8503, "lon": 4.3517, "country": "BE"}, "vienna": {"lat": 48.2082, "lon": 16.3738, "country": "AT"},
    "lisbon": {"lat": 38.7223, "lon": -9.1393, "country": "PT"}, "dublin": {"lat": 53.3498, "lon": -6.2603, "country": "IE"},
    "bucharest": {"lat": 44.4268, "lon": 26.1025, "country": "RO"}, "sofia": {"lat": 42.6977, "lon": 23.3219, "country": "BG"},
    "vilnius": {"lat": 54.6872, "lon": 25.2797, "country": "LT"}, "london": {"lat": 51.5072, "lon": -0.1276, "country": "GB"},
    "dubai": {"lat": 25.2048, "lon": 55.2708, "country": "AE"}, "lagos": {"lat": 6.5244, "lon": 3.3792, "country": "NG"},
}
HOME_CITIES = ["milan", "rome", "naples", "turin", "bologna", "madrid", "barcelona", "paris", "lyon", "berlin",
               "munich", "amsterdam", "vienna", "lisbon", "dublin"]
CHANNELS = ["card_present", "card_not_present", "atm", "sepa_instant", "sepa_credit_transfer", "sepa_direct_debit"]

SYSTEM_PROMPT = f"""You write realistic synthetic bank payments for testing a fraud engine. Reply with one JSON object only.

Shape:
{{
  "description": "one English sentence describing this customer and the new payment",
  "customer": {{"segment": "retail" | "business", "account_age_days": int}},
  "profile_change": null | {{"field": "phone" | "email" | "address", "hours_ago": number}},
  "history": [payment, ...],      // past payments, oldest first
  "candidate": payment            // the new payment to check, minutes_ago = 0
}}
payment = {{
  "minutes_ago": int,             // minutes before the candidate; history values > 0
  "amount": number,               // EUR, > 0
  "channel": one of {CHANNELS},
  "merchant": string | null,      // card and atm payments: merchant or bank name
  "mcc": "4 digits" | null,       // card payments: ISO 18245 merchant category code
  "city": string | null,          // card_present and atm: one of {sorted(CITIES)}
  "country": "ISO2" | null,       // card_not_present: merchant country
  "device": "home" | "new" | null,  // remote payments: the customer's usual device or a new one
  "ip_country": "ISO2" | null,    // remote payments
  "authentication": "sca" | "none" | "exemption",
  "beneficiary": null | {{"name": string, "iban_country": "ISO2", "vop": "match" | "close_match" | "no_match" | "unavailable"}},
  "creditor": null | {{"name": string, "mandate_signed_days_ago": int}},   // sepa_direct_debit only
  "recurring": bool               // subscriptions, rent, utilities
}}
Rules: transfers (sepa_instant, sepa_credit_transfer) need a beneficiary; direct debits need a creditor. The same
beneficiary or creditor keeps the same name across payments. Spread the history over the last 30-60 days with the
customer's real habits (groceries, fuel, restaurants, rent, utilities, subscriptions). No markdown, no comments."""


class GenerationError(Exception):
    pass


# ── planning ──────────────────────────────────────────────────────────────────
def allocate(mix: dict[str, float], n: int) -> list[str]:
    """Exact counts from percentages (largest remainder), then a stable shuffle."""
    mix = {k: v for k, v in mix.items() if v > 0}
    unknown = set(mix) - set(TYPES)
    if unknown:
        raise GenerationError(f"unknown payment types: {', '.join(sorted(unknown))}")
    total = sum(mix.values())
    if not mix or total <= 0:
        raise GenerationError("choose at least one payment type")
    exact = {k: n * v / total for k, v in mix.items()}
    counts = {k: int(x) for k, x in exact.items()}
    for k in sorted(exact, key=lambda k: exact[k] - counts[k], reverse=True)[: n - sum(counts.values())]:
        counts[k] += 1
    plan = [k for k in TYPES if k in counts for _ in range(counts[k])]
    random.Random(n * 7919 + len(plan)).shuffle(plan)
    return plan


def estimate(n: int, history: int, price: dict) -> dict:
    """Rough cost before running, from a measured set (mistral-small-4-119b, 13 Oct 2026):
    ~750 prompt tokens per customer, ~100 output tokens per payment written."""
    tin, tout = 750 * n, (100 * (history + 1) + 80) * n
    return {"input_tokens": tin, "output_tokens": tout,
            "usd": round(tin * price["input"] + tout * price["output"], 4)}


# ── Regolo chat models ────────────────────────────────────────────────────────
def _base() -> str:
    return os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai")


async def chat_models() -> list[dict]:
    """Chat models the key can use, with prices. clef-flash is the decision model, not a writer."""
    key = os.environ.get("REGOLO_API_KEY")
    if not key:
        raise GenerationError("add your Regolo API key first")
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{_base()}/model_group/info", headers={"Authorization": f"Bearer {key}"})
    if r.status_code != 200:
        raise GenerationError(f"Regolo refused the model list (HTTP {r.status_code})")
    out = []
    for e in r.json().get("data", []):
        if e.get("mode") != "chat" or e.get("model_group") == "clef-flash":
            continue
        out.append({"id": e["model_group"], "input": float(e.get("input_cost_per_token") or 0),
                    "output": float(e.get("output_cost_per_token") or 0),
                    "max_input_tokens": e.get("max_input_tokens")})
    return sorted(out, key=lambda m: m["id"])


async def chat_json(model: str, messages: list[dict], timeout_s: float = 120) -> tuple[dict, dict]:
    """One chat completion that must return a JSON object. Returns (object, usage)."""
    key = os.environ.get("REGOLO_API_KEY")
    async with httpx.AsyncClient(timeout=timeout_s) as c:
        r = await c.post(f"{_base()}/v1/chat/completions", headers={"Authorization": f"Bearer {key}"},
                         json={"model": model, "messages": messages, "temperature": 0.8,
                               "response_format": {"type": "json_object"}})
    if r.status_code != 200:
        raise GenerationError(f"{model}: HTTP {r.status_code} {r.text[:200]}")
    body = r.json()
    text = (body["choices"][0]["message"].get("content") or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text), body.get("usage") or {}
    except json.JSONDecodeError as e:
        raise GenerationError(f"not JSON: {e}") from e


# ── compact format → ScoringRequest ───────────────────────────────────────────
def _digits(seed: str, n: int) -> str:
    return str(int(hashlib.sha256(seed.encode()).hexdigest(), 16))[:n].rjust(n, "0")


def _iban(country: str, name: str) -> str:
    country = (country or "IT").upper()[:2]
    return f"{country}{_digits('chk' + name, 2)}X{_digits(country + name, 22)}"


def to_request(raw: dict, cust_id: str, home: str) -> dict:
    """Build the engine's request from the model's compact output. Raises on missing pieces."""
    home_city = CITIES[home]
    devices: dict[str, str] = {}

    def payment(p: dict, tid: str) -> dict:
        ch = p["channel"]
        if ch not in CHANNELS:
            raise ValueError(f"unknown channel {ch!r}")
        minutes = max(0, int(p.get("minutes_ago") or 0))
        tx: dict[str, Any] = {"transaction_id": tid, "timestamp": (NOW - timedelta(minutes=minutes)).astimezone(CET).isoformat(),
                              "amount": round(float(p["amount"]), 2), "channel": ch, "recurring": bool(p.get("recurring")),
                              "authentication": p.get("authentication") if p.get("authentication") in ("sca", "none", "exemption") else "none"}
        city = CITIES.get(str(p.get("city") or "").lower())
        if ch in ("card_present", "atm"):
            city = city or home_city
            tx["location"] = dict(city)
        if ch in ("card_present", "card_not_present", "atm") or p.get("merchant"):
            country = (city or {}).get("country") or (p.get("country") or home_city["country"])
            tx["merchant"] = {"name": p.get("merchant") or ("ATM" if ch == "atm" else "MERCHANT"),
                              "mcc": str(p["mcc"])[:4] if p.get("mcc") else ("6011" if ch == "atm" else None),
                              "country": str(country).upper()[:2]}
        if ch not in ("card_present", "atm", "sepa_direct_debit"):
            label = p.get("device") or "home"
            devices.setdefault(label, f"dev-{cust_id}-{label}" if label == "home" else f"dev-{cust_id}-{label}-{len(devices)}")
            tx["device_id"] = devices[label]
            tx["ip_country"] = str(p.get("ip_country") or home_city["country"]).upper()[:2]
        if ch in ("sepa_instant", "sepa_credit_transfer"):
            b = p.get("beneficiary") or {"name": "Unknown beneficiary", "iban_country": home_city["country"]}
            vop = b.get("vop") if b.get("vop") in ("match", "close_match", "no_match", "unavailable") else "match"
            tx["beneficiary"] = {"iban": _iban(b.get("iban_country"), b["name"]), "name": b["name"], "vop_result": vop}
        if ch == "sepa_direct_debit":
            cr = p.get("creditor") or {"name": "Unknown creditor", "mandate_signed_days_ago": 0}
            signed = NOW - timedelta(days=max(0, int(cr.get("mandate_signed_days_ago") or 0)), hours=1)
            tx["mandate"] = {"creditor_id": f"{home_city['country']}{_digits(cr['name'], 2)}ZZZ{_digits('c' + cr['name'], 11)}",
                             "mandate_id": f"MND-{_digits('m' + cr['name'], 8)}", "signed_at": signed.astimezone(CET).isoformat()}
        return tx

    history = [payment(p, f"{cust_id}-h{i:02d}") for i, p in enumerate(raw.get("history") or [])]
    candidate = payment({**raw["candidate"], "minutes_ago": 0}, f"{cust_id}-c")
    customer = raw.get("customer") or {}
    change = raw.get("profile_change")
    req = {
        "customer": {
            "id": cust_id, "segment": customer.get("segment") if customer.get("segment") in ("retail", "business") else "retail",
            "account_age_days": max(0, int(customer.get("account_age_days") or 900)), "home_country": home_city["country"],
            "recent_profile_changes": [{"field": str(change.get("field") or "phone"),
                                        "at": (NOW - timedelta(hours=float(change.get("hours_ago") or 1))).astimezone(CET).isoformat()}]
            if isinstance(change, dict) else [],
        },
        "history": history[-50:],
        "candidate": candidate,
    }
    ScoringRequest.model_validate(req)  # raises with a readable message
    return req


# ── one item, with one repair attempt ─────────────────────────────────────────
async def generate_item(model: str, kind: str, index: int, history: int, vulnerable: bool, seed: int) -> dict:
    rnd = random.Random(seed * 1_000_003 + index)
    home = rnd.choice(HOME_CITIES)
    cust_id = f"g{seed % 1000:03d}-{index:03d}"
    user = (f"Payment type to write: {TYPES[kind]['title']}. {TYPES[kind]['brief']}\n"
            f"The customer lives in {home} ({CITIES[home]['country']}). Write exactly {history} past payments, "
            f"then the candidate. Vary names, merchants and amounts; this is customer #{index} of a set.")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}
    t0 = time.perf_counter()
    last_error = ""
    for attempt in range(2):
        try:
            raw, usage = await chat_json(model, messages)
            for k in usage_total:
                usage_total[k] += int(usage.get(k) or 0)
            req = to_request(raw, cust_id, home)
            req["customer"]["vulnerable"] = vulnerable
            return {"name": f"{index:03d}_{kind}", "description": str(raw.get("description") or TYPES[kind]["title"])[:240],
                    "type": kind, "label": TYPES[kind]["label"], "expected": TYPES[kind]["expected"], "request": req,
                    "_usage": usage_total, "_seconds": round(time.perf_counter() - t0, 2), "_attempts": attempt + 1}
        except GenerationError as e:
            last_error = str(e)
            if "HTTP" in last_error:
                break
        except Exception as e:  # validation or missing fields: ask once for a fix
            last_error = f"{type(e).__name__}: {e}"[:600]
            messages += [{"role": "assistant", "content": json.dumps(raw)[:6000] if "raw" in locals() else ""},
                         {"role": "user", "content": f"That JSON is not valid: {last_error}. Return the corrected object only."}]
    return {"_error": last_error, "_usage": usage_total, "_seconds": round(time.perf_counter() - t0, 2), "type": kind}


async def generate_set(
    name: str, model: str, mix: dict[str, float], n: int, history: int = 12, vulnerable_pct: float = 5,
    concurrency: int = 4, progress: Callable[[int, int], None] | None = None, out_dir: Path | None = None,
    title: str = "",
) -> dict:
    if not NAME.match(name):
        raise GenerationError("name: 1-40 lowercase letters, digits, '-' or '_'")
    if not 1 <= n <= MAX_ITEMS:
        raise GenerationError(f"between 1 and {MAX_ITEMS} payments")
    out_dir = out_dir or GENERATED_DIR
    models = {m["id"]: m for m in await chat_models()}
    if model not in models:
        raise GenerationError(f"model '{model}' is not available to this key")
    price = models[model]
    plan = allocate(mix, n)
    seed = int(_digits(name + model, 6))
    vulnerable = {i for i in range(n) if random.Random(seed + i).random() * 100 < vulnerable_pct}
    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def one(i: int, kind: str) -> dict:
        nonlocal done
        async with sem:
            item = await generate_item(model, kind, i + 1, history, i in vulnerable, seed)
        done += 1
        if progress:
            progress(done, n)
        return item

    t0 = time.perf_counter()
    results = await asyncio.gather(*(one(i, k) for i, k in enumerate(plan)))
    wall = time.perf_counter() - t0
    items = [r for r in results if "_error" not in r]
    failed = [{"type": r["type"], "error": r["_error"]} for r in results if "_error" in r]
    tin = sum(r["_usage"]["prompt_tokens"] for r in results)
    tout = sum(r["_usage"]["completion_tokens"] for r in results)
    meta = {
        "name": name, "title": title or name, "model": model, "created_at": datetime.now(CET).isoformat(timespec="seconds"),
        "requested": n, "generated": len(items), "failed": failed, "history": history, "vulnerable_pct": vulnerable_pct,
        "mix": {k: v for k, v in mix.items() if v > 0}, "counts": {k: plan.count(k) for k in dict.fromkeys(plan)},
        "repaired": sum(1 for r in items if r["_attempts"] > 1),
        "input_tokens": tin, "output_tokens": tout, "cost_usd": round(tin * price["input"] + tout * price["output"], 5),
        "wall_s": round(wall, 1), "seconds_per_item": round(sum(r["_seconds"] for r in results) / len(results), 2),
        "concurrency": concurrency,
    }
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in items]
    if clean:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{name}.json").write_text(json.dumps(clean, indent=1))
        (out_dir / f"{name}.meta.json").write_text(json.dumps(meta, indent=1))
    return meta


def list_sets(out_dir: Path | None = None) -> list[dict]:
    out_dir = out_dir or GENERATED_DIR
    out = []
    for p in sorted(out_dir.glob("*.meta.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    return out
