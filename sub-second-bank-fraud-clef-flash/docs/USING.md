# Using fraudclef

This guide explains how to install, run and integrate the engine. It is written for two readers: a consultancy evaluating the approach, and a bank engineer who will run it and wire it to real data. To change *how* payments are judged, read [POLICIES.md](POLICIES.md) next.

- [1. What the engine does](#1-what-the-engine-does)
- [2. Install and start](#2-install-and-start)
- [3. The console](#3-the-console)
- [4. Command line](#4-command-line)
- [5. Input: the scoring request](#5-input-the-scoring-request)
- [6. Output: the decision](#6-output-the-decision)
- [7. Calling the engine from Python](#7-calling-the-engine-from-python)
- [8. Audit log](#8-audit-log)
- [9. Test data](#9-test-data)
- [10. Security and data protection](#10-security-and-data-protection)
- [11. Tests](#11-tests)
- [12. Project layout](#12-project-layout)
- [13. Troubleshooting](#13-troubleshooting)
- [14. What a production deployment adds](#14-what-a-production-deployment-adds)

---

## 1. What the engine does

The engine receives one **candidate payment**, the **customer** and the customer's **past payments**. It returns a decision:

| Decision | Meaning for the customer |
|---|---|
| `approve` | The payment goes through. |
| `step_up` | The customer must confirm, for example with a one-time code or in the app (strong customer authentication). |
| `hold` | The payment is stopped until the bank checks it, for example with a call to the customer. |
| `block` | The payment is refused. |

Each payment goes through these steps. Every threshold and rule comes from the policy.

```
 payment + customer + past payments
        │
        ▼
 1. Features        numbers computed from the history: how unusual the amount is, new device,
        │           new beneficiary, impossible travel, card-testing bursts…   (local, < 1 ms)
        ▼
 2. Hard rules      sanctions, mule accounts, card testing, account takeover, limits.
        │           The first rule that matches decides.                      (local, < 1 ms)
        ▼
 3. Quick score     a weighted sum of the features, 0 to 1. Clearly ordinary payments are
        │           approved here.                                            (local, < 1 ms)
        ▼
 4. Decision model  Clef-Flash on Regolo, only for the uncertain payments, high amounts and
        │           instant transfers. It answers the policy's questions with probabilities.
        ▼                                                                     (~150–500 ms)
 5. Decision        quick score and model answers combined, compared to thresholds; then
        │           overrides, channel limits and the PSD2 exemption check.
        ▼
 6. Audit           a hash-chained record of what was decided, why, and what was sent.
```

"When to ask the decision model" is called **routing**. There are three modes:

| Mode | In the console | What happens |
|---|---|---|
| `cascade` | Only when needed | Rules and the quick score settle the clear cases. The model sees the uncertain ones, plus the amounts and channels the policy says must always be checked. |
| `always` | On every payment | Every payment the hard rules let through goes to the model. |
| `never` | Never | Rules and the quick score only. No call to Regolo. |

Hard rules always run first, in every mode.

---

## 2. Install and start

### Prerequisites

- macOS or Linux, with `curl` and `openssl`.
- [uv](https://docs.astral.sh/uv/), the Python package manager. Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh`. uv installs Python 3.12 and the dependencies itself.
- A Regolo API key, to call the decision model. New accounts can start a free trial at [regolo.ai/pricing](https://regolo.ai/pricing); create the key at [regolo.ai/signup](https://regolo.ai/signup). Without a key, everything except the model calls still works, and `--fake` runs a fully offline demo.

### Start

```bash
./run.sh start
```

The script checks each prerequisite and reports what it finds:

| Check | What it does |
|---|---|
| Tools | Finds `uv` and `curl`. |
| Configuration | Creates `.env` from `.env.example` on the first run, with a random pseudonymisation secret, readable only by you (`chmod 600`). |
| Dependencies | `uv sync`: creates `.venv` and installs the locked versions from `uv.lock`. |
| Policies | Loads and validates every file in `policies/`. |
| Regolo | Checks that `api.regolo.ai` is reachable, that `clef-flash` is listed and that the key is accepted. |
| Data | Generates the test payments if they are missing. |
| Offline tests | Runs the test suite. Nothing is sent to Regolo. |

When the checks pass, the script starts the console on **http://127.0.0.1:8080** and opens the browser.

```bash
./run.sh stop           # stop the console
./run.sh restart        # stop, then start
./run.sh status         # is it running?
./run.sh check          # run the checks only
./run.sh start --fake   # offline demo: a stand-in replaces the model, nothing is sent
./run.sh start --port 9000 --skip-tests --no-open
```

The console log is in `logs/ui.log`.

### Configuration: `.env`

```ini
REGOLO_API_KEY=            # pasted in the console sidebar, or written here
REGOLO_BASE_URL=https://api.regolo.ai
FRAUDCLEF_HMAC_KEY=…       # secret for pseudonymising IBANs, names and device ids
```

`.env` is never committed (it is in `.gitignore`). Changing `FRAUDCLEF_HMAC_KEY` changes every pseudonym, so records written before and after the change can no longer be linked.

---

## 3. The console

The console is a local web page with four tabs and a sidebar. It listens on `127.0.0.1` only, and it has no login.

### Sidebar

- **Regolo API key.** Paste the key and press *Check and save key*. The key is checked with Regolo, then written to `.env`. The console never shows it again. For new users, the box also offers the 30-day trial.
- **Add a dataset.** Opens a dialog with two sources (see [§9](#9-test-data)):
  - *Write with a Regolo model*: a chat model writes fictional customers in a mix of fraud types you choose. The price is shown before it starts.
  - *Sample IBM TabFormer*: downloads the public dataset once (279 MB, 2.35 GB extracted), then takes a labelled sample of the period, number of frauds and genuine payments you choose. Free; it takes about a minute.
- **Services.** Shows whether Regolo is reachable, the key is active, the policies are valid, the audit chain is intact and test data exists. It also shows the live model price.

### Start

Open at `/`. Three steps to get going, each marked done when finished: create a Regolo API key, add it in the sidebar, run a quick comparison. Below them, the latest run: how many payments each level decided, with time and cost.

### Test

The main page. A switch at the top moves between two sections.

**Set up a run**, in four steps:

1. **Policies.** One card per policy, with a short description and three comparable settings. Choose one, or up to three to compare them on the same payments. The page also shows one real rule of the selected policy, as written in the YAML.
2. **Decision model.** Why it is worth asking the model, with figures from your latest run. Then choose one or more of: only when needed, on every payment, never.
3. **Dataset.** The test sets, each showing how it was built and its mix of payment types.
4. **Run.** A table lists every policy-and-routing combination you chose. For each one it shows the **exact number of model calls** and the **cost** at the Regolo price:
   - The call count is exact because the console simulates the routing offline on the chosen payments. This simulation writes nothing to the audit log.
   - Tokens per call come from your latest run of that policy, or are estimated from its number of questions.

   The button shows the total, for example *Run all 24 checks, about $0.0026*.

**Results**:

- **While a run is in progress**, a progress panel says which policy and routing are running and lists the last payments checked: decision, what decided it (rule, quick score or model), time and tokens. The panel disappears when the run ends.
- **The summary**, in plain language: a one-line best trade-off, then one card per combination with:
  - fraud stopped;
  - genuine customers interrupted;
  - average time per payment;
  - cost.
- **Selecting a card** opens its detail:
  - the test set in one line;
  - who decided and the decisions;
  - model calls, with tokens and cost per call;
  - model latency;
  - the result by type of payment.

  *Show every payment* adds the table of individual payments. Click a row to see the reasons and the model's answers.

"Stopped" means *not approved straight away*: a step-up, hold or block.

Every run is saved in `logs/bench_runs/`. Its decisions go to the audit log under the run's id.

### Policies

A YAML editor with syntax highlighting:

- Every edit is validated as you type: schema, weights, thresholds, and a dry run of every rule. Syntax errors point to the line.
- **Save** keeps the previous file in `policies/.history/`. It refuses a change that would break a policy inheriting from this one.
- **New policy** creates a policy that inherits another (you write only the differences), or a full copy.
- **Test this policy** opens the Test page with that policy selected.

[POLICIES.md](POLICIES.md) explains the content.

### Audit log

The audit log page:

- verifies the hash chain;
- lists runs (a benchmark, a set of scenarios, the command line) with their decisions;
- lists individual decisions. Opening one shows what started it, the policy, the reasons, the model's answers, the pseudonymised data sent to Regolo, the computed features and the hashes.

---

## 4. Command line

Everything the console does is also available from the terminal. Prefix each command with `uv run`.

### Score payments

```bash
uv run fraudclef score data/scenarios/04_card_testing.json -v
```

```
04_card_testing                    BLOCK    risk=0.100 by=rule      total=    0.2ms model=      -    PASS
    - rule:card_testing_burst  (Card-testing pattern: burst of micro-charges)
    - prescore:new_merchant = 0.1
```

The input can be:

- a request file (the format in [§5](#5-input-the-scoring-request));
- a scenario file (a request plus `name` and `expected`);
- a JSON list of either;
- a folder of such files.

| Option | Default | Meaning |
|---|---|---|
| `--policy` | `policies/retail-eu.yaml` | Policy file. |
| `--routing` | from the policy | `cascade`, `always` or `never`. |
| `--backend` | from the policy | `regolo`, or `fake` for the offline stand-in. |
| `--audit` | `logs/decisions.jsonl` | Audit log path; `''` disables it. |
| `--json` | off | Print the full decision as JSON. |
| `-v` | off | Print every reason, not just the first three. |

The exit code is 1 if a scenario's decision is not one of its `expected` values. This makes the command usable as a regression check in CI.

### Compare routing modes on a dataset

```bash
uv run fraudclef bench --dataset data/scenarios --routing always,cascade --concurrency 2
uv run fraudclef bench --dataset data/random_dataset.json --policy policies/retail-eu.yaml --backend fake
```

The command prints latency percentiles, the share of payments sent to the model, decisions, tokens and cost for each mode, plus the agreement between modes. It writes the report to `logs/bench_runs/`. Concurrency above 8 is refused unless you pass `--allow-high-concurrency`, because Regolo's shared rate limits are not published.

### Other commands

```bash
uv run fraudclef generate --random 200   # rewrite the 15 named scenarios and 200 random customers
uv run fraudclef audit-verify            # OK: hash chain intact (414 records)
```

---

## 5. Input: the scoring request

A request has three parts: the customer, the past payments and the candidate payment. The format is strict: an unknown field is rejected, so typos surface immediately.

```json
{
  "customer": {
    "id": "c_123",
    "segment": "retail",
    "vulnerable": false,
    "account_age_days": 1450,
    "home_country": "IT",
    "recent_profile_changes": [ { "field": "phone_number", "at": "2026-10-11T19:02:00+02:00" } ]
  },
  "history": [
    { "transaction_id": "h1", "timestamp": "2026-10-01T12:10:00+02:00", "amount": 42.50,
      "channel": "card_present", "merchant": { "name": "ESSELUNGA", "mcc": "5411", "country": "IT" },
      "location": { "lat": 45.46, "lon": 9.19, "country": "IT" } }
  ],
  "candidate": {
    "transaction_id": "tx_0011",
    "timestamp": "2026-10-12T11:00:00+02:00",
    "amount": 4900.00,
    "currency": "EUR",
    "channel": "sepa_instant",
    "device_id": "dev_9f2a",
    "ip_country": "IT",
    "beneficiary": { "iban": "IT40S0542811101000000654321", "name": "Banca Sicurezza Conto", "vop_result": "no_match" },
    "authentication": "sca"
  }
}
```

### Customer

| Field | Type | Notes |
|---|---|---|
| `id` | text | Never sent to the decision model. |
| `segment` | `retail` or `business` | Selects limits and thresholds. |
| `vulnerable` | true/false | Elderly or flagged customers. They get their own, stricter limits and thresholds. |
| `account_age_days` | number | |
| `home_country` | ISO code | Default `IT`. |
| `usual_countries` | list of ISO codes | Optional, from the bank's customer profile: the countries the customer paid in over a longer period, for example 90 days ending 30 days ago. When present, `unusual_country` uses it instead of the recent history. TabFormer samples fill it. |
| `recent_profile_changes` | list of `{field, at}` | Phone, e-mail or password changes. A recent change plus a new device is the classic account-takeover sign. |

### Transaction (used for the candidate and for each past payment)

| Field | Required | Notes |
|---|---|---|
| `transaction_id` | yes | |
| `timestamp` | yes | ISO 8601 **with a timezone offset**. A timestamp without one is rejected. |
| `amount` | yes | Greater than 0. |
| `currency` | no | Default `EUR`. |
| `channel` | yes | `card_present`, `card_not_present`, `atm`, `sepa_instant`, `sepa_credit_transfer` or `sepa_direct_debit`. |
| `merchant` | no | `{name, mcc, country}`. For card payments. |
| `location` | no | `{lat, lon, country}`. For card-present and ATM payments; used for impossible travel. |
| `device_id` | no | For online payments and transfers. |
| `ip_country` | no | |
| `beneficiary` | no | `{iban, name, vop_result}`. For transfers. `vop_result` is the Verification of Payee outcome: `match`, `close_match`, `no_match` or `unavailable`. |
| `mandate` | no | `{creditor_id, mandate_id, signed_at}`. For direct debits. |
| `recurring` | no | true for subscriptions and standing orders. |
| `authentication` | no | `sca`, `none` or `exemption`. Default `none`. |
| `description` | no | Free text. It is never sent to the model. |
| `errors` | no | For past payments only: why an attempt was declined. A list of `bad_pin`, `bad_cvv`, `bad_card_number`, `bad_expiration`, `bad_zipcode`, `insufficient_balance` or `technical_glitch`. The candidate has none: it is being decided. |

The request may carry up to 50 past payments. The engine reads only the most recent ones, as many as the policy's `history.payments` says (10 by default). In production the history would come from the bank's own systems rather than from the request (see [§14](#14-what-a-production-deployment-adds)).

---

## 6. Output: the decision

```json
{
  "transaction_id": "c06",
  "decision": "hold",
  "enforced": true,
  "risk_score": 0.35,
  "prescore": 0.35,
  "model_risk": null,
  "decided_by": "rule",
  "reasons": [
    { "source": "rule", "id": "vop_no_match_large", "detail": "Verification of Payee: beneficiary name does not match the IBAN" },
    { "source": "prescore", "id": "amount_zscore", "value": 0.2 },
    { "source": "prescore", "id": "new_beneficiary", "value": 0.1 }
  ],
  "model_answers": null,
  "sca_exemption": null,
  "input_tokens": null,
  "history_used": 10,
  "history_available": 30,
  "policy": "retail-eu@1 (sha256:08e307540291)",
  "latency_ms": { "features": 0.12, "rules": 0.05, "prescore": 0.01, "total": 0.31 }
}
```

| Field | Meaning |
|---|---|
| `decision` | `approve`, `step_up`, `hold` or `block`. |
| `enforced` | `false` when the policy is in shadow mode: the decision is recorded but not acted upon. |
| `decided_by` | `rule`, `prescore`, `model`, or `fail_mode` (the model did not answer in time, and the channel's fallback decided). |
| `risk_score` | 0 to 1. When the model was asked, this is the quick score and the model's risk combined with the policy's weights. |
| `reasons` | Why, in order of importance. `source` is `rule`, `prescore`, `model`, `override`, `sca`, `fail_mode` or `channel`. |
| `model_answers` | The model's probabilities for each question, when it was asked. |
| `sca_exemption` | `recurring` or `tra` when a remote payment without SCA is approved under a PSD2 exemption. |
| `input_tokens` | Tokens billed by Regolo for this payment. Output is free. |
| `history_used` / `history_available` | Past payments read, out of those received. |
| `policy` | Policy id, version and content hash. It identifies exactly which rules decided. |
| `latency_ms` | Time per step, in milliseconds. |

---

## 7. Calling the engine from Python

```python
import asyncio, json
from dotenv import load_dotenv
from fraudclef.benchmark import build_engine
from fraudclef.models import ScoringRequest
from fraudclef.policy import load_policy

load_dotenv()  # REGOLO_API_KEY and FRAUDCLEF_HMAC_KEY from .env

async def main():
    policy = load_policy("policies/retail-eu.yaml")                       # validated, or PolicyError
    engine = build_engine(policy, backend=None,                     # None: the policy's backend
                          audit_path="logs/decisions.jsonl")        # None: no audit log
    payload = json.load(open("data/scenarios/06_fake_bank_operator.json"))["request"]
    try:
        decision = await engine.score(ScoringRequest.model_validate(payload),
                                      routing=None,                 # or "cascade" | "always" | "never"
                                      context={"source": "my-service"})  # stored in the audit record
    finally:
        await engine.aclose()
    print(decision.decision, decision.decided_by, decision.reasons[0].id)

asyncio.run(main())
```

```
hold rule vop_no_match_large
```

Keep one engine per policy and reuse it. It holds the HTTP connection to Regolo and the circuit breaker, which stops calling the model for a while after repeated timeouts.

The console also exposes an HTTP API on `127.0.0.1` (OpenAPI documentation at `/api/docs`). It has no authentication and serves the demo; it is not an integration interface.

---

## 8. Audit log

Every decision is appended to `logs/decisions.jsonl` as one JSON line. Each record contains:

- **What started it:** the console, a benchmark run, the command line, or your own `context`.
- **A hash of the request as received.**
- **The policy id and its content hash.**
- **The computed features.**
- **The pseudonymised data sent to Regolo**, if the model was asked.
- **The decision.**
- **The hash of the previous record:** editing or deleting a line breaks the chain from that point on.

```bash
uv run fraudclef audit-verify            # OK: hash chain intact (414 records)
```

---

## 9. Test data

| Set | Size | How it was built |
|---|---|---|
| **Payment transactions (mixed)** | 12 + 3 demos | Hand-written in `src/fraudclef/datagen.py`, one case per pattern, each with the decision an analyst expects. The 3 demos simulate a model outage and a shadow-mode policy, and run one at a time. |
| **E-commerce payments** | 31 | The online card payments of the random set. |
| **Card payments in shops** | 158 | The card-present payments of the random set. All genuine: this set measures how often good customers are interrupted. |
| **Retail customers (random)** | 200 | Rule-generated customers with 30 past payments each, about 15% fraud. The fraud is easy to spot on purpose: use this set for volume and speed, not accuracy. |
| **TabFormer card payments** | any | A labelled sample of the IBM TabFormer dataset (24.4M synthetic US card transactions, Apache-2.0). In the console: *Add a dataset* → *Sample IBM TabFormer*, which also downloads it. From the terminal, after placing `card_transaction.v1.csv` in `data/tabformer/raw/`: `uv run python -m fraudclef.tabformer data/tabformer/raw/card_transaction.v1.csv --fraud 50 --legit 1000`. Failed attempts are kept on past payments as `errors`, and each customer gets `usual_countries` from the 90 days ending 30 days before the payment. In its test period (2019–2020) 0.101% of payments are fraud, and every one of them is at a foreign merchant. |
| **Generated sets** | 1–100 | Written by a Regolo chat model in a mix you choose (sidebar, *Generate a test set*). Saved in `data/generated/`. |

Each payment carries a **type**, such as everyday payment, unusual but genuine, card testing, stolen card online, account takeover, impersonation scam or ATM cash-out abroad, and a label, fraud or genuine.

In generated sets, the label is what the model was **asked to write**, not verified fraud.

None of this data is real. To evaluate the engine on the bank's own payments, export them in the request format of [§5](#5-input-the-scoring-request), with known outcomes in `label` or `expected`, and run `fraudclef bench` on the file.

---

## 10. Security and data protection

- **The API key** lives only in `.env` (`chmod 600`, never committed). The console never returns it, and `run.sh` passes it to `curl` on stdin, so it does not appear in the process list.
- **The console** listens on `127.0.0.1` only and has no login. It rejects writes coming from other web origins.
- **Pseudonymisation.** Before data is sent to the model:
  - IBANs, beneficiary names, device ids and mandate ids are replaced by HMAC hashes;
  - merchant names, descriptions, exact coordinates and transaction ids are dropped.

  Both lists are in each policy's `privacy` section.
- **No external calls if forbidden.** With `privacy.allow_external_backend: false`, the engine refuses to start with the Regolo backend.
- **Fail closed.** A rule that cannot be evaluated on a payment results in a step-up with the error recorded. It never results in a silent approval.

---

## 11. Tests

```bash
uv run pytest -q                 # 58 offline tests: no network, no cost
uv run pytest -m live -q         # one live contract test against Regolo (needs the key)
```

The tests cover:

- the named scenarios and their expected decisions;
- policy validation and inheritance;
- the history window;
- the audit chain;
- the circuit breaker;
- pseudonymisation;
- the PSD2 exemptions;
- the console API, including the editor, the key handling, the run estimates and the generated sets.

---

## 12. Project layout

```
policies/            YAML policies (retail-eu, poc, retail-eu-explainable); .history/ keeps previous versions
lists/               mule_ibans.txt and other lists a policy can reference
data/                scenarios/, random_dataset.json, generated/
logs/                decisions.jsonl (audit), bench_runs/ (one JSON per run), ui.log
src/fraudclef/
  models.py          request and decision schemas
  features.py        the features computed from the history
  policy.py          policy schema, inheritance, validation, dry run of every rule
  rules.py           the restricted expression evaluator used by `when`
  engine.py          the pipeline: rules, quick score, routing, model, decision, PSD2, audit
  backends.py        Regolo client, offline stand-in, circuit breaker
  privacy.py         HMAC pseudonymisation
  audit.py           hash-chained log and its verification
  benchmark.py       runs and comparisons, shared by CLI and console
  datagen.py         named scenarios and random customers
  generator.py       test sets written by a Regolo chat model
  pricing.py         live model price from the Regolo catalogue
  cli.py             fraudclef score | bench | generate | audit-verify
  web/               the console (FastAPI + static page)
tests/
run.sh               check | start | stop | restart | status
```

---

## 13. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `uv not found` | Install uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh`. |
| `API key rejected by Regolo (HTTP 401)` | The key is wrong or revoked. Paste a new one in the sidebar. |
| `api.regolo.ai unreachable` | Network or proxy. Use `./run.sh start --fake` to work offline. |
| `invalid policy …` at start | A policy file does not validate. The message names the field. See [POLICIES.md §9](POLICIES.md#9-validation-and-error-messages). |
| Many decisions by `fail_mode` | The model did not answer within the policy's timeout. `retail-eu` waits only 150 ms on card payments, which the shared API cannot meet. Use `retail-eu`. |
| `FRAUDCLEF_HMAC_KEY not set` warning | Run `./run.sh check` once: it creates `.env` with a random secret. |
| The console looks unstyled after an update | Reload the page. The page asks the browser to revalidate its files. |
| Port 8080 already in use | `./run.sh start --port 9000`. |

---

## 14. What a production deployment adds

This proof of concept deliberately leaves out several things a bank deployment would need:

- **History from the bank's systems.** Read it from a feature store, not from the request.
- **Dedicated model capacity**, in the bank's region. Card-authorisation latency needs it.
- **Authentication and authorisation** on any API.
- **A policy release process.** A policy change should go through review, a change ticket and a second approver. The policy already records these (`governance`), and the engine refuses a policy whose author and approver are the same person.
- **Monitoring:**
  - decision mix;
  - model latency and timeouts;
  - fail-mode rate;
  - drift of the features.
- **Validation of the model on real, labelled payments**, by Model Risk and Compliance.

[GUIDE.md](../GUIDE.md) §9 discusses volumes, GPU sizing and the remaining gaps.
