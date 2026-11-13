# fraudclef: payment fraud scoring with a decision model

fraudclef checks a payment against the customer's own history and returns one of four decisions: **approve**, **step-up** (ask the customer to confirm), **hold** (stop it until someone checks) or **block**. A payment settled by the rules takes under a millisecond. One that needs the model took a median of about 150 to 700 ms on the shared Regolo API, depending on how much the model reads and how busy the API is.

Every rule, weight, threshold and question the engine uses lives in a **YAML policy**, not in the code. A risk team can change how payments are judged without a software release.

Most payments are settled locally by hard rules and a quick weighted score, at no cost. Only uncertain payments, high amounts and instant transfers go to the decision model: **Clef-Flash**, a 9-billion-parameter model from Cloudflare served by **Regolo**. Clef-Flash does not write text. It reads the payment and the customer's past payments and returns a probability for each answer to the policy's questions, such as "which fraud pattern fits?" and "how risky is this, from 0 to 3?". Before anything is sent, names, IBANs and device ids are replaced by keyed hashes. Every decision is written to an audit log in which each record carries the hash of the one before, so an edited or deleted line shows.

It runs as a Python engine, a local web console, and a command-line runner. Companion engineering guide: <https://regolo.ai/sub-second-bank-fraud-detection-clef-flash-yaml-policies/>.

## Where to start

| You want to | Read |
|---|---|
| Install it, run the console, score payments, compare policies, call the engine from code | [docs/USING.md](docs/USING.md) |
| Change how payments are judged: rules, thresholds, questions to the model, a new policy for another kind of risk | [docs/POLICIES.md](docs/POLICIES.md) |
| The design choices, every measurement and the sizing for real banking volumes | [GUIDE.md](GUIDE.md) |

## In one minute

```bash
git clone https://github.com/regolo-ai/tutorials.git
cd tutorials/sub-second-bank-fraud-clef-flash
./run.sh start          # checks everything, then opens http://127.0.0.1:8080
```

The Start page has three steps: create a Regolo API key, paste it in the sidebar, run a quick comparison (less than one cent). Then:

1. Open **Test**: choose up to three policies, when to ask the decision model and a dataset. The cost is shown before the run starts.
2. Open **Policies** to edit the YAML in the browser. Every keystroke is validated, and the previous version is kept.
3. Open **Audit log** to see what was decided and exactly what was sent to Regolo.

Stop it with `./run.sh stop`.

## How a payment is decided

The checks run from cheapest to most expensive, and each level decides only the cases it is sure about (a cascade):

1. **Hard rules**, in microseconds. Sanctioned country, known mule account, travel between two card payments faster than 900 km/h, a burst of micro-charges, segment limits. The first rule that matches decides.
2. **Quick score**, in microseconds. A weighted sum of computed features such as how far the amount is from the customer's usual amounts, a new device or a new beneficiary. Clearly habitual payments are approved here.
3. **Clef-Flash**, in tens to hundreds of milliseconds. The grey zone, payments of €500 or more and instant transfers.
4. **Decision**. Thresholds, overrides, PSD2 strong customer authentication (SCA) exemptions, and a fallback decision per channel for when Regolo does not answer.

The routing is a switch, so the same data can be run three ways and compared: `cascade` (the model only when needed), `always` (the model on every payment no rule settles), `never` (rules and quick score only).

## Key capabilities

- **Policies change without code.** Rules, weights, routing, the questions to the model, thresholds and fallbacks are YAML. A policy can inherit another and change only what differs. The loader refuses a policy whose author is also its approver, whose weights do not add up to 1, or whose rule expressions fail a dry run. A policy in `shadow` mode logs its decisions without acting on them.
- **The cascade cuts model calls.** On 200 random labelled payments, `cascade` sent 25% of them to the model against 94.5% for `always`, and ran at 29 payments per second against 6.
- **A model call is cheap.** The default policy asks two questions, about 2,500 input tokens per call. At Regolo's price of $0.15 per million input tokens (output is free) that is about $0.0004 per call.
- **Graded answers.** The pattern question and the 0 to 3 risk score return intermediate values in the grey zone. For example, groceries scored 0.002 out of 3, a plausible trip to Barcelona 2.22 and a vulnerable customer's unusual €900 transfer 2.35.
- **Nothing to train.** The model judges from the policy's questions and the customer's history. No bank data is used for training.
- **The bank keeps deciding when Regolo is down.** Each channel has its own timeout and fallback. A small card payment falls back to the quick score; an instant transfer gets a step-up, never an approval. After repeated timeouts a circuit breaker skips Regolo and applies the fallback at once.
- **Every decision can be traced.** The audit record holds the input hash, the features, the rules that matched, the model's answers, the policy version and the timings. Tampering and deletion are detected by `fraudclef audit-verify`.
- **Exit strategy.** Clef-Flash is open-weight (Apache-2.0), so the same policies and API can run on dedicated or on-premises GPUs later.

## Benchmarks

All measurements below were taken on 12 and 13 October 2026 through the shared Regolo API from one laptop. Latency includes the internet round trip. Each run is saved in `logs/bench_runs/` with every decision.

### Latency and tokens

Every question makes Regolo read the whole payment state again, so tokens and latency grow with the number of questions. Medians of 6 calls on real scenario states:

| State sent | Questions | Input tokens | Median | Slowest |
|---|---|---|---|---|
| summary, 10 past payments, features | 5 | about 6,100 | 566 ms | 769 ms |
| summary, 10 past payments, features | 2 | about 2,500 | 148 ms | 196 ms |
| summary and features only | 2 | about 1,100 | 143 ms | 218 ms |

With 4 requests in parallel, the model's median rose from about 200 ms to about 680 ms. Over the shared API the 95th percentile was 737 ms, so the production timeouts in `retail-eu.yaml` (150 ms on card payments) cannot be met there. `retail-eu.yaml` sets 3-second cloud API timeouts; co-located dedicated GPUs tighten card timeouts to 150-300 ms.

How many past payments the model reads is set in the policy. On 12 of the hand-written scenarios, with the model called on every one:

| Past payments read | Input tokens per call | Median / 95th percentile | Cost per 1,000 calls | Scenarios as expected |
|---|---|---|---|---|
| 5 | 1,716 | 296 / 501 ms | $0.26 | 11 of 12 |
| 10 | 2,462 | 258 / 409 ms | $0.37 | 12 of 12 |
| 30 | 5,118 | 867 / 994 ms | $0.77 | 12 of 12 |

With 5 payments the monthly streaming charge falls out of the window and is no longer recognised as recurring.

### Synthetic data

All 15 hand-written scenarios meet their expected decision, live on Regolo and offline. On 200 random labelled payments:

| | Model on every payment | Model only when needed |
|---|---|---|
| Sent to the model | 94.5% | 25% |
| Payments per second | 6 | 29 |
| Fraud not approved | 100% | 100% |
| Genuine payments with a step-up, hold or block | 18.2% | 15.2% |

The fraud in this set is deliberately obvious, so 100% is not a performance claim.

### IBM TabFormer card payments

TabFormer is a public labelled dataset of 24.4 million synthetic US card payments (Apache-2.0). The console downloads it and takes samples (sidebar, *Add a dataset*). Policies were tuned on a 2018 sample (200 frauds, 3,000 genuine) and confirmed once on a 2019 to 2020 sample (50 frauds, 1,000 genuine). Precision is recomputed at the real share of fraud in the period (0.145% in 2018, 0.101% in 2019 to 2020): it is the share of stopped payments that are fraud.

Results on the 2019 to 2020 sample, model only when needed:

| Policy | Fraud stopped | Genuine interrupted | Fraud held | Genuine held | Precision of holds | Cost |
|---|---|---|---|---|---|---|
| `cards-us` (questions rewritten for US cards) | 74% | 9.0% | 32% | 1.8% | 1.8% | $0.075 |
| `cards-us-profile` (customer's usual countries) | 92% | 8.8% | 92% | 2.0% | 4.5% | $0.045 |
| One rule: country outside the usual ones | 90% | 0.5% | 90% | 0.5% | about 15% | $0 |
| One rule: merchant outside the US | 100% | 0.5% | 100% | 0.5% | 16.9% | $0 |

"Interrupted" counts any step-up, hold or block.

An earlier run on the same 1,050 payments, before customers carried their usual countries, gave these results with the model only when needed: `retail-eu` (written for EU retail) stopped 50% of fraud and interrupted 15.2% of genuine customers; `cards-us` stopped 56% and interrupted 9.1%. With `retail-eu`, asking the model on every payment stopped 80% of fraud but interrupted 52.7% of genuine customers. `cards-us` rose from 56% to 74% in the later run because the model now also sees the usual countries.

What these runs found:

- **Rewriting the questions helped the model.** In the earlier run, with `retail-eu`, Clef-Flash gave fraud and genuine payments almost the same median risk (2.29 and 2.12 out of 3). With `cards-us`, which explains that frequent small purchases in shops are normal, genuine payments dropped to 0.41 while fraud stayed at 2.08.
- **A stolen card comes in bursts, which hides it from a short history.** The 30 past payments in a TabFormer sample cover a median of 9 days. After a few fraudulent payments abroad, the new country already looks habitual. `cards-us-profile` uses `customer.usual_countries`, the countries the customer paid in over the 90 days ending 30 days before the payment, as a bank's customer profile would hold. With a 7-day gap that rule caught 54% of the 2018 frauds; with 30 days, 88%.
- **On this dataset the model adds little to the rules.** In `cards-us-profile`, the usual-country rule held 45 of the 50 frauds and 5 genuine payments. Clef-Flash stopped 1 more fraud and interrupted 83 genuine payments (68 step-ups, 15 holds).
- **Failed attempts carry no signal here.** A wrong PIN, CVV or card number in the last 24 hours appeared before 1 of 50 frauds and 20 of 1,000 genuine payments.

## Limits

- **No real bank data.** The hand-written and random sets are synthetic, with labels that say what each payment was meant to be. TabFormer is also synthetic. Real detection rates need labelled bank data, run in shadow mode first.
- **TabFormer has an artifact.** Every fraud in its 2019 to 2020 period is at a foreign merchant, so "merchant outside the US" is close to perfect there and would not be in a real portfolio. The dataset also lacks device, IP, location, profile changes and transfer beneficiaries, the signals the model uses for account takeover and scams.
- **The model's probabilities are not calibrated.** They are not real fraud probabilities. Weights and thresholds are starting points to tune on labelled data.
- **Yes/no questions saturate.** They come back as 0 or 1, so the shipped policies rely on the pattern choice and the 0 to 3 score. `x_label_mass`, a field in Regolo's answers, is undocumented; it is logged and not used.
- **Latency is measured on a shared API.** Card-authorisation budgets need dedicated capacity. Regolo publishes no rate limits for `clef-flash`, so the console keeps concurrency at 8 or below.
- **A slow Regolo invalidates a run.** One run on 13 October had calls over the 2-second timeout; the circuit breaker opened and fallbacks decided up to 99% of payments. The console now warns when fallbacks decide more than 5% of a setting's payments.
- **Infrastructure is not production.** The history arrives in the request instead of a feature store. The quick score is a hand-weighted sum instead of a trained model. The audit log is a local file. The GPU sizing in [GUIDE.md](GUIDE.md) is an estimate, not a measurement.
- **The console has no authentication.** It binds to `127.0.0.1` only. The API key is stored in `.env` and never sent back to the browser.
- **Regulatory scope.** References cover Del. Reg. (EU) 2018/389 (PSD2 RTS SCA Art. 14 and Art. 18), Reg. (EU) 2024/886 (Instant Payments and Verification of Payee, mandatory in the euro area since 9 Oct 2025), Reg. (EU) 2022/2554 (DORA, applicable since 17 Jan 2025), Reg. (EU) 2024/1689 (EU AI Act Annex III point 5(b), which excludes AI systems used strictly to detect financial fraud from the high-risk credit-scoring list), GDPR Art. 22, and the EU Council PSD3/PSR compromise texts published on 23 Apr 2026. Bank legal and compliance teams must still validate concrete thresholds and policies before production use.
