# Writing and changing policies

A **policy** is a YAML file in `policies/` that decides everything the engine does with a payment:

- the hard rules;
- the weights of the quick score;
- when to ask the decision model, and what to ask it;
- the thresholds for each decision;
- what to do when the model does not answer.

The code computes the features and runs the steps. The policy says what they mean.

This guide is for the people who will change those decisions: a fraud strategy team, a consultancy, or the bank engineer who supports them. It assumes no programming background beyond reading a spreadsheet formula. Every example in it was checked against the engine's validator.

- [1. How a policy is used](#1-how-a-policy-is-used)
- [2. YAML in five minutes](#2-yaml-in-five-minutes)
- [3. Conditions: the `when` language](#3-conditions-the-when-language)
- [4. What a condition can read](#4-what-a-condition-can-read)
- [5. The policy, section by section](#5-the-policy-section-by-section)
- [6. Inheritance with `extends`](#6-inheritance-with-extends)
- [7. Recipes](#7-recipes)
- [8. Adapting the engine to another kind of risk](#8-adapting-the-engine-to-another-kind-of-risk)
- [9. Validation and error messages](#9-validation-and-error-messages)
- [10. A safe change process](#10-a-safe-change-process)
- [Appendix: the score arithmetic](#appendix-the-score-arithmetic)

---

## 1. How a policy is used

The project ships these policies:

| File | Purpose |
|---|---|
| `retail-eu.yaml` | The complete policy for EU retail accounts, with production timeouts: it waits only 150 ms for the model on card payments. |
| `retail-eu.yaml` | Inherits `retail-eu` and changes only the timeouts, to 2 seconds, so the shared Regolo API can answer. **The default.** |
| `retail-eu-explainable.yaml` | Inherits `retail-eu` and adds three yes/no questions to the model, to explain decisions to an analyst. It costs about 2.5 times the tokens. |
| `cards-us.yaml` | Inherits `retail-eu` for a US card portfolio such as the IBM TabFormer sample. It reads 20 past payments, weights foreign merchants and recent failed attempts in the quick score, and rewrites the model's questions so that frequent small purchases in shops do not read as card testing. |
| `cards-us-profile.yaml` | Inherits `cards-us` and judges card use abroad against the customer's usual countries (`customer.usual_countries`) instead of any foreign merchant, and holds card payments abroad outside them (hard rule `unusual_country`). A fraud burst abroad fills the recent history with payments in the new country; the profile looks further back. |

Every payment goes through the policy in this order. The policy sections that control each step are in brackets.

```
 1. Features         computed from the last N payments                       [history]
 2. Hard rules       first match decides                                      [hard_rules, lists, limits]
 3. Quick score      weighted sum of features, 0 to 1                         [prescore]
 4. Routing          approve, block, or ask the model?                        [routing]
 5. Decision model   answers the questions with probabilities                 [model, questions]
 6. Combine          risk = a × quick score + b × model risk                  [decision.combine]
 7. Thresholds       risk → approve / step_up / hold / block                  [decision.thresholds]
 8. Overrides        model answers can force a decision                       [decision.overrides]
 9. Model failure    no answer in time → the channel's fallback               [decision.on_backend_failure]
10. Channel limits   e.g. no step-up on a direct debit                        [decision.unavailable_actions]
11. PSD2 exemptions  remote payment approved without SCA? only if exempt      [sca]
12. Audit            record with the policy's id and content hash             [audit, governance]
```

There are three places to edit a policy:

- **In the console**, under *Policies*. Every edit is validated as you type, and saving keeps the previous version in `policies/.history/`. This is the recommended way.
- **In any text editor.** The console and the command line read the file each time they score, so a saved change applies to the next payment. `./run.sh check` validates every policy.
- **By creating a new one.** In the console, *New policy* either inherits an existing policy, so you write only what differs, or makes a full copy.

---

## 2. YAML in five minutes

YAML is a text format for settings. You need six things.

**1. `key: value`, one per line.** A space after the colon is required.

```yaml
policy_id: retail-eu
version: 3
```

**2. Indentation shows what belongs to what.** Use two spaces, never tabs. Everything indented under `routing:` is part of `routing`.

```yaml
routing:
  mode: cascade
  approve_if_prescore_below: 0.15
```

**3. Lists: one item per line, each starting with `- `.**

```yaml
channels:
  - sepa_instant
  - sepa_credit_transfer
```

**4. Short forms on one line.** `[a, b]` is a list and `{key: value, key: value}` is a group. These two blocks mean the same:

```yaml
thresholds:
  default: { step_up: 0.40, hold: 0.65, block: 0.80 }
```
```yaml
thresholds:
  default:
    step_up: 0.40
    hold: 0.65
    block: 0.80
```

**5. Quotes.** Put conditions and any text containing `:` or `#` in double quotes. Inside a condition, use single quotes for text values.

```yaml
when: "candidate.channel == 'atm' and candidate.amount > 500"
reason: "Large ATM withdrawal: check the card"
```

**6. Comments start with `#`.** For long text, `>-` folds the following indented lines into one paragraph.

```yaml
# This line is ignored by the engine.
description: >-
  Business accounts in Italy: higher limits,
  payroll and supplier transfers are normal.
```

The most common mistake is wrong indentation. The editor reports it with the line number, for example `YAML syntax error at line 4, column 29: mapping values are not allowed here`.

---

## 3. Conditions: the `when` language

Hard rules and overrides have a `when` condition. It reads like a spreadsheet formula, and the result is either true or false.

```yaml
when: "candidate.amount >= 3000 and candidate.channel == 'sepa_instant' and features.new_beneficiary"
```

The line above reads: *the amount is at least 3,000, the payment is an instant transfer, and the beneficiary has never been paid before*.

### What you can write

| You want | Write | Example |
|---|---|---|
| equal / not equal | `==` `!=` | `candidate.authentication != 'sca'` |
| compare numbers | `<` `<=` `>` `>=` | `customer.account_age_days < 30` |
| a range | `a <= x < b` | `1000 <= candidate.amount < 5000` |
| all conditions | `and` | `customer.vulnerable and candidate.amount > 1000` |
| any condition | `or` | `features.ip_geo_mismatch or features.new_country` |
| the opposite | `not` | `not features.new_device` |
| one of several values | `in [...]` | `candidate.channel in ['card_present', 'atm']` |
| in a list from the policy | `in lists.…` | `candidate.ip_country in lists.high_risk_countries` |
| a value from a table | `table[key]` | `features.amount_24h_total > limits.daily_amount[customer.limit_segment]` |
| arithmetic | `+ - * / %` | `candidate.amount > 2 * limits.atm_daily[customer.limit_segment]` |
| how many items | `len(...)` | `len(customer.recent_profile_changes) > 0` |
| larger / smaller of | `max(...)` `min(...)` | `max(features.amount_zscore, 0) > 8` |
| absolute value | `abs(...)` | `abs(features.amount_zscore) > 6` |
| group conditions | `( )` | `(features.new_device or features.ip_geo_mismatch) and candidate.amount > 500` |

A true/false feature can be used directly. `features.new_device` is the same as `features.new_device == True`.

### Fields that may be missing

Some parts of a payment exist only on some channels. For example, `merchant` exists only on card payments, `beneficiary` only on transfers and `mandate` only on direct debits. Reading a field of a missing part is an error, so **check that the part exists first**:

```yaml
# Wrong: rejected when the policy is loaded
when: "candidate.merchant.mcc == '7995'"
# Right: on a transfer there is no merchant, so the condition is simply false
when: "candidate.merchant and candidate.merchant.mcc == '7995'"
```

The validator catches this when you save, because it runs every condition on a sample payment that has no merchant and no beneficiary:

```
hard_rules[t]: "candidate.merchant.mcc == '7995'": Attribute 'mcc' does not exist in expression …
```

The **features** never have this problem: they always exist, on every channel (see [§4.3](#43-features-computed-for-every-payment)). Prefer them when one fits. For example, `features.high_risk_mcc` already checks the merchant category against `lists.high_risk_mcc`.

### What happens on errors

| When | What happens |
|---|---|
| A typo in a name, such as `features.new_devic` | **The policy is refused when you save it or when the engine starts.** A broken rule never reaches a payment. |
| A condition fails on one payment, for example on data the sample did not have | That payment gets **step-up**, and the error is recorded as the reason. The engine never approves silently. |

### What you cannot write

Conditions cannot call anything other than `len`, `min`, `max` and `abs`. They cannot import code, change values or read files. This is deliberate: a policy can be edited by people who cannot change the code, so it must not be able to run code.

---

## 4. What a condition can read

A condition sees five groups of names in hard rules. Overrides see a sixth group, `answers`.

| Name | What it is |
|---|---|
| `candidate` | The payment being checked. |
| `customer` | The account holder. |
| `features` | Numbers and yes/no facts computed from the payment and the history. |
| `lists` | The `lists` section of the policy. |
| `limits` | The `limits` section of the policy. |
| `answers` | The decision model's answers. **Overrides only.** |

### 4.1 `candidate`

| Name | Type | Example |
|---|---|---|
| `candidate.amount` | number | `4900.0` |
| `candidate.currency` | text | `'EUR'` |
| `candidate.channel` | text | `'card_present'`, `'card_not_present'`, `'atm'`, `'sepa_instant'`, `'sepa_credit_transfer'`, `'sepa_direct_debit'` |
| `candidate.authentication` | text | `'sca'`, `'none'`, `'exemption'` |
| `candidate.recurring` | yes/no | `True` |
| `candidate.ip_country` | text or empty | `'LT'` |
| `candidate.device_id` | text or empty | |
| `candidate.merchant.name` / `.mcc` / `.country` | text | **card payments only**: check `candidate.merchant` first |
| `candidate.beneficiary.iban` / `.name` / `.vop_result` | text | **transfers only**: check `candidate.beneficiary` first |
| `candidate.mandate.creditor_id` / `.signed_at` | text | **direct debits only**: check `candidate.mandate` first |
| `candidate.location.country` / `.lat` / `.lon` | | **card present and ATM**: check `candidate.location` first |

### 4.2 `customer`

| Name | Type | Example |
|---|---|---|
| `customer.id` | text | `'c_123'` |
| `customer.segment` | text | `'retail'` or `'business'` |
| `customer.vulnerable` | yes/no | |
| `customer.account_age_days` | number | `1450` |
| `customer.home_country` | text | `'IT'` |
| `customer.usual_countries` | list or `None` | `['US', 'MX']`, when the bank sends it |
| `customer.recent_profile_changes` | list | use with `len(...)` |
| `customer.limit_segment` | text | `'vulnerable'` for vulnerable customers, otherwise the segment. It is the key into `limits`. |

### 4.3 `features`: computed for every payment

Features are computed from the candidate and the last `history.payments` past payments. They always exist, on every channel. When something does not apply, a feature is `False` or `0`; when an event never happened, it holds the large value 1000000.

| Feature | Type | Meaning | Typical use |
|---|---|---|---|
| `amount_zscore` | number | How far the amount is from the customer's usual amounts, in robust standard deviations. 0 is usual, above 6 is very unusual. | Amount out of profile. |
| `amount_ratio_max` | number | Amount divided by the largest past amount. 2 means twice the largest ever. | |
| `is_round_amount` | yes/no | At least 100 and a multiple of 100. | Scams often ask for round sums. |
| `tx_count_10m`, `tx_count_1h` | number | Payments in the last 10 minutes or hour, including this one. | Velocity. |
| `small_tx_burst` | number | Payments of €5 or less in the last hour, including this one. | Card testing. |
| `amount_24h_total` | number | Total spent in 24 hours, including this payment. | Daily limits. |
| `km_from_last` | number | Distance from the last card-present or ATM payment. | |
| `implied_speed_kmh` | number | Speed needed to get here from a physical payment of the last 24 h. Above 900 is impossible. | Cloned card. |
| `ip_geo_mismatch` | yes/no | The IP country is not one the customer uses. | |
| `new_merchant`, `new_mcc` | yes/no | Never paid this merchant, or this merchant category, before. Card payments only. | |
| `high_risk_mcc` | yes/no | Merchant category in `lists.high_risk_mcc`. | Crypto, gambling, money transfer. |
| `new_country` | yes/no | A country the customer never paid in. | |
| `foreign_merchant` | yes/no | The payment's country is not the customer's home country. | Cross-border card use. |
| `unusual_country` | yes/no | A foreign country outside `customer.usual_countries`; without that list, the same as `new_country` for foreign countries. | Stolen card used abroad, even after a burst of payments there. |
| `high_risk_country`, `sanctioned_country` | yes/no | Any country involved (location, IP, merchant, IBAN) is in the policy's list. | |
| `new_device` | yes/no | A device never seen in the history. | Account takeover. |
| `profile_change_hours` | number | Hours since the last phone, e-mail or password change; 1000000 if none. | Account takeover. |
| `new_beneficiary` | yes/no | An IBAN never paid before. | Scams. |
| `vop_mismatch` | yes/no | Verification of Payee answered `no_match`. | Fake-operator scams. |
| `first_instant_payment` | yes/no | The customer's first instant transfer. | |
| `beneficiary_in_mule_list` | yes/no | The IBAN is in the policy's mule list file. | |
| `atm_withdrawals_24h`, `atm_amount_24h` | number | ATM withdrawals and their total over 24 h, including this one. | Cash-out. |
| `atm_country_vs_home` | yes/no | An ATM outside the home country. | |
| `new_creditor` | yes/no | A direct-debit creditor never seen before. | |
| `mandate_age_days` | number | Days since the direct-debit mandate was signed; 1000000 if no mandate. | Fraudulent mandates. |
| `dd_amount_vs_mandate_history` | number | This debit divided by the largest earlier debit of the same creditor. | |
| `recurring_matches_known` | yes/no | Recurring, same merchant or creditor, amount within 10% of an earlier one. | Lowers risk; PSD2 exemption. |
| `hour_deviation` | number | Distance from the customer's usual hours, 0 to 1. 0.5 means 6 hours away. | |
| `failed_attempts_24h` | number | Declined attempts in the last 24 h, for any reason. | |
| `credential_errors_24h` | number | Declined attempts in the last 24 h with a wrong PIN, CVV, card number, expiry date or ZIP code. | Someone who does not know the card's details. |
| `recent_credential_error` | yes/no | At least one such attempt in the last 24 h. | |
| `history_len` | number | How many past payments were read. | |

To see the real values for a payment, run it on the Test page, open the audit log and open the decision: *Computed features* lists them all.

### 4.4 `lists` and `limits`

These two names give access to the policy's own sections (see [§5.4](#54-lists-and-limits)). You can add your own lists and use them in conditions:

```yaml
lists:
  watched_customers: [c_001, c_042]
hard_rules:
  - id: watched_customer_large
    when: "customer.id in lists.watched_customers and candidate.amount > 1000"
    decision: hold
    reason: "Customer under review: large payments are checked by hand"
```

### 4.5 `answers` (overrides only)

After the model has answered, overrides can read its answers by question name:

| Question type | `answers.<name>` | Extra |
|---|---|---|
| `noul` (yes/no) | probability of *yes*, 0 to 1 | |
| `choice` | the most likely option, as text | `answers.<name>_confidence`: its probability, 0 to 1 |
| `score` | the expected level: 0 is the first level, 1 the second, and so on, with decimals | |

```yaml
when: "answers.scam_pattern == 'money_mule' and answers.scam_pattern_confidence > 0.6"
when: "answers.fraud_risk >= 2.5"     # fraud_risk has 4 levels, 0 to 3
```

---

## 5. The policy, section by section

Sections are shown in file order. Each example is written as you would put it in a policy that `extends` another (see [§6](#6-inheritance-with-extends)). Sections marked **required** must exist in the policy or in its parent.

### 5.1 Identity and governance (required)

```yaml
policy_id: retail-eu            # stable name; appears in every decision and audit record
description: >-                 # one sentence, shown on the Test page
  Production settings for EU retail accounts.
version: 3                      # increase it on every change
effective_from: 2026-11-01      # recorded with the policy; the engine does not enforce it
governance:
  author: fraud-strategy-team
  approved_by: risk-officer     # must differ from author: four-eyes principle
  change_ticket: CHG-2026-0412
  mode: enforce                 # enforce | shadow
```

- **`mode: shadow`** makes the engine decide and record as usual. Each decision carries `enforced: false`, so the calling system does not act on it. Use it to observe a new policy on live traffic before switching it on.
- **Four eyes.** The engine refuses a policy whose `approved_by` equals `author`. The comparison ignores letter case.
- **Identity in every decision.** Each decision records `policy_id@version` and a hash of the policy's full content, for example `retail-eu@1 (sha256:08e307540291)`. Any change, however small, changes the hash. The audit log therefore always shows exactly which rules decided.

### 5.2 Privacy

```yaml
privacy:
  pseudonymize: [beneficiary.iban, beneficiary.name, device_id, mandate.creditor_id, mandate.mandate_id]
  drop_fields_before_model: [description, merchant.name, location.lat, location.lon, transaction_id]
  allow_external_backend: true
```

| Key | Effect |
|---|---|
| `pseudonymize` | Fields replaced by a keyed hash before the model sees them. The same IBAN always gives the same hash, so the model can still tell "known" from "new", but cannot read the value. |
| `drop_fields_before_model` | Fields removed entirely. |
| `allow_external_backend` | `false` forbids sending anything to Regolo. The engine then refuses to start with the Regolo backend, so use `routing.mode: never`. |

### 5.3 History

```yaml
history:
  payments: 10          # 1 to 50
```

This sets how many of the customer's most recent payments are read. They feed the features, and they are sent to the model.

| More payments | Fewer payments |
|---|---|
| Steadier view of what is usual for the customer. Monthly payments such as rent and subscriptions stay in view. | Fewer tokens, faster answers. |
| Every payment adds about 140 input tokens per model call. | Monthly payments drop out and start to look new. |

Measured on the 12 hand-written payments with the model always asked:

| Payments | Tokens per call | Correct |
|---|---|---|
| 5 | ~1,700 | 11 of 12: the monthly streaming subscription looked new |
| 10 | ~2,460 | 12 of 12 |
| 30 | ~5,100 | 12 of 12, about 3 times slower |

### 5.4 Lists and limits

```yaml
lists:
  sanctioned_countries: [KP, IR, SY, CU, RU, BY]
  high_risk_countries: [NG, GH, KH, MM]
  high_risk_mcc: ["4829", "6051", "6540", "7995", "5967"]   # quote codes: "0742" must stay text
  mule_beneficiaries_file: ../lists/mule_ibans.txt

limits:                                   # one row per limit, one column per customer.limit_segment
  daily_amount: { retail: 5000, business: 50000, vulnerable: 1500 }
  atm_daily:    { retail: 1000, business: 3000,  vulnerable: 500 }
```

- **Built-in lists.** `sanctioned_countries`, `high_risk_countries` and `high_risk_mcc` feed the features of the same name. `mule_beneficiaries_file` is a text file with one IBAN per line; spaces are ignored and lines starting with `#` are comments. Its path is relative to the policy file.
- **Your own lists and limits.** Any other list or limit you add can be used in conditions, as in [§4.4](#44-lists-and-limits).
- **`limits` keys.** Every limit you read with `[customer.limit_segment]` needs the three keys `retail`, `business` and `vulnerable`.

### 5.5 Hard rules (required)

```yaml
hard_rules:
  - id: sanctions_country
    when: "features.sanctioned_country"
    decision: block
    reason: "Country subject to sanctions"
  - id: account_takeover_pattern
    when: "features.profile_change_hours < 48 and features.new_device and features.new_beneficiary"
    decision: hold
    reason: "Recent contact change + new device + new beneficiary; verify out of band"
  - id: known_recurring
    when: "features.recurring_matches_known and not features.new_device"
    decision: approve
    reason: "Matches an established recurring payment"
```

| Key | Meaning |
|---|---|
| `id` | Short name; appears in the decision's reasons and in the audit. |
| `when` | The condition ([§3](#3-conditions-the-when-language)). |
| `decision` | `approve`, `step_up`, `hold` or `block`. |
| `reason` | Plain-language explanation for the analyst and the audit. |

- **Order matters: the first rule that matches decides**, and later rules are not checked. Put the most serious rules first (sanctions, mules) and the "safe" approvals last. Otherwise a known subscription could be approved before the sanctions rule is reached.
- **A hard rule decides immediately.** The model is not asked.
- **Choose the decision with the channel in mind.** For an account takeover, use `hold` rather than `step_up`: a one-time code would go to the phone number the fraudster just changed.

### 5.6 PSD2 exemptions (required)

A remote payment (card online, instant or ordinary transfer) approved without strong customer authentication must use a PSD2 exemption. Otherwise the engine turns it into a step-up.

```yaml
sca:
  current_fraud_rate_bps: { card_not_present: 5, credit_transfer: 0.8 }   # the bank's reported rates
  tra_thresholds_eur:
    card_not_present: [{max_rate_bps: 1, eur: 500}, {max_rate_bps: 6, eur: 250}, {max_rate_bps: 13, eur: 100}]
    credit_transfer:  [{max_rate_bps: 0.5, eur: 500}, {max_rate_bps: 1, eur: 250}, {max_rate_bps: 1.5, eur: 100}]
  exempt_only_if_risk_below: 0.20
```

- **Recurring payments** that match an earlier one are exempt.
- **Transaction risk analysis (TRA).** The exemption applies only when two things are true:
  - the payment's risk is below `exempt_only_if_risk_below`;
  - its amount is within the band allowed by the bank's current fraud rate.

  Example: with a card fraud rate of 5 basis points, the tiers up to 6 and 13 apply, so card payments up to €250 can be exempt.
- **Keep the rates current.** Update `current_fraud_rate_bps` from the bank's fraud reporting.

### 5.7 Quick score (required)

```yaml
prescore:
  weights:                    # must add up to 1
    amount_zscore: 0.20
    new_device: 0.15
    new_beneficiary: 0.10
    ip_geo_mismatch: 0.10
    new_country: 0.10
    high_risk_mcc: 0.10
    new_merchant: 0.10
    new_creditor: 0.05
    first_instant_payment: 0.05
    hour_deviation: 0.05
```

The quick score is a weighted sum of features, from 0 to 1. Each feature is first converted to a value between 0 and 1:

| Feature | Converted value |
|---|---|
| any yes/no feature | yes = 1, no = 0 |
| `amount_zscore` | 0 at 0, rising to 1 at 10 |
| `amount_ratio_max` | 0 up to the largest past amount, 1 at five times it |
| `hour_deviation` | 0 up to 0.1, 1 at 0.5 |
| `tx_count_1h` | 0 up to 2 payments, 1 at 7 |
| `dd_amount_vs_mandate_history` | 0 up to 1.5×, 1 at 4.5× |
| `credential_errors_24h` | 0 at none, 1 at three or more |

- **Allowed features.** Only these numeric features and the yes/no features can be weighted. Any other name is refused.
- **Example.** A new device (0.15) plus a new beneficiary (0.10) plus an amount z-score of 5 (0.20 × 0.5 = 0.10) gives a quick score of 0.35.

### 5.8 Routing (required)

```yaml
routing:
  mode: cascade                    # cascade | always | never
  approve_if_prescore_below: 0.15
  block_if_prescore_above: 0.95
  always_call_model_if:
    amount_at_least: 500
    channels: [sepa_instant]
```

**How `cascade` decides each payment the hard rules let through:**

1. If the amount is at least `amount_at_least`, or the channel is in `channels`, the payment **goes to the model**.
2. Otherwise, a quick score below `approve_if_prescore_below` means **approve**.
3. A quick score above `block_if_prescore_above` means **block**.
4. Anything in between **goes to the model**.

**The other two modes:**

- `always` sends every payment the hard rules let through to the model.
- `never` decides on the quick score alone, using the thresholds of [§5.11](#511-decision-required).

The Test page can override `mode` for a run, to compare the three modes.

**Tuning:**

- Raising `approve_if_prescore_below` sends fewer payments to the model: cheaper and faster, but the model sees fewer borderline cases.
- Adding channels or lowering `amount_at_least` does the opposite.
- The Test page shows the effect before you run: the exact number of model calls per combination.

### 5.9 The decision model (required)

```yaml
model:
  backend: regolo                 # regolo | fake (offline stand-in, for tests)
  name: clef-flash
  timeout_ms:                     # how long to wait for an answer, per channel
    card_present: 150
    atm: 300
    card_not_present: 300
    sepa_instant: 800
    default: 500                  # required
  circuit_breaker: { failure_ratio: 0.2, window_s: 30, open_s: 60, min_calls: 5 }
```

- **`timeout_ms`.** If no answer arrives in time, the channel's fail mode decides (see [§5.11](#511-decision-required)). Card payments need short timeouts, because the card network waits for the answer. Transfers can wait longer.
- **`circuit_breaker`.** If at least `min_calls` calls happened in the last `window_s` seconds and `failure_ratio` of them failed, the engine stops asking the model for `open_s` seconds. In that window the fail mode decides at once, instead of every payment waiting for a timeout.

### 5.10 Questions to the model (required)

The model answers each question with probabilities, in one call. **Every question re-reads the whole payment and history**, so each one adds input tokens and time. On Regolo, five questions cost about 6,100 tokens and two about 2,500.

There are three question types:

```yaml
questions:
  # 1. choice: pick the option that fits best; each option has a risk from 0 to 1
  scam_pattern:
    type: choice
    weight: 0.40
    instructions: Which fraud pattern best fits the candidate payment?
    criteria:                                   # option: what it means (the model reads this)
      none: No fraud pattern, behaviour consistent with the customer's habits
      card_fraud: Unauthorised use of a cloned or stolen card
      app_scam: Customer appears manipulated into paying a fraudster
      account_takeover: Payment initiated by a third party controlling the account
    risk_by_option: { none: 0.0, card_fraud: 1.0, app_scam: 0.9, account_takeover: 1.0 }   # same options

  # 2. score: a scale; the first level is the lowest risk
  fraud_risk:
    type: score
    weight: 0.60
    instructions: Rate the overall risk that the candidate payment is fraud against the account holder.
    criteria:
      - Consistent with the customer's habits
      - Unusual but plausible
      - Suspicious, needs verification
      - Very likely fraudulent

  # 3. noul: yes or no
  amount_anomalous:
    type: noul
    weight: 0.10
    instructions: Is the candidate amount anomalous compared with the customer's habits?
```

**Rules the validator enforces:**

- **Weights.** The `weight` of all questions adds up to 1.
- **`choice`.** At least two options, and `risk_by_option` lists exactly the same options as `criteria`.
- **`score`.** At least two levels.

**How each answer becomes a risk from 0 to 1:**

| Type | Risk | Example |
|---|---|---|
| `noul` | the probability of *yes* | 0.8 |
| `choice` | each option's probability × its `risk_by_option`, summed | 70% app_scam (0.9) + 30% none (0) = 0.63 |
| `score` | the expected level ÷ (levels − 1) | expected level 2.4 of 0–3 → 0.8 |

The model's risk is the weighted sum of the questions' risks.

**Writing good questions:**

- One idea per question, in plain words, about the candidate payment.
- For `choice`, make the options mutually exclusive, and include a "nothing wrong" option with risk 0.
- Prefer `choice` and `score`. Measured on Regolo, yes/no answers tend to come back as almost exactly 0 or 1, while `choice` and `score` give graded probabilities. That is why the shipped policy uses two questions and keeps the yes/no ones only in `retail-eu-explainable`, for explanation.

### 5.11 Decision (required)

```yaml
decision:
  combine: { prescore: 0.4, model: 0.6 }        # must add up to 1
  thresholds:
    default:    { step_up: 0.40, hold: 0.65, block: 0.80 }    # required
    vulnerable: { step_up: 0.25, hold: 0.50, block: 0.70 }
    # business: { step_up: 0.50, hold: 0.75, block: 0.90 }    # optional, per segment
  overrides:
    - when: "answers.scam_pattern == 'app_scam' and answers.scam_pattern_confidence >= 0.70 and candidate.channel == 'sepa_instant'"
      decision: hold
      reason: "Likely authorised push payment scam: call the customer before releasing"
  on_backend_failure:
    card_present: use_prescore
    sepa_instant: step_up
    sepa_direct_debit: hold
    default: step_up                            # required
  unavailable_actions:
    sepa_direct_debit: { step_up: hold }        # the payer is not online during a direct debit
```

**`combine`** sets how much the quick score and the model count in the final risk: `risk = 0.4 × quick score + 0.6 × model risk`.

**`thresholds`** turn that risk into a decision. Below `step_up` the payment is approved; from `step_up` it gets a step-up, from `hold` a hold, from `block` a block. They must increase: `0 ≤ step_up < hold < block ≤ 1`. The engine picks the row in this order:

1. `vulnerable`, for vulnerable customers, if the row exists;
2. the row named after the customer's segment (`retail` or `business`), if it exists;
3. `default`.

**`overrides`** are checked after the thresholds. The first one that matches replaces the decision. They are the place to act on what the model said, for example on a confident "account takeover".

**`on_backend_failure`** decides, per channel, what happens when the model does not answer in time, or the circuit breaker is open. The value is a decision, or `use_prescore`, which applies the thresholds to the quick score alone. Choose by what the channel can bear:

- In a shop (`card_present`), refusing a genuine customer is costly, so the quick score decides.
- An instant transfer cannot be recalled, so a step-up is safer.

**`unavailable_actions`** replaces a decision a channel cannot carry out. A direct debit happens without the payer online, so a step-up becomes a hold.

### 5.12 Audit

```yaml
audit:
  sink: logs/decisions.jsonl
  hash_chain: true
  retention_days: 3650
  log_model_payload: pseudonymized      # pseudonymized | none
```

- `hash_chain` links each record to the previous one, so an edited or deleted line breaks the chain.
- `log_model_payload: none` leaves the data sent to the model out of the audit record.
- In this proof of concept, `sink` and `retention_days` are recorded with the policy, but they do not change where the log is written or how long it is kept. The console and the command line write to `logs/decisions.jsonl`.

---

## 6. Inheritance with `extends`

A policy can start from another one and list only what changes:

```yaml
extends: retail-eu.yaml          # a file in the same folder
policy_id: retail-eu
description: retail-eu's rules with a 2-second wait for the model, so the shared API can answer.
governance:
  change_ticket: POC-001
model:
  timeout_ms: { card_present: 2000, atm: 2000, card_not_present: 2000, sepa_instant: 2000, default: 2000 }
```

The result is the parent with the child's changes applied. **How a change is applied depends on what it is**, and this is the most important thing to know about inheritance.

| In the child | Result | Example |
|---|---|---|
| a **group** (`key:` with keys under it) | merged key by key: keys you write replace the parent's, the others are kept | `governance: {change_ticket: X}` keeps the parent's author and approver |
| a **list** (`- ` items or `[...]`) | **replaces the parent's list entirely** | `hard_rules:` with one rule leaves the policy with **that one rule** |
| a single value | replaces it | `version: 4` |

This has three practical consequences:

- **Adding a hard rule or an override.** The new list replaces the old one, so a child must repeat the whole list. Either make a **full copy** (console: *New policy* → *Full copy*) and edit the list there, or copy the parent's `hard_rules:` into the child and add your rule.
- **Adding a value to a list,** such as one more MCC code: repeat the whole list with the new value.
- **Changing weights.** `prescore.weights` and `questions` are groups, so they merge. If the child changes one weight, the total no longer adds up to 1 and the policy is refused. Restate all the weights so they add up to 1. To remove a feature from the quick score, set its weight to 0.

The inheritance chain can have several levels (`retail-eu-explainable` → `retail-eu` → `retail-eu`). The parent must be in the same folder. A loop is refused.

When you save a parent in the console, every policy that inherits it is checked again. If one would stop loading, the save is undone and the console tells you which one broke.

---

## 7. Recipes

Each recipe is a complete child policy that you can paste into *New policy* (inherit from `retail-eu`) and validate. To compare the result with the original:

1. Open *Test* and select both policies.
2. Pick a set of payments.
3. Look at fraud stopped, genuine customers interrupted, time and cost.

### 7.1 Stricter thresholds for vulnerable customers

```yaml
extends: retail-eu.yaml
policy_id: eu-vulnerable-strict
description: poc with earlier step-ups and holds for vulnerable customers.
decision:
  thresholds:
    vulnerable: { step_up: 0.20, hold: 0.40, block: 0.65 }
```

Only the `vulnerable` row changes; `default` is inherited.

### 7.2 Separate thresholds for business accounts

```yaml
extends: retail-eu.yaml
policy_id: eu-business
description: poc with more tolerant thresholds for business accounts, which make larger and rarer payments.
decision:
  thresholds:
    business: { step_up: 0.50, hold: 0.75, block: 0.90 }
limits:
  daily_amount: { retail: 5000, business: 150000, vulnerable: 1500 }
```

### 7.3 One more high-risk merchant category

```yaml
extends: retail-eu.yaml
policy_id: eu-mcc
description: poc that also treats securities brokers (MCC 6211) as high risk.
lists:
  high_risk_mcc: ["4829", "6051", "6540", "7995", "5967", "6211"]   # the whole list, plus 6211
```

Lists replace, so the full list is repeated ([§6](#6-inheritance-with-extends)).

### 7.4 Block a known mule account

You do not need to change the policy for this. Add the IBAN as one line in `lists/mule_ibans.txt`:

```
# added 2026-10-13, case 4411
LT121000011101001000
```

The next payment to that IBAN is blocked by the `known_mule_beneficiary` rule.

### 7.5 A new hard rule

Make a **full copy** of `retail-eu`, which repeats the whole list, and insert the rule in the right place in `hard_rules`, before `known_recurring`:

```yaml
  - id: gambling_vulnerable
    when: "customer.vulnerable and candidate.merchant and candidate.merchant.mcc == '7995'"
    decision: block
    reason: "Gambling payment by a vulnerable customer"
```

Two more rules, as further examples of the syntax:

```yaml
  - id: young_account_large_instant
    when: "customer.account_age_days < 30 and candidate.channel == 'sepa_instant' and candidate.amount >= 1000"
    decision: hold
    reason: "Account opened less than 30 days ago sends a large instant transfer"
  - id: atm_burst_abroad
    when: "features.atm_country_vs_home and features.atm_withdrawals_24h >= 3"
    decision: block
    reason: "Third ATM withdrawal abroad in 24 hours"
```

### 7.6 Ask the model more often

```yaml
extends: retail-eu.yaml
policy_id: eu-more-model
description: poc that asks the model from 250 euro and on every transfer.
routing:
  approve_if_prescore_below: 0.10
  always_call_model_if:
    amount_at_least: 250
    channels: [sepa_instant, sepa_credit_transfer]
```

Step 4 of the Test page shows how many more model calls this makes, and their cost, before you run.

### 7.7 Add a question to the model

```yaml
extends: retail-eu.yaml
policy_id: eu-merchant-question
description: poc plus a yes/no question on unusual merchants.
questions:
  merchant_unusual:
    type: noul
    weight: 0.20
    instructions: Is the merchant or the merchant category unusual for this customer?
  scam_pattern:
    weight: 0.30            # was 0.40
  fraud_risk:
    weight: 0.50            # was 0.60: 0.20 + 0.30 + 0.50 = 1
```

Questions merge by name, so the two existing questions keep their text and options; only their weights change. Expect roughly 1,200 more input tokens per model call.

### 7.8 Act on a model answer

Overrides are a list, so as with hard rules, copy the parent's `overrides` and add yours:

```yaml
extends: retail-eu.yaml
policy_id: eu-mule-override
description: poc that holds payments the model confidently sees as money-mule activity.
decision:
  overrides:
    - when: "answers.scam_pattern == 'account_takeover' and answers.scam_pattern_confidence >= 0.70 and features.new_device"
      decision: block
      reason: "Model is confident of account takeover on a new device"
    - when: "answers.scam_pattern == 'app_scam' and answers.scam_pattern_confidence >= 0.70 and candidate.channel == 'sepa_instant'"
      decision: hold
      reason: "Likely authorised push payment scam: call the customer before releasing"
    - when: "answers.scam_pattern == 'money_mule' and answers.scam_pattern_confidence >= 0.60"
      decision: hold
      reason: "Model sees money-mule activity"
```

### 7.9 A safer fallback for instant transfers

```yaml
extends: retail-eu.yaml
policy_id: eu-instant-hold
description: poc that holds instant transfers when the model cannot answer.
decision:
  on_backend_failure:
    sepa_instant: hold
```

### 7.10 Try a policy without acting on it

```yaml
extends: retail-eu.yaml
policy_id: eu-shadow
description: poc in shadow mode, to observe its decisions without acting on them.
governance:
  mode: shadow
```

Each decision is recorded with `enforced: false`.

---

## 8. Adapting the engine to another kind of risk

The same engine can serve another portfolio or another risk, as long as the work fits the request format and the features of [§4](#4-what-a-condition-can-read). For example, a policy for small-business accounts:

```yaml
extends: retail-eu.yaml
policy_id: sme-it
description: Small-business accounts in Italy, where payroll and supplier transfers are normal and invoice fraud is the main threat.
version: 1
effective_from: 2026-12-01
governance:
  author: sme-risk-team
  approved_by: head-of-fraud
  change_ticket: CHG-2026-0500
history:
  payments: 20                         # monthly payroll and suppliers stay in view
limits:
  daily_amount: { retail: 5000, business: 150000, vulnerable: 1500 }
routing:
  always_call_model_if:
    amount_at_least: 10000
    channels: [sepa_instant]
decision:
  thresholds:
    business: { step_up: 0.45, hold: 0.70, block: 0.85 }
questions:
  scam_pattern:                        # the existing options are kept; one is added
    criteria:
      invoice_redirection: A supplier's bank details changed shortly before a large payment (business e-mail compromise)
    risk_by_option:
      invoice_redirection: 1.0
```

The `scam_pattern` question gains an option because `criteria` and `risk_by_option` are groups, and groups merge.

**What a policy can change:**

- rules and their order;
- lists and limits;
- the weights of the quick score;
- routing;
- the questions to the model, their wording and options;
- the thresholds, overrides and fallbacks;
- the history length.

**What needs a code change:**

| Change | Where |
|---|---|
| A new field in the request, such as the merchant's risk rating or the session duration | `src/fraudclef/models.py` |
| A new feature, such as "first payment to this country this year" | Add it to `compute_features` in `src/fraudclef/features.py`. To weight it in the quick score: if it is yes/no, add its name to `_BOOL_FEATURES` in `policy.py`; if it is a number, add a conversion to `PRESCORE_NORMALISERS`. |
| A new channel | `Channel` in `models.py`, plus the features that depend on it |

After a code change, run `uv run pytest -q` and `./run.sh check`.

---

## 9. Validation and error messages

**When a policy is checked:** on every edit in the console, on save, at `./run.sh check`, and every time the engine loads a policy.

**What is checked:**

- **YAML syntax**, with the line and column of the error.
- **Field names.** An unknown key is refused, so a typo cannot be silently ignored.
- **Values.** Decisions are one of the four allowed; channels are known; numbers are in range.
- **Weights.** Quick-score weights, question weights and `combine` each add up to 1.
- **Thresholds** increase: `step_up < hold < block`.
- **Questions.** `choice` and `score` questions are well formed.
- **Four eyes.** Author and approver differ.
- **`default` entries.** `thresholds` and `on_backend_failure` each have a `default` row.
- **Routing.** `approve_if_prescore_below` is lower than `block_if_prescore_above`.
- **Dry run.** Every `when` condition of the hard rules and overrides is run on a sample payment.
- **Files.** The parent file and the mule list file exist and stay inside the project.

**Common messages:**

| Message (shortened) | Cause | Fix |
|---|---|---|
| `YAML syntax error at line 4, column 29: mapping values are not allowed here` | Wrong indentation, or a `:` inside unquoted text. | Align the line with its siblings; put text containing `:` in quotes. |
| `routing.approve_below: Extra inputs are not permitted` | Unknown key, usually a typo. | Check the name in [§5](#5-the-policy-section-by-section). |
| `prescore.weights must sum to 1 (got 1.3500)` | A weight changed without rebalancing the others; in a child policy, the weights merged with the parent's. | Restate all the weights so they add up to 1. |
| `questions[*].weight must sum to 1 (got 1.1000)` | The same, for questions. | |
| `four-eyes principle: approved_by must differ from author` | Same person in both fields. | Name the real approver. |
| `thresholds must satisfy 0 <= step_up < hold < block <= 1` | Thresholds out of order. | |
| `hard_rules.0.decision: Input should be 'approve', 'step_up', 'hold' or 'block'` | A decision such as `reject`. | Use one of the four. |
| `hard_rules[t]: 'features.new_devic': Attribute 'new_devic' does not exist` | A typo in a name. | Check the name in [§4](#4-what-a-condition-can-read). |
| `Attribute 'mcc' does not exist in expression 'candidate.merchant.mcc …'` | A field of a part that may be missing. | Write `candidate.merchant and candidate.merchant.mcc …` ([§3](#fields-that-may-be-missing)). |
| `prescore.weights reference unknown features: [...]` | A feature that does not exist or cannot be weighted. | See the list in [§5.7](#57-quick-score-required). |
| `choice questions need risk_by_option for exactly the criteria options` | An option in one list and not in the other. | |
| `extends: 'x.yaml' not found` | Wrong file name. | The parent must be in `policies/`. |
| `not saved: this change breaks a policy that extends it` | The change makes a child policy invalid. | Fix the child too, or adjust the change. |

---

## 10. A safe change process

1. **Create a new policy.** Inherit the current one, or copy it, and give it a new `policy_id` or a higher `version`. Fill in `governance`: author, approver, change ticket.
2. **Validate.** The editor does it as you type; `./run.sh check` does it for every policy.
3. **Compare.** On the Test page, select the current and the new policy, and the routing you use. Run them on the hand-written set (each payment has the decision an analyst expects) and on a generated set with the mix of fraud you care about. Check:
   - fraud stopped, overall and by type;
   - genuine customers interrupted;
   - time per payment;
   - cost.
4. **Read the differences.** Open the cards and *Show every payment*. Each payment shows its reasons and the model's answers.
5. **Observe without acting.** Run the new policy in `mode: shadow` on real traffic. Its decisions are recorded with `enforced: false`.
6. **Switch on.** Set `mode: enforce`. The audit log ties every decision to the exact policy content through its hash, and `policies/.history/` keeps every earlier version saved from the console.

The test sets are synthetic, and the fraud in the random set is easy on purpose. A change should be judged on the bank's own labelled payments before production ([USING.md §9](USING.md#9-test-data)).

---

## Appendix: the score arithmetic

For a payment that reaches the model:

```
quick score   = Σ weight(feature) × converted value(feature)                (capped at 1)
model risk    = Σ weight(question) × risk(answer)                           (capped at 1)
risk          = combine.prescore × quick score + combine.model × model risk
decision      = thresholds(risk) → overrides → unavailable_actions → PSD2 check
```

**Worked example.** Instant transfer of €4,900 to a new IBAN, Verification of Payee `no_match`, policy `retail-eu`, routing *on every payment*. The `vop_no_match_large` hard rule is skipped here to show the arithmetic.

| Step | Value |
|---|---|
| Quick score | amount z-score 1.0 × 0.20 + new beneficiary 1 × 0.10 + first instant payment 1 × 0.05 = **0.35** |
| Model, `scam_pattern` | 80% app_scam (0.9) + 20% none (0) = 0.72; × weight 0.40 = 0.288 |
| Model, `fraud_risk` | expected level 2.4 of 0–3 = 0.80; × weight 0.60 = 0.48 |
| Model risk | 0.288 + 0.48 = **0.768** |
| Risk | 0.4 × 0.35 + 0.6 × 0.768 = **0.601** |
| Thresholds (`default`) | 0.601 ≥ 0.40 (step-up) and < 0.65 (hold): **step_up** |
| Overrides | `app_scam` with confidence 0.80 ≥ 0.70 on `sepa_instant` → **hold** |
