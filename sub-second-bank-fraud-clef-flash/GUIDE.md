# Sub-second bank fraud detection with Clef-Flash on Regolo

> **Status:** v4, reference engine implemented and run against Regolo (12 Oct 2026). Results are in §7.3 and §10.
> The policy files in `policies/` are the source of truth; the YAML excerpts below explain them.
> To run and integrate the engine, read [docs/USING.md](docs/USING.md); to write or change policies, [docs/POLICIES.md](docs/POLICIES.md). This guide holds the design choices, measurements and sizing.

## 0. Quickstart

```bash
./run.sh start              # checks everything, starts the console, opens http://127.0.0.1:8080
```

On the first start `run.sh` creates `.env` from `.env.example` with a random `FRAUDCLEF_HMAC_KEY`. Paste your Regolo API key in the console sidebar: the console checks it with Regolo and saves it in `.env` (mode 600). New users can start from the 30-day free trial linked in the same box ([regolo.ai/pricing](https://regolo.ai/pricing)).

`run.sh` commands: `check` (prerequisites only), `start`, `stop`, `restart`, `status`. Options: `--skip-tests`, `--no-open`, `--port N`, `--fake` (offline backend, no Regolo calls).

`./run.sh check` verifies, in order:
1. `uv` and `curl` are installed;
2. `.env` exists (created if missing); warns if `REGOLO_API_KEY` or `FRAUDCLEF_HMAC_KEY` is not set;
3. dependencies are in sync;
4. all policies load and validate;
5. Regolo is reachable and lists `clef-flash`; if a key is set, Regolo accepts it (a missing or rejected key is a warning: fix it in the sidebar);
6. scenario and random data exist (generated if missing);
7. offline tests pass;
8. the port is free.

The console binds to `127.0.0.1` only: it has no authentication. The API key goes from the browser to `.env` once and is never sent back. Requests that write (policies, key) must come from the console itself: other origins get 403.

The same operations are available from the command line:

```bash
uv run fraudclef score data/scenarios --backend regolo
uv run fraudclef bench --dataset data/random_dataset.json --backend regolo --routing always,cascade --concurrency 4
uv run fraudclef audit-verify logs/decisions.jsonl
uv run pytest            # offline tests (fake backend)
uv run pytest -m live    # contract test against the real Regolo API
```

### The console

| View | What it shows |
|---|---|
| Sidebar (every page) | regolo.ai account box: the 30-day free trial for new users and a field to paste the API key. Once a valid key is saved, the trial offer disappears and only the key box stays. Below it, service status: Regolo reachable and `clef-flash` listed, key active, policies valid, audit chain intact, test data, live price. An **Add a dataset** button opens a dialog with two sources: a Regolo model writes a set (§8.1), or a labelled sample is taken from IBM TabFormer |
| **Start** | Served at `/`. What the console does and three steps (create a Regolo API key, add it, run a quick comparison), each marked when done. Then the latest benchmark: the cascade band, and time, cost and performance figures |
| **Test** | One page with two sections, switched at the top. **Set up a run** is a four-step wizard. 1, **Policies**: one real rule of the first selected policy in one line, then a card per policy (one-sentence description; model wait on cards, questions to Clef-Flash, past payments read); pick one, or up to three to compare. 2, **Decision model** (Clef-Flash on Regolo): why it is worth asking (reads the customer's history as a whole, graded risk instead of yes/no, speed and cost per 1,000 payments from the latest run, no training, pseudonymised input), then only when needed (cascade), on every payment, never; the policy's own setting is marked, and several can be compared. Hard rules always decide first. 3, **Dataset**: *Payment transactions (mixed)* (hand-written), *E-commerce payments* and *Card payments in shops* (the random customers by channel), *Retail customers (random)* and generated sets, each with its make-up by type. 4, **Run**: every combination with the exact number of calls to Clef-Flash (routing is simulated offline on the chosen payments, no audit record written), tokens per call from the latest run of that policy (or estimated from its questions) and the cost at the Regolo price; the button reads *Run all N checks, about $X*. No "free" label: Regolo's documented API has no endpoint for trial or subscription status. **Results**: a progress panel says which policy and setting is running and lists the last payments checked (decision, who decided, time, tokens), and disappears when the run ends; then a one-line best trade-off naming the set, one card per setting (fraud stopped, genuine customers interrupted, average time per payment, cost). Selecting a card opens that setting's detail: the set in one line (size, share of fraud, history, how it was built, when and how it was run, its make-up as a bar), who decided, the decisions, calls to the decision model with tokens and cost per call, its typical and slow-end wait, the whole-set time, the cost per million payments, and each type of payment; *Show every payment* adds the table of that setting's payments, each opening its reasons and the model's answers. For the hand-written set, the three outage and shadow demos run one at a time there. Previous runs are listed at the bottom. Each run is saved in `logs/bench_runs/` and its decisions go to the audit log under the run id. Old links `#scenarios` and `#benchmark` open this page |
| **Policies** | YAML editor with syntax highlighting. Every edit is checked as you type (schema, governance, weights, thresholds and a dry run of every rule); syntax errors point to the line. Saving keeps the previous file in `policies/.history/` and is refused if it breaks a policy that extends this one. **New policy** creates one that inherits another (only the differences) or a full copy: this is how the engine is adapted to another kind of risk |
| **Audit log** | Hash-chain verification, then the runs (benchmark, "Run all scenarios", single runs, command line) with their decisions. Opening a decision shows what started it, the reasons, Clef's answers, the pseudonymised state sent to Regolo, the features and the hashes |

What a policy can and cannot change: rules, pre-score weights, routing, the questions to Clef-Flash (instructions and options), thresholds, overrides, fail modes, privacy and audit settings are YAML. The transaction format and the computed features are code (`models.py`, `features.py`): adapting the engine to a different kind of event starts there.

### How to read the benchmark

| Question | Figure | Where it comes from |
|---|---|---|
| **How long?** | Per-payment median and 95th percentile; model call median / 95th / 99th; features + rules + pre-score mean | `latency_ms` measured inside the engine for every decision |
| **How much?** | Input tokens per model call; cost per call, per 1,000 and per million payments | Regolo's `usage.input_tokens` × the price read live from `/model_group/info` (output tokens are free) |
| **How well?** | Throughput; share sent to the model; scenario expectations met; synthetic fraud not approved; legit payments with friction; agreement between modes; share of graded (0.1–0.9) model probabilities | Decisions compared with each item's `expected` or `label` |

Read the numbers with these limits:
- Latency includes internet round trips to the shared Regolo API.
- "Fraud not approved" on synthetic data is not a real-world accuracy figure.
- A payment counted under "Fail mode" means Regolo did not answer within the timeout, or the circuit breaker had opened after earlier timeouts and the call was skipped. That is a resilience event, not a model decision. Model latency, tokens and cost per call are computed on answered calls only; unanswered attempts are counted separately.
- `retail-eu.yaml` opens the breaker when 20% of at least 5 calls in 30 s fail: on the shared API one slow call in five is enough. That is the production setting, kept on purpose.

## 1. Goal

Given a **candidate transaction** and the customer's **recent transactions** (JSON; the policy sets how many are read, 10 by default), return in under one second:

- a **decision**: `approve` / `step_up` (SCA, OTP, in-app confirmation, callback) / `hold` (suspend for manual review) / `block`;
- a **risk score** and **reasons** (which signals and rules contributed);
- all driven by a **configurable YAML security policy**, versioned and approved, with no retraining.

Deliverable: a **reference engine** as a Python library + CLI (`fraudclef`). The decision model runs on **Regolo** (EU-hosted): `POST https://api.regolo.ai/v1/systemone`, model `clef-flash`. Local execution was dropped from scope (§7.2).

## 2. Why Clef-Flash

**Clef-Flash** (Cloudflare, October 2026, Apache-2.0) is a 9B-parameter *decision model* fine-tuned from Qwen3.5-9B. It **does not generate text**. It takes a `state` (text or JSON) and a schema of typed `questions`, and returns **a probability for every allowed option of every question in a single forward pass**. On Regolo, billed input tokens grow with the number of questions (§7.3), so each question is not free.

| Type | Meaning | Output |
|---|---|---|
| `noul` | true/false | probability of true |
| `choice` | one of named options | `choice`, `confidence`, `probabilities` |
| `score` | ordered scale 0..n | expected `score`, `confidence`, `legend`, `probabilities` |

Vendor latency: **median 38.8 ms, p95 122.4 ms on an H200**. Our own measurement through Regolo is in §7.3.

Known weaknesses (vendor benchmarks): arithmetic (GSM8K 67.3) and complex reasoning. So **code computes the numbers and the model only judges them** (§4.3).

## 3. Architecture: a three-level cascade

### 3.1 What "cascade" means

A cascade orders the checks **from cheapest to most expensive**. Each level decides only the cases it is sure about and passes the rest to the next level:

1. **Hard rules** (microseconds): clear-cut cases such as a sanctioned country, a known mule account or impossible travel. Decided immediately.
2. **Pre-score** (microseconds): a weighted score over the computed features. Clearly normal transactions (the vast majority: groceries, usual bills) are approved here. Clearly extreme ones are blocked.
3. **Clef-Flash** (tens to hundreds of ms, on a GPU): only the **grey zone**, where judgement is needed. It also always sees high amounts and critical channels (instant transfers).

The model is the most expensive and slowest component, so it gets only the cases where it adds value. In the reference engine the routing mode is a switch, so the setups can be compared on the same data (§10):
- `cascade`: rules → pre-score gate → model for the grey zone;
- `always`: rules still decide first; only the pre-score gate is bypassed, so every request that no rule settles goes to the model;
- `never`: rules + pre-score thresholds, no model.

### 3.2 Pipeline

```
 request: candidate + history (10 tx)
            │
            ▼
 ┌──────────────────────────────┐
 │ 0. Validation + privacy      │  Pydantic schema, normalisation,
 │                              │  pseudonymisation (IBAN/PAN/names → HMAC)
 └──────────────┬───────────────┘
                ▼
 ┌──────────────────────────────┐
 │ 1. Feature engineering       │  z-score, velocity, geo, novelty…  (< 1 ms)
 └──────────────┬───────────────┘
                ▼
 ┌──────────────────────────────┐
 │ 2. Hard rules (policy)       │  sanctions, mules, limits, SCA exemptions
 └──────────────┬───────────────┘
                ▼
 ┌──────────────────────────────┐
 │ 3. Pre-score                 │  weighted features (reference engine) → trained GBDT (prod)
 └───────┬───────────┬──────────┘
     low │           │ grey zone / high amount / critical channel
 approve ◄           ▼
         ┌──────────────────────────────┐
         │ 4. Clef-Flash /v1/systemone  │  Regolo
         │    questions from the policy │  timeout + circuit breaker
         └──────────────┬───────────────┘
                        ▼
         ┌──────────────────────────────┐
         │ 5. Decision engine           │  weights, thresholds, overrides, fail modes
         └──────────────┬───────────────┘
                        ▼
 ┌──────────────────────────────┐
 │ 6. Append-only audit log     │  input hash, features, rules, model answers,
 │                              │  policy@version, latencies, decision
 └──────────────────────────────┘
```

## 4. Data format

### 4.1 Transaction

```json
{
  "transaction_id": "tx_0011",
  "timestamp": "2026-10-12T03:14:00+02:00",
  "amount": 1890.00,
  "currency": "EUR",
  "channel": "card_present",
  "merchant": { "name": "ELECTRO WORLD LTD", "mcc": "5732", "country": "RO" },
  "location": { "lat": 44.43, "lon": 26.10, "country": "RO" },
  "device_id": "dev_9f2a",
  "ip_country": "RO",
  "beneficiary": { "iban": "RO49AAAA1B31007593840000", "name": "M. Popescu", "vop_result": "no_match" },
  "mandate": null,
  "recurring": false,
  "authentication": "sca",
  "description": "Online purchase"
}
```

`channel` is one of `card_present`, `card_not_present`, `atm`, `sepa_instant`, `sepa_credit_transfer`, `sepa_direct_debit`.

- `vop_result`: outcome of **Verification of Payee** (`match`, `close_match`, `no_match`, `unavailable`), mandatory for euro credit transfers since 9 October 2025 (Reg. (EU) 2024/886).
- `mandate`: for SEPA Direct Debit, `{ "creditor_id": "...", "mandate_id": "...", "signed_at": "..." }`.
- `recurring`: marked by the scheme or the merchant (subscriptions, standing orders).

### 4.2 Request

```json
{
  "customer": { "id": "c_123", "segment": "retail", "vulnerable": false, "account_age_days": 1450,
                "home_country": "IT", "recent_profile_changes": [{"field": "phone_number", "at": "2026-10-11T19:02:00+02:00"}] },
  "history": [ /* up to 50 transactions; the engine reads the last history.payments */ ],
  "candidate": { /* transaction to score */ }
}
```

In production, history comes from a feature store rather than the request (§9.4).

### 4.3 Features

| Feature | Fraud signal |
|---|---|
| `amount_zscore`, `amount_ratio_max`, `is_round_amount` | amount out of profile |
| `tx_count_10m`, `tx_count_1h`, `small_tx_burst`, `amount_24h_total` | velocity, card testing |
| `km_from_last`, `implied_speed_kmh`, `ip_geo_mismatch` | impossible travel, cloned card |
| `new_merchant`, `new_mcc`, `high_risk_mcc` | merchant out of profile (gift cards, crypto, money transfer) |
| `new_country`, `high_risk_country`, `sanctioned_country` | geography |
| `new_device`, `profile_change_hours` | account takeover (new device after a phone/email change) |
| `new_beneficiary`, `vop_mismatch`, `first_instant_payment`, `beneficiary_in_mule_list` | APP fraud / instant-transfer scams |
| `atm_withdrawals_24h`, `atm_country_vs_home` | **ATM**: cash-out after card theft or skimming |
| `new_creditor`, `mandate_age_days`, `dd_amount_vs_mandate_history` | **SDD**: fraudulent mandates, unexpected debits |
| `recurring_matches_known` | **Recurring**: same merchant and amount as an established subscription (lowers risk) |
| `hour_deviation` | unusual time of day |

With 10 transactions (the default window) the statistics are fragile. The code handles std ≈ 0, short history and missing location.

## 5. YAML security policy

### 5.1 Banking practices applied

| Practice | How the policy reflects it |
|---|---|
| **PSD2 / RTS SCA (Del. Reg. (EU) 2018/389)**: transaction risk analysis (TRA) exemptions only below thresholds tied to the PSP's fraud rate | `sca`: exempt only when risk is low **and** the amount is under the TRA threshold allowed by the bank's current fraud rate |
| **Verification of Payee** and liability for unflagged mismatches (PSR) | rule: VoP `no_match` + significant amount → `hold` |
| **Impersonation / APP fraud** (PSR: refund duty for some PSP-impersonation cases) | rules on "contact change + new device + new beneficiary + instant" |
| **Instant Payments**: ~10 s decision window, irrevocable | per-channel latency budget, conservative fail mode for instant |
| **Defence in depth** | rules + pre-score + model; no single layer decides everything |
| **Per-channel fail-safe** | model unavailable: small card-present → stand-in on pre-score; instant transfers → `step_up`, never `approve` |
| **Vulnerable customers** | lower thresholds, more frequent step-up |
| **GDPR (data minimisation, Art. 22)** | pseudonymisation before the model; automated `block`s reviewable and contestable; `hold` → analyst |
| **AI Act** | Annex III 5(b) excludes AI used to detect financial fraud from the high-risk list; transparency, logging and human oversight kept as good practice |
| **DORA** (since 17 Jan 2025) | Regolo is an ICT third-party provider: timeouts, circuit breaker, per-channel fail modes so the bank keeps deciding when Regolo is down, exit strategy (open weights, §9.4) |
| **Model risk management** | versioned policy, shadow mode, champion/challenger, drift monitoring |
| **Four-eyes principle** | `governance`: author ≠ approver; policy file hash recorded in every audit record |

### 5.2 Policy (`policies/retail-eu.yaml`, production targets)

> Excerpt as designed in v3. The implemented file differs in three measured ways: it asks **two** questions (`scam_pattern`, `fraud_risk`; weights 0.4/0.6) because every extra question re-encodes the whole state (§7.3); the account-takeover rule decides `hold` instead of `step_up`, because an OTP would go to the phone number that was just changed; it adds a `new_mandate_large_debit` rule and `unavailable_actions` (no step-up on a direct debit). The three yes/no questions live in `policies/retail-eu-explainable.yaml`.

```yaml
policy_id: retail-eu
version: 1
effective_from: 2026-11-01
governance:
  author: fraud-strategy-team
  approved_by: risk-officer        # must differ from author (four-eyes)
  change_ticket: CHG-2026-0412
  mode: enforce                    # enforce | shadow (compute and log, do not act)

privacy:
  pseudonymize: [beneficiary.iban, beneficiary.name, customer.id, device_id, mandate.creditor_id]
  drop_fields_before_model: [description, merchant.name]   # free text may contain personal data
  allow_external_backend: true                            # false → nothing is sent to Regolo (routing.mode: never)

lists:
  sanctioned_countries: [KP, IR, SY, CU, RU, BY]   # align with official EU/UN sanctions lists
  high_risk_countries: [NG, GH, KH, MM]           # example; align with FATF/EU lists
  high_risk_mcc: ["4829", "6051", "6540", "7995", "5967"]
  mule_beneficiaries_file: lists/mule_ibans.txt   # hashed IBANs flagged as mule accounts

limits:
  daily_amount: { retail: 5000, vulnerable: 1500, business: 50000 }
  atm_daily: { retail: 1000, vulnerable: 500, business: 3000 }

# Level 2: hard rules (evaluated in order; first match decides)
hard_rules:
  - id: sanctions_country
    when: "features.sanctioned_country"
    decision: block
    reason: "Sanctioned country"
  - id: known_mule_beneficiary
    when: "features.beneficiary_in_mule_list"
    decision: block
    reason: "Beneficiary flagged as mule account"
  - id: impossible_travel_card_present
    when: "candidate.channel in ['card_present', 'atm'] and features.implied_speed_kmh > 900"
    decision: block
    reason: "Physically impossible travel (likely cloned card)"
  - id: card_testing_burst
    when: "features.small_tx_burst >= 4 and features.tx_count_10m >= 5"
    decision: block
    reason: "Card-testing pattern"
  - id: atm_daily_limit
    when: "candidate.channel == 'atm' and features.atm_amount_24h > limits.atm_daily[customer.segment]"
    decision: block
    reason: "ATM daily limit exceeded"
  - id: vop_no_match_large
    when: "features.vop_mismatch and candidate.amount >= 1000"
    decision: hold
    reason: "Beneficiary name does not match IBAN (VoP no match)"
  - id: account_takeover_pattern
    when: "features.profile_change_hours < 48 and features.new_device and features.new_beneficiary"
    decision: step_up
    reason: "Recent contact change + new device + new beneficiary"
  - id: daily_limit
    when: "features.amount_24h_total > limits.daily_amount[customer.segment]"
    decision: step_up
    reason: "Segment daily limit exceeded"
  - id: known_recurring
    when: "features.recurring_matches_known and not features.new_device"
    decision: approve
    reason: "Matches an established recurring payment"

# PSD2: SCA exemptions (Art. 18 RTS, TRA)
sca:
  current_fraud_rate_bps: { card_not_present: 5, credit_transfer: 0.8 }
  tra_thresholds_eur:   # RTS SCA Annex: cards 0.13%/0.06%/0.01%, transfers 0.015%/0.01%/0.005%
    card_not_present: [{max_rate_bps: 1, eur: 500}, {max_rate_bps: 6, eur: 250}, {max_rate_bps: 13, eur: 100}]
    credit_transfer:  [{max_rate_bps: 0.5, eur: 500}, {max_rate_bps: 1, eur: 250}, {max_rate_bps: 1.5, eur: 100}]
  exempt_only_if_risk_below: 0.20

# Level 3: pre-score and routing
prescore:
  weights:
    amount_zscore: 0.20
    new_beneficiary: 0.15
    new_device: 0.15
    ip_geo_mismatch: 0.15
    new_country: 0.10
    high_risk_mcc: 0.10
    first_instant_payment: 0.10
    hour_deviation: 0.05

routing:
  mode: cascade                       # cascade | always | never
  approve_if_prescore_below: 0.15
  block_if_prescore_above: 0.95
  always_call_model_if:
    amount_at_least: 500
    channels: [sepa_instant]

# Level 4: Clef-Flash
model:
  backend: regolo                     # regolo | fake (offline tests)
  name: clef-flash
  timeout_ms:                         # PRODUCTION targets (dedicated capacity, same region)
    card_present: 150
    atm: 300
    card_not_present: 300
    sepa_instant: 800
    default: 500
  circuit_breaker: { failure_ratio: 0.2, window_s: 30, open_s: 60 }

questions:
  amount_anomalous:
    type: noul
    weight: 0.20
    instructions: Is the amount anomalous compared with the spending habits shown in the history and features?
  geo_device_inconsistent:
    type: noul
    weight: 0.20
    instructions: Are location, country, IP or device inconsistent with the customer's recent transactions?
  account_takeover:
    type: noul
    weight: 0.20
    instructions: Are there signs that a third party has taken control of the account (recent contact change, new device, new beneficiary)?
  scam_pattern:
    type: choice
    weight: 0.20
    instructions: Which fraud pattern best fits the transaction?
    criteria:
      none: No fraud pattern, habitual behaviour
      card_fraud: Unauthorised card use (cloned or stolen)
      card_testing: Card being tested with micro-charges
      app_scam: Customer appears manipulated into paying a fraudster (fake bank operator, investment, romance)
      account_takeover: Payment initiated by a third party controlling the account
      money_mule: Account appears used to move funds through
      unauthorised_debit: Direct debit from a creditor the customer never authorised
    risk_by_option: { none: 0.0, card_fraud: 1.0, card_testing: 1.0, app_scam: 0.9, account_takeover: 1.0, money_mule: 0.8, unauthorised_debit: 0.9 }
  fraud_risk:
    type: score
    weight: 0.20
    instructions: Rate the overall risk that this transaction is fraud against the customer.
    criteria:
      - Consistent with the customer's habits
      - Unusual but plausible
      - Suspicious, needs verification
      - Very likely fraudulent

# Level 5: decision
decision:
  combine: { prescore: 0.4, model: 0.6 }
  thresholds:
    default:    { step_up: 0.40, hold: 0.65, block: 0.80 }
    vulnerable: { step_up: 0.25, hold: 0.50, block: 0.70 }
  overrides:
    - when: "answers.account_takeover >= 0.90"
      decision: block
    - when: "answers.scam_pattern == 'app_scam' and answers.scam_pattern_confidence >= 0.70 and candidate.channel == 'sepa_instant'"
      decision: hold               # a call to the customer beats a hard block
  on_backend_failure:
    card_present: use_prescore     # stand-in processing
    atm: step_up
    card_not_present: step_up
    sepa_instant: step_up
    sepa_credit_transfer: hold
    sepa_direct_debit: hold
    default: step_up

audit:
  sink: logs/decisions.jsonl
  hash_chain: true
  retention_days: 3650
  log_model_payload: pseudonymized
```

### 5.3 reference engine policy (`policies/retail-eu.yaml`)

The production timeouts above **cannot be met over the shared public API** (measured p95 737 ms, §7.3). The reference engine policy inherits everything and relaxes only latency:

```yaml
extends: retail-eu.yaml
policy_id: retail-eu
model:
  timeout_ms: { default: 2000 }   # correctness testing over the shared API, not a latency target
```

### 5.4 Notes

- **TRA thresholds** reproduce the RTS SCA table and must be checked by Compliance.
- **Probabilities are not calibrated.** Clef's probabilities are not real fraud probabilities. Weights and thresholds are starting points, to be tuned on labelled data in `shadow` mode first.
- **Lists** (countries, MCCs) are examples. In production they come from official sanctions lists, FATF lists and internal lists.
- **No `eval`.** `when` expressions run in a restricted evaluator (`simpleeval`) with read-only access to `candidate`, `customer`, `features`, `lists`, `limits` and `answers`.
- **History window (`history.payments`, 1–50, default 10).** The engine reads the customer's most recent N payments before the one being checked, for the features and for the state sent to Clef-Flash; the request may carry more (the generated data has 30). Measured on Regolo, the 12 scenarios with the model always called (13 Oct 2026, shared API):

  | Payments read | Input tokens per call | Model median / 95th | Cost per 1,000 calls | Scenario expectations met |
  |---|---|---|---|---|
  | 5 | 1,716 | 296 / 501 ms | $0.26 | 11 of 12 |
  | 10 | 2,462 | 258 / 409 ms | $0.37 | 12 of 12 |
  | 30 | 5,118 | 867 / 994 ms | $0.77 | 12 of 12 |

  Each payment adds about 140 input tokens. At 30 the model call no longer fits a card-payment budget. At 5 the monthly Netflix charge drops out of the window, so scenario 12 is no longer recognised as recurring and gets a step-up: a window shorter than a month misses rent, utilities and subscriptions. Production alternative for long histories: keep the window short for the model and precompute long-term aggregates (monthly recurring payees, 90-day median) as features.
- **Startup validation.** The loader rejects a policy if `author == approved_by`, weights do not sum to 1, thresholds are not increasing, or a question has no `instructions`.

## 6. Example call

```bash
curl -s https://api.regolo.ai/v1/systemone \
  -H "Authorization: Bearer $REGOLO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "clef-flash",
    "state": {
      "history_summary": {"avg_amount": 46.2, "countries": ["IT"]},
      "candidate": {"amt": 1890, "ch": "sepa_instant", "cc": "RO", "hour": 3, "vop": "no_match"},
      "features": {"amount_zscore": 87.8, "new_beneficiary": true, "new_device": true}
    },
    "questions": {
      "account_takeover": {"type": "noul", "instructions": "Are there signs a third party took over the account?"},
      "fraud_risk": {"type": "score", "criteria": ["Usual", "Unusual", "Suspicious", "Very likely fraud"]}
    }
  }'
```

## 7. Backends

### 7.1 Regolo: verified contract (live call, 12 Oct 2026)

`POST https://api.regolo.ai/v1/systemone` → `200`:

```json
{
  "model": "clef-flash",
  "answers": {
    "ato":     {"type": "noul", "noul": 0.99999999996, "x_label_mass": 0.132},
    "pattern": {"type": "choice", "choice": "app_scam", "confidence": 0.987,
                "probabilities": {"none": 9.2e-08, "card_fraud": 0.0086, "app_scam": 0.991}, "x_label_mass": 0.998},
    "risk":    {"type": "score", "score": 2.9999994, "confidence": 0.9999994,
                "legend": {"0": "Usual", "1": "Unusual", "2": "Suspicious", "3": "Very likely fraud"},
                "probabilities": {"0": 5.8e-11, "1": 1.7e-07, "2": 2.2e-07, "3": 0.9999996}, "x_label_mass": 0.999}
  },
  "usage": {"input_tokens": 354, "output_tokens": 0}
}
```

Catalog (`GET /model_group/info`) for `clef-flash`:

| Field | Value |
|---|---|
| serving | `hosted_vllm` |
| max input tokens | 65,536 |
| price | $0.15 / M input tokens, $0 output |
| `tpm` / `rpm` | not published. Treat rate limits as unknown, not unlimited, and confirm with Regolo before any load test |

- **Cost per call**: input tokens ≈ state tokens × number of questions (§7.3). The implemented policy uses ~2,500 tokens per call, about **$0.0004**.
- **`x_label_mass`** is undocumented. We saw ~0.998 on `choice`/`score` answers but 0.01–0.15 on `noul` answers. The reference engine logs it and does not use it in decisions. Its meaning is a question for Cloudflare/Regolo.

### 7.2 Scope: Regolo only

Local execution through Ollama was dropped from the reference engine (decision of 12 Oct 2026). Without a second backend:
- **Regolo is the only model backend.** When it is slow or down, the circuit breaker opens and each channel applies its `on_backend_failure` fail mode immediately, instead of waiting for a timeout;
- **the exit strategy required by DORA** rests on Clef-Flash being open-weight (Apache-2.0): a dedicated or on-prem deployment remains possible later (§9.4) without changing the policy or the protocol (`/v1/systemone`).

### 7.3 Measured latency and token usage (Regolo, shared API, from this Mac)

First probe: 20 sequential calls, ~230-token state, 2 questions: p50 175 ms, p95 737 ms, max 1.2 s.

**Finding 1: tokens and latency scale with the number of questions.** Regolo's `usage.input_tokens` grows linearly with the questions, and so does latency: the state appears to be encoded once per question. Medians of 6 calls each, real scenario states:

| State | Questions | Input tokens | p50 | max |
|---|---|---|---|---|
| full (summary + 10 tx + features) | 5 | ~6,100 | 566 ms | 769 ms |
| full | **2 (choice + score)** | **~2,500** | **148 ms** | 196 ms |
| summary + features, no raw history | 5 | ~2,700 | 281 ms | 346 ms |
| summary + features, no raw history | 2 | ~1,100 | 143 ms | 218 ms |

So the policy asks few, rich questions. One `choice` with the fraud patterns plus one `score` keeps p50 around 150–250 ms. Cost at ~2,500 tokens is about **$0.0004 per model call**.

**Finding 2: yes/no answers saturate, choice and score do not.** On grey-zone scenarios:
- the `noul` questions returned 0.0 or 1.0 with `x_label_mass` of only 0.001–0.02;
- `choice` and `score` returned intermediate values (expected risk 2.2–2.4 out of 3, choice confidence 0.28–0.33) with `x_label_mass` of 0.6–0.9.

`x_label_mass` is undocumented, but it looks like the probability mass the model puts on the allowed labels. **The decision relies on `choice` + `score`.**

**Finding 3: concurrency on the shared API queues.** At concurrency 4, model p50 rose from ~200 ms to ~680 ms, for about 6 model calls per second. The shared endpoint is fine for correctness tests. Throughput and tail latency need dedicated capacity (§9).

### 7.4 Shared client design

- `httpx.AsyncClient` with keep-alive;
- per-channel timeout from the policy;
- at most one retry, only on connection errors, and only within the time budget;
- circuit breaker: while open, requests skip Regolo and go straight to the channel's fail mode;
- API key only from the `REGOLO_API_KEY` environment variable (`.env`, git-ignored), never in YAML or logs.

## 8. Synthetic scenarios

### 8.1 Sets generated with a Regolo chat model

The console (sidebar → *Add a dataset* → *Write with a Regolo model*) asks a chat model on Regolo to write customers and payments in a mix of eight types: everyday payment and unusual but genuine (legit); card testing, stolen card online, account takeover, impersonation scam, ATM cash-out abroad, unknown direct debit (fraud). The models are the `chat` entries of `/model_group/info` for the key, except `clef-flash`, with their input and output prices.

- **Presets.** *Payment transactions (mixed)*, *E-commerce payments*, *Instant transfers and scams*, *Cards abroad*, or a custom mix; the preset also names the set (editable). The dialog says in one sentence what will happen (model, customers, genuine and fraud counts) and shows the price before starting: the selected model's input and output prices from Regolo, the expected tokens, and the time measured on earlier sets with that model.
- **Mix.** Percentages are turned into exact counts (largest remainder), one type per customer.
- **Format.** The model writes a compact format (minutes ago, city, `home`/`new` device, beneficiary and creditor names). `generator.py` fills timestamps, coordinates, IBANs (same name, same IBAN), mandates and device ids, then validates the request; an invalid answer gets one correction request with the error, then is discarded and counted.
- **Labels.** Label and expected decisions come from the requested type, not from the model: they say what the payment was meant to be, not verified fraud.
- **Cost.** An estimate is shown before running; the real tokens and cost from `usage` after. Measured on 13 Oct 2026 with `mistral-small-4-119b`, 10 customers with 12 past payments: 10 of 10 valid with no correction, about 10 s per customer (4 in parallel, 31 s in total), 7,330 input and 13,842 output tokens, $0.033. Scored on Clef-Flash, every fraud was stopped and both "unusual but genuine" payments were held by the model.
- Sets are saved in `data/generated/<name>.json` (+ `.meta.json`) and appear in step 3 of the Test page.

### 8.2 Named scenarios

| # | Scenario | Deciding level | Expected |
|---|---|---|---|
| 1 | Usual grocery spend | pre-score | approve |
| 2 | Amount ×20, electronics, e-commerce, new merchant | Clef | step_up |
| 3 | Card present in Milan, 40 min later in Bucharest | rule | block |
| 4 | 6 micro-charges in 8 minutes | rule | block |
| 5 | Phone changed yesterday + new device + instant to new IBAN | rule + Clef | step_up / hold |
| 6 | "Fake bank operator": instant €4,900, VoP no match | rule | hold |
| 7 | Plausible trip to Spain, consistent spending | Clef | approve |
| 8 | Merchant in sanctioned country | rule | block |
| 9 | Vulnerable customer, unusual €900 transfer | Clef + dedicated thresholds | step_up |
| 10 | **ATM**: 3 withdrawals abroad within 1 h after a card-present purchase at home | rule / Clef | block |
| 11 | **SDD**: first debit from a new creditor, mandate signed today, €750 | Clef | hold |
| 12 | **Recurring**: monthly streaming subscription, same amount | rule | approve |
| 13 | Backend unreachable, card present €25 | fail mode | approve (stand-in) |
| 14 | Backend unreachable, instant €2,000 | fail mode | step_up |
| 15 | Policy in `shadow` | — | decision logged, not enforced |

The generator also produces **N random customers** with mixed normal/anomalous candidates (configurable fraud rate) for routing and throughput tests.

## 9. Does it work at real banking volumes?

### 9.1 Real volumes (ECB)

Euro-area payment statistics, **second half of 2025** (184 days):

| Instrument | Transactions | Average per second | Average per minute |
|---|---|---|---|
| All non-cash payments | 83.5 bn | ~5,250 | **~315,000** |
| Card payments | 47.8 bn | ~3,000 | ~180,000 |
| Credit transfers (25% instant) | 17.8 bn | ~1,100 | ~67,000 |
| Direct debits | 11.7 bn | ~740 | ~44,000 |

Per-second and per-minute values are my own division of the ECB totals.

What this means:

- **The entire euro area averages ~315k payments per minute.** Peaks (lunchtime, Black Friday, salary days) are higher. Assuming 2–3× (my estimate, not a sourced figure), that is roughly 0.6–1 million per minute.
- **"Millions per minute" is card-network scale.** Visa quotes a capacity above 65,000 messages per second (~3.9 M/min), a figure from secondary sources.
- **A single large bank** handles a fraction of that. At an assumed 5% share it averages ~16k/min with peaks around ~50k/min (my estimate).

### 9.2 GPU sizing: model on every transaction vs cascade

Assumptions (order of magnitude; replace with `fraudclef bench` measurements on dedicated hardware):
- compute ≈ 2 × 9·10⁹ × input tokens FLOPs per request;
- **measured** input tokens per request are ~1,100 (summary state, 2 questions) or ~2,500 (full state, 2 questions), because the state is encoded once per question (§7.3);
- an H200 sustains ~4·10¹⁴ FLOP/s in BF16 (~40% of peak);
- that gives **~20 req/s per GPU** (1,100 tokens) or **~9 req/s per GPU** (2,500 tokens).

| Load (peak) | RPS | GPUs, model on 100% (1.1k / 2.5k tok) | GPUs, cascade with 5% to model |
|---|---|---|---|
| Large bank (~50k/min) | ~830 | 41 / 93 | 3 / 5 |
| Euro area peak (~1 M/min) | ~16,700 | 830 / 1,880 | 42 / 94 |
| Card-network stress (3 M/min) | ~50,000 | 2,480 / 5,620 | 124 / 281 |

If the serving stack shared the state's KV cache across questions (prefix caching), the cost would fall towards one state encoding per request. That needs verifying on the deployment.

The reference engine measured **25% routed to the model** on a synthetic dataset where 30% of candidates are deliberately abnormal. Real traffic is far more habitual, so 2–5% is a reasonable target, to be confirmed in shadow mode.

Add ×1.5–2 for headroom and N+1 per availability zone. Main takeaways:
- **For a single bank, sending everything to Clef is possible but wasteful** (40–90 GPUs). With the cascade it takes a handful.
- **The cascade cuts the fleet by about 20×** and keeps tail latency low, because the GPUs are not saturated.
- **Number of questions is a cost multiplier**: each extra question costs another full state encoding.

### 9.3 Scaling out with parallel machines

The design is **stateless**, so it scales horizontally:

```
                    ┌─────────────── load balancer ───────────────┐
                    ▼                       ▼                     ▼
             scorer replica 1        scorer replica 2   …   scorer replica N     (CPU: features, rules, pre-score)
                    │                       │                     │
                    └──────── only grey-zone requests ────────────┘
                                            ▼
                    ┌─────────────── model gateway ───────────────┐
                    ▼                       ▼                     ▼
              Clef GPU 1               Clef GPU 2      …     Clef GPU M          (data-parallel: one 9B BF16 copy ≈ 18 GB per GPU)
                                            │
                       feature store (Redis/Aerospike) ◄── Kafka/Flink stream
```

- **Scorer tier (CPU):** N identical replicas. Throughput grows linearly because there is no shared state in the request path; the feature store is the only shared component.
- **Model tier (GPU):** M independent copies of the model, one per GPU (data parallelism; no tensor parallelism needed for 9B). Size it as `M = ceil(peak_model_rps × headroom / rps_per_gpu)`.
  - `rps_per_gpu` must be **measured**: raise concurrency until p95 exceeds the budget (the "knee").
  - Continuous batching (vLLM/SGLang) raises throughput at the cost of latency.
- **Isolation:** separate pools per channel (card-present vs instant), so a surge in one cannot slow the other.
- **Autoscaling** on model-gateway queue depth, not CPU usage.

What the reference engine can and cannot show:
- **It can** measure the cascade routing rate, end-to-end latency and throughput under concurrency (`fraudclef bench --concurrency N`) on Regolo.
- **It cannot** demonstrate multi-GPU horizontal scaling: that needs dedicated capacity.
- Against Regolo, concurrency stays gentle (default ≤ 8) because rate limits are unknown.

### 9.4 Prototype vs production

| Component | reference engine | Production |
|---|---|---|
| History | in the request | in-memory feature store, updated via streaming |
| Pre-score | weighted sum from policy | trained tabular model (LightGBM/XGBoost) with SHAP |
| Clef | shared Regolo API | dedicated deployment (reserved Regolo capacity or on-prem SGLang/vLLM) |
| Policy | YAML file | YAML in Git, four-eyes approval, canary rollout, hot reload |
| Audit | JSONL with hash chain | WORM storage, SIEM and case-management integration |
| Release | — | shadow → champion/challenger → enforce |

**Conclusion.** The architecture works at real banking volume **as a judgement layer on the grey zone**. For a single bank it could even score every transaction with a modest GPU fleet. What separates the reference engine from production is infrastructure (feature store, streaming, dedicated capacity), not a redesign.

## 10. reference engine objectives and results (Regolo, 12 Oct 2026)

| # | Objective | Result |
|---|---|---|
| 1 | All 15 scenarios meet expectations | **15/15** live on Regolo, 15/15 offline (`pytest`) |
| 2 | Clef discriminates in the grey zone | **Yes for `choice` + `score`, no for `noul`** (§7.3). Example: groceries → risk 0.002/3; Barcelona trip → 2.22; vulnerable customer's €900 transfer → 2.35 |
| 3 | Cascade vs always | see table below |
| 4 | Latency and throughput | model p50 ~150–240 ms sequential, ~680 ms at concurrency 4 on the shared API |
| 5 | Resilience | timeout → per-channel fail mode within budget; open circuit skips Regolo and applies the fail mode (tests) |
| 6 | Audit | hash chain verified; tampering and deletion detected (tests) |

Cascade vs always on 200 random labelled requests (`--concurrency 4`):

| | always | cascade |
|---|---|---|
| Sent to the model | 94.5% | **25%** |
| Throughput | 6 req/s | **29 req/s** |
| Fraud not approved | 100% | 100% |
| Legit with friction (step-up/hold/block) | 18.2% | 15.2% |
| Decision agreement | — | 98% (5 legit transactions approved by cascade, step-up under always) |

How to read these numbers:
- The random dataset is synthetic and its fraud is deliberately obvious. **100% fraud caught is not a performance claim.** Real detection rates need labelled bank data in shadow mode.
- **Legit friction is the number to tune.** Clef rated a plausible trip abroad at 2.2/3 ("suspicious"), so travel generates step-ups. Customer travel notices or a lower `fraud_risk` weight would address it.

## 11. Project layout

```
.
├── GUIDE.md
├── run.sh                         # check | start | stop | restart | status for the console
├── pyproject.toml                 # uv, Python 3.12+, `fraudclef` entry point
├── .env.example                   # REGOLO_API_KEY, FRAUDCLEF_HMAC_KEY
├── .gitignore                     # .env, logs/, generated random data
├── policies/
│   ├── retail-eu.yaml             # production targets, 2 questions
│   ├── retail-eu.yaml                   # extends retail-eu, relaxed timeouts for the shared API
│   ├── retail-eu-explainable.yaml          # poc + 3 yes/no questions (slower)
│   └── .history/                  # previous versions, written by the console editor
├── lists/mule_ibans.txt
├── data/scenarios/*.json          # generated by `fraudclef generate`
├── data/generated/*.json          # sets written by a Regolo chat model from the console
├── logs/                          # decisions.jsonl (audit), bench_runs/*.json, ui.log
├── src/fraudclef/
│   ├── models.py        # Pydantic: Transaction, ScoringRequest, Decision
│   ├── privacy.py       # HMAC pseudonymisation
│   ├── features.py      # features, robust z-score, pre-score normalisers, history summary
│   ├── policy.py        # load, extends, validate, four-eyes, expression dry run
│   ├── rules.py         # restricted expression evaluator (simpleeval)
│   ├── backends.py      # SystemOne client (Regolo), FakeBackend, circuit breaker
│   ├── engine.py        # cascade, decision, overrides, fail modes, SCA, audit
│   ├── audit.py         # JSONL with hash chain + verify; each record says what started it
│   ├── pricing.py       # live clef-flash price from the Regolo catalog
│   ├── benchmark.py     # shared by CLI and console: latency, tokens, cost, agreement
│   ├── datagen.py       # named scenarios + random labelled dataset
│   ├── generator.py     # sets written by a Regolo chat model: mix, compact format, validation, cost
│   ├── cli.py           # fraudclef score | bench | generate | audit-verify
│   └── web/             # FastAPI console: app.py + static/ (index.html, app.js, styles.css, brand/ regolo.ai logo)
└── tests/               # scenarios, policy validation, audit, breaker, privacy, SCA, web API, live contract
```

## Sources

- [Cloudflare/clef-flash model card](https://huggingface.co/Cloudflare/clef-flash)
- Regolo: `GET https://api.regolo.ai/models`, `GET /model_group/info`, live `POST /v1/systemone` (12 Oct 2026) · [catalog](https://docs.regolo.ai/models/catalog/)
- [ECB payments statistics, H2 2025](https://www.ecb.europa.eu/press/stats/paysec/html/ecb.pis2025h2~23986fb4a6.en.html) · [ECB H1 2025](https://www.ecb.europa.eu/press/stats/paysec/html/ecb.pis2025h1~36edd636c8.en.html)
- Visa capacity (secondary): [PitchBook](https://pitchbook.com/profiles/company/41641-21)
- Cloudflare announcement via secondary sources: [developersdigest.tech](https://www.developersdigest.tech/blog/cloudflare-clef-decision-models-2026), [datanorth.ai](https://datanorth.ai/news/cloudflare-releases-clef-and-clef-flash)
- [PSD3/PSR final Council compromise texts (23 Apr 2026)](https://www.cliffordchance.com/content/dam/cliffordchance/briefings/2026/04/impact-of-psd3-are-you-ready.pdf) · [European Parliament provisional deal (27 Nov 2025)](https://www.europarl.europa.eu/news/en/press-room/20251121IPR31540/payment-services-deal-more-protection-from-online-fraud-and-hidden-fees)
- EU regulations referenced (for bank Compliance review before production deployment): Del. Reg. (EU) 2018/389 (PSD2 RTS SCA Art. 14 & Art. 18), Reg. (EU) 2024/886 (Instant Payments & Verification of Payee, mandatory since 9 Oct 2025), Reg. (EU) 2022/2554 (DORA, applicable since 17 Jan 2025), [Reg. (EU) 2024/1689 Annex III point 5(b) (EU AI Act fraud-detection exception)](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3), and GDPR Art. 22.
