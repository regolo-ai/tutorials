"""A labelled sample of IBM TabFormer card transactions, in the engine's request format.

TabFormer (Apache-2.0, https://github.com/IBM/TabFormer) has 24.4M synthetic US card transactions,
2000 users, 1991-2020, with a fraud label. The sample takes candidates from one period (by default
the test period, after 2018), at most one fraud per user so no single card's burst dominates, and
gives each candidate the user's last payments before it as history.

What the format cannot carry, and how it is mapped:
- no coordinates (city, state, zip only): no `location`, so impossible travel is not computed;
- declined attempts ("Errors?") are kept on past payments as `errors`, never on the candidate;
- no device, IP or authentication data: card-not-present payments are marked `sca`, so the PSD2
  check does not turn approvals into step-ups for a reason unrelated to fraud;
- foreign merchants carry a country name in the state column: mapped to ISO codes;
- refunds (negative amounts) are left out; amounts stay in USD.

Run: uv run python -m fraudclef.tabformer data/tabformer/raw/card_transaction.v1.csv --fraud 50 --legit 1000
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import tarfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from . import generator
from .models import ScoringRequest

TZ = ZoneInfo("America/New_York")
RAW_DIR = Path("data/tabformer/raw")
CSV_NAME = "card_transaction.v1.csv"
ARCHIVE_NAME = "transactions.tgz"
# IBM's public Box share of the dataset (the git-lfs copy in the TabFormer repo is no longer served).
BOX_URL = "https://ibm.ent.box.com/index.php?rm=box_download_shared_file&vanity_name=tabformer-data&file_id=f_770766751708"
ARCHIVE_BYTES = 278_576_638
PERIODS = {"train": "1991-2017", "validation": "2018", "test": "2019-2020"}
HISTORY = 30
WINDOW = timedelta(days=180)  # history is looked for in the 180 days before each candidate
# The customer's usual countries: paid in over 90 days ending 30 days before the candidate, so a
# fraud burst in a new country does not make that country look habitual. TabFormer bursts last
# weeks: on the 2018 sample a 7-day gap caught 54% of frauds, 14 days 76%, 30 days 88%.
USUAL_LOOKBACK, USUAL_GAP = timedelta(days=90), timedelta(days=30)
CHANNELS = {"Swipe Transaction": "card_present", "Chip Transaction": "card_present", "Online Transaction": "card_not_present"}
COUNTRIES = {
    "Mexico": "MX", "Italy": "IT", "Canada": "CA", "United Kingdom": "GB", "China": "CN", "Germany": "DE", "France": "FR",
    "India": "IN", "Japan": "JP", "Dominican Republic": "DO", "Taiwan": "TW", "South Korea": "KR", "Spain": "ES",
    "Costa Rica": "CR", "Netherlands": "NL", "Hong Kong": "HK", "Jamaica": "JM", "Brazil": "BR", "Aruba": "AW",
    "Ireland": "IE", "Philippines": "PH", "Czech Republic": "CZ", "Australia": "AU", "Portugal": "PT", "Austria": "AT",
    "Greece": "GR", "Switzerland": "CH", "Israel": "IL", "Belgium": "BE", "Sweden": "SE", "Norway": "NO", "Denmark": "DK",
    "Finland": "FI", "Poland": "PL", "Hungary": "HU", "Turkey": "TR", "Russia": "RU", "Egypt": "EG", "Morocco": "MA",
    "South Africa": "ZA", "Nigeria": "NG", "Kenya": "KE", "Argentina": "AR", "Chile": "CL", "Peru": "PE", "Colombia": "CO",
    "Ecuador": "EC", "Venezuela": "VE", "Panama": "PA", "Guatemala": "GT", "Honduras": "HN", "El Salvador": "SV",
    "Nicaragua": "NI", "Bahamas": "BS", "Barbados": "BB", "Haiti": "HT", "Trinidad and Tobago": "TT", "Thailand": "TH",
    "Vietnam": "VN", "Singapore": "SG", "Malaysia": "MY", "Indonesia": "ID", "Pakistan": "PK", "Bangladesh": "BD",
    "Saudi Arabia": "SA", "United Arab Emirates": "AE", "Qatar": "QA", "Kuwait": "KW", "Jordan": "JO", "Lebanon": "LB",
    "New Zealand": "NZ", "Fiji": "FJ", "Iceland": "IS", "Luxembourg": "LU", "Romania": "RO", "Bulgaria": "BG",
    "Croatia": "HR", "Serbia": "RS", "Ukraine": "UA", "Estonia": "EE", "Latvia": "LV", "Lithuania": "LT", "Slovakia": "SK",
    "Slovenia": "SI", "Malta": "MT", "Cyprus": "CY", "Uruguay": "UY", "Paraguay": "PY", "Bolivia": "BO", "Belize": "BZ",
    "Cuba": "CU", "Iran": "IR", "North Korea": "KP", "Syria": "SY", "Iraq": "IQ", "Algeria": "DZ", "Tunisia": "TN",
    "Ghana": "GH", "Ethiopia": "ET", "Sri Lanka": "LK", "Nepal": "NP", "Cambodia": "KH", "Myanmar": "MM", "Mongolia": "MN",
}


ERRORS = {"Bad PIN": "bad_pin", "Bad CVV": "bad_cvv", "Bad Card Number": "bad_card_number", "Bad Expiration": "bad_expiration",
          "Bad Zipcode": "bad_zipcode", "Insufficient Balance": "insufficient_balance", "Technical Glitch": "technical_glitch"}


def _period(year: int, period: str) -> bool:
    return {"train": year < 2018, "validation": year == 2018, "test": year > 2018}[period]


def _ts(row: list[str]) -> datetime:
    h, m = row[5].split(":")
    return datetime(int(row[2]), int(row[3]), int(row[4]), int(h), int(m), tzinfo=TZ)


def _amount(row: list[str]) -> float:
    return float(row[6].replace("$", ""))


def _tx(row: list[str], tid: str, candidate: bool = False) -> dict:
    channel = CHANNELS[row[7]]
    state = row[10].strip()
    country = None if not state else "US" if len(state) == 2 else COUNTRIES.get(state, state.upper()[:20])
    tx = {"transaction_id": tid, "timestamp": _ts(row).isoformat(), "amount": round(_amount(row), 2), "currency": "USD",
          "channel": channel, "merchant": {"name": f"M{row[8]}", "mcc": row[12], "country": country}}
    if channel == "card_not_present":
        tx["authentication"] = "sca"
    errors = [ERRORS[e.strip()] for e in row[13].split(",") if e.strip() in ERRORS]
    if errors and not candidate:  # the candidate is being decided: its own outcome is not known yet
        tx["errors"] = errors
    return tx


def _describe(row: list[str]) -> str:
    where = "online" if row[7] == "Online Transaction" else f"in {row[9].title()}{', ' + row[10] if row[10] else ''}"
    return f"{row[6]} at merchant {row[8][-6:]} (MCC {row[12]}) {where}"


def build_sample(csv_path: str | Path, n_fraud: int, n_legit: int, period: str = "test", seed: int = 7,
                 progress: Callable[[str, int], None] | None = None) -> tuple[list[dict], dict]:
    """`progress(stage, rows_read)` is called every million rows of each of the two passes."""
    rnd = random.Random(seed)
    # Pass 1: candidates. One random fraud per user (reservoir per user), legit by reservoir sampling.
    fraud_by_user: dict[str, tuple[int, list[str]]] = {}
    seen_fraud: dict[str, int] = defaultdict(int)
    legit: list[list[str]] = []
    n_legit_seen = n_total = n_fraud_total = 0
    with open(csv_path, newline="") as f:
        r = csv.reader(f)
        next(r)
        for k, row in enumerate(r):
            if progress and k % 1_000_000 == 0:
                progress("selecting", k)
            if not _period(int(row[2]), period):
                continue
            n_total += 1
            is_fraud = row[14] == "Yes"
            n_fraud_total += is_fraud
            if _amount(row) <= 0:
                continue
            if is_fraud:
                seen_fraud[row[0]] += 1
                if rnd.random() < 1 / seen_fraud[row[0]]:
                    fraud_by_user[row[0]] = row
            else:
                n_legit_seen += 1
                if len(legit) < n_legit:
                    legit.append(row)
                elif (k := rnd.randrange(n_legit_seen)) < n_legit:
                    legit[k] = row
    users = sorted(fraud_by_user)
    frauds = [fraud_by_user[u] for u in rnd.sample(users, min(n_fraud, len(users)))]
    candidates = [(row, "fraud") for row in frauds] + [(row, "legit") for row in legit]

    # Pass 2: each candidate user's payments in the window before their candidates.
    span: dict[str, tuple[datetime, datetime]] = {}
    for row, _ in candidates:
        t = _ts(row)
        lo, hi = span.get(row[0], (t, t))
        span[row[0]] = (min(lo, t), max(hi, t))
    rows_by_user: dict[str, list[tuple[datetime, list[str]]]] = defaultdict(list)
    with open(csv_path, newline="") as f:
        r = csv.reader(f)
        next(r)
        for k, row in enumerate(r):
            if progress and k % 1_000_000 == 0:
                progress("history", k)
            s = span.get(row[0])
            if not s or not (s[0] - WINDOW).year <= int(row[2]) <= s[1].year:  # cheap filter before parsing dates
                continue
            t = _ts(row)
            if s[0] - WINDOW <= t <= s[1] and _amount(row) > 0:
                rows_by_user[row[0]].append((t, row))
    for rows in rows_by_user.values():
        rows.sort(key=lambda x: x[0])

    items = []
    for i, (row, label) in enumerate(candidates):
        t = _ts(row)
        before = [x for ts, x in rows_by_user[row[0]] if ts < t][-HISTORY:]
        usual = {c for ts, x in rows_by_user[row[0]] if t - USUAL_GAP - USUAL_LOOKBACK <= ts < t - USUAL_GAP
                 if (c := _tx(x, "")["merchant"]["country"])}
        cand = _tx(row, f"tf{i:05d}c", candidate=True)
        req = {"customer": {"id": f"tf-user-{row[0]}", "segment": "retail", "home_country": "US",
                            "usual_countries": sorted(usual)},
               "history": [_tx(x, f"tf{i:05d}h{k:02d}") for k, x in enumerate(before)], "candidate": cand}
        ScoringRequest.model_validate(req)
        kind = ("stolen_card_online" if cand["channel"] == "card_not_present" else "cloned_card") if label == "fraud" \
            else "habitual"
        items.append({"name": f"tabformer_{i:05d}", "label": label, "type": kind, "expected": None,
                      "description": _describe(row), "request": req})
    rnd.shuffle(items)  # benchmarks may take the first N: keep the mix
    meta = {"source": "IBM TabFormer card_transaction.v1.csv", "period": period, "seed": seed,
            "period_transactions": n_total, "period_fraud": n_fraud_total,
            "base_rate": round(n_fraud_total / n_total, 6) if n_total else None,
            "fraud_users_in_period": len(users), "fraud": len(frauds), "legit": len(legit)}
    return items, meta


def save_sample(items: list[dict], info: dict, name: str, title: str, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or generator.GENERATED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps(items))
    counts: dict[str, int] = {}
    for it in items:
        counts[it["type"]] = counts.get(it["type"], 0) + 1
    meta = {"name": name, "title": title, "model": None,
            "how": f"Sampled from IBM TabFormer, {info['period']} period ({PERIODS[info['period']]})",
            "created_at": datetime.now(TZ).isoformat(timespec="seconds"), "requested": len(items), "generated": len(items),
            "failed": [], "history": HISTORY, "vulnerable_pct": 0, "mix": {}, "counts": counts, "repaired": 0,
            "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "tabformer": info}
    (out_dir / f"{name}.meta.json").write_text(json.dumps(meta, indent=1))
    return meta


def extract_csv(archive: Path, dest: Path) -> Path:
    """Extract only the CSV from the archive, with tarfile's safe `data` filter."""
    with tarfile.open(archive, "r:gz") as tar:
        member = next((m for m in tar.getmembers() if Path(m.name).name == CSV_NAME and m.isfile()), None)
        if member is None:
            raise ValueError(f"{CSV_NAME} not found in {archive.name}")
        member.name = CSV_NAME  # flatten any folder in the archive
        tar.extract(member, dest, filter="data")
    return dest / CSV_NAME


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fraudclef.tabformer", description=__doc__.split("\n")[0])
    ap.add_argument("csv")
    ap.add_argument("--fraud", type=int, default=50)
    ap.add_argument("--legit", type=int, default=1000)
    ap.add_argument("--period", choices=["train", "validation", "test"], default="test")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--name", default="tabformer-2019-2020")
    ap.add_argument("--title", default="TabFormer card payments (pilot)")
    args = ap.parse_args(argv)
    items, info = build_sample(args.csv, args.fraud, args.legit, args.period, args.seed)
    save_sample(items, info, args.name, args.title)
    print(json.dumps(info, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
