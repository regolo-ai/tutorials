"""Deterministic feature engineering over the candidate and the customer's history.

The model is weak at arithmetic, so every number it sees is computed here. All features are
always present and never None, so policy expressions can compare them safely.
"""

from __future__ import annotations

import math
import statistics
from datetime import timedelta

from .models import PHYSICAL_CHANNELS, ScoringRequest, Transaction

SMALL_AMOUNT_EUR = 5.0
# Declined attempts that point at someone who does not know the card's details.
CREDENTIAL_ERRORS = {"bad_pin", "bad_cvv", "bad_card_number", "bad_expiration", "bad_zipcode"}
NO_EVENT_HOURS = 1e6  # sentinel for "never happened"


def _haversine_km(a, b) -> float:
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def tx_country(tx: Transaction) -> str | None:
    if tx.location and tx.location.country:
        return tx.location.country
    if tx.merchant and tx.merchant.country:
        return tx.merchant.country
    if tx.beneficiary:
        return tx.beneficiary.country
    return None


def _merchant_key(tx: Transaction) -> str | None:
    if tx.mandate:
        return f"creditor:{tx.mandate.creditor_id}"
    if tx.merchant and tx.merchant.name:
        return tx.merchant.name.strip().upper()
    if tx.beneficiary:
        return f"iban:{tx.beneficiary.iban}"
    return None


def robust_zscore(amount: float, history_amounts: list[float]) -> float:
    """(x - median) / (1.4826 * MAD), with a floor on the scale so tiny or flat histories
    do not explode. Robust statistics stop one large rent payment from masking anomalies."""
    if not history_amounts:
        return 0.0
    med = statistics.median(history_amounts)
    mad = statistics.median(abs(a - med) for a in history_amounts)
    scale = max(1.4826 * mad, 0.1 * med, 1.0)
    return (amount - med) / scale


def compute_features(req: ScoringRequest, lists: dict, mule_ibans: set[str]) -> dict[str, float | bool | int | str]:
    c = req.candidate
    hist = [t for t in req.history if t.timestamp < c.timestamp]
    t0 = c.timestamp

    def within(delta: timedelta) -> list[Transaction]:
        return [t for t in hist if t0 - t.timestamp <= delta]

    amounts = [t.amount for t in hist]
    z = robust_zscore(c.amount, amounts)
    max_hist = max(amounts, default=0.0)

    last_10m, last_1h, last_24h = within(timedelta(minutes=10)), within(timedelta(hours=1)), within(timedelta(hours=24))

    # Impossible travel: the highest implied speed between the candidate and any physical
    # transaction of the last 24 h (card present or ATM). Remote payments carry the
    # merchant's location, not the customer's, so they are excluded.
    km_from_last, max_speed = 0.0, 0.0
    if c.channel in PHYSICAL_CHANNELS and c.location:
        physical = [t for t in last_24h if t.channel in PHYSICAL_CHANNELS and t.location]
        if physical:
            km_from_last = _haversine_km(physical[-1].location, c.location)
        for t in physical:
            km = _haversine_km(t.location, c.location)
            hours = max((t0 - t.timestamp).total_seconds() / 3600, 1 / 60)
            if km > 50:  # ignore GPS noise inside the same city
                max_speed = max(max_speed, km / hours)

    known_countries = {req.customer.home_country} | {x for t in hist if (x := tx_country(t))}
    country = tx_country(c)
    countries_involved = {x for x in (country, c.ip_country, c.merchant.country if c.merchant else None,
                                      c.beneficiary.country if c.beneficiary else None) if x}

    known_merchants = {k for t in hist if (k := _merchant_key(t))}
    known_mccs = {t.merchant.mcc for t in hist if t.merchant and t.merchant.mcc}
    known_devices = {t.device_id for t in hist if t.device_id}
    known_ibans = {t.beneficiary.iban for t in hist if t.beneficiary}
    known_creditors = {t.mandate.creditor_id for t in hist if t.mandate}

    # Hours since the most recent profile change (phone, email, password) before the candidate.
    changes = [ch.at for ch in req.customer.recent_profile_changes if ch.at <= t0]
    profile_change_hours = (t0 - max(changes)).total_seconds() / 3600 if changes else NO_EVENT_HOURS

    # Time-of-day deviation: circular distance (hours) to the nearest habitual hour, scaled to [0, 1].
    hours = [t.timestamp.hour + t.timestamp.minute / 60 for t in hist]
    ch = c.timestamp.hour + c.timestamp.minute / 60
    hour_dev = min((min(abs(ch - h), 24 - abs(ch - h)) for h in hours), default=0.0)

    # Recurring payment matching an established one (same merchant/creditor, amount within 10%).
    key = _merchant_key(c)
    recurring_match = c.recurring and any(
        _merchant_key(t) == key and abs(t.amount - c.amount) <= 0.1 * t.amount for t in hist
    )

    dd_ratio = 0.0
    if c.mandate:
        prev = [t.amount for t in hist if t.mandate and t.mandate.creditor_id == c.mandate.creditor_id]
        dd_ratio = c.amount / max(prev) if prev else 0.0

    atm_24h = [t for t in last_24h if t.channel == "atm"]
    is_atm = c.channel == "atm"

    return {
        "amount_zscore": round(z, 2),
        "amount_ratio_max": round(c.amount / max_hist, 2) if max_hist else 0.0,
        "is_round_amount": c.amount >= 100 and c.amount % 100 == 0,
        "tx_count_10m": len(last_10m) + 1,
        "tx_count_1h": len(last_1h) + 1,
        "small_tx_burst": sum(1 for t in last_1h if t.amount <= SMALL_AMOUNT_EUR) + (c.amount <= SMALL_AMOUNT_EUR),
        "amount_24h_total": round(sum(t.amount for t in last_24h) + c.amount, 2),
        "km_from_last": round(km_from_last, 1),
        "implied_speed_kmh": round(max_speed, 1),
        "ip_geo_mismatch": bool(c.ip_country) and c.ip_country not in known_countries,
        # Card merchants only: transfers and debits have their own novelty features
        # (new_beneficiary, new_creditor), so they are not counted twice.
        "new_merchant": c.merchant is not None and key not in known_merchants,
        "new_mcc": bool(c.merchant and c.merchant.mcc) and c.merchant.mcc not in known_mccs,
        "high_risk_mcc": bool(c.merchant and c.merchant.mcc in set(lists.get("high_risk_mcc", []))),
        "new_country": country is not None and country not in known_countries,
        "foreign_merchant": country is not None and country != req.customer.home_country,
        # Like new_country, but against the profile's usual countries when the bank sends them.
        "unusual_country": country is not None and country != req.customer.home_country
        and country not in (set(req.customer.usual_countries) if req.customer.usual_countries is not None else known_countries),
        "high_risk_country": bool(countries_involved & set(lists.get("high_risk_countries", []))),
        "sanctioned_country": bool(countries_involved & set(lists.get("sanctioned_countries", []))),
        "new_device": c.device_id is not None and c.device_id not in known_devices,
        "profile_change_hours": round(profile_change_hours, 1),
        "new_beneficiary": c.beneficiary is not None and c.beneficiary.iban not in known_ibans,
        "vop_mismatch": bool(c.beneficiary and c.beneficiary.vop_result == "no_match"),
        "first_instant_payment": c.channel == "sepa_instant" and not any(t.channel == "sepa_instant" for t in hist),
        "beneficiary_in_mule_list": bool(c.beneficiary and c.beneficiary.iban in mule_ibans),
        "atm_withdrawals_24h": len(atm_24h) + is_atm,
        "atm_amount_24h": round(sum(t.amount for t in atm_24h) + (c.amount if is_atm else 0.0), 2),
        "atm_country_vs_home": is_atm and country is not None and country != req.customer.home_country,
        "new_creditor": c.mandate is not None and c.mandate.creditor_id not in known_creditors,
        "mandate_age_days": round((t0 - c.mandate.signed_at).total_seconds() / 86400, 1) if c.mandate else NO_EVENT_HOURS,
        "dd_amount_vs_mandate_history": round(dd_ratio, 2),
        "recurring_matches_known": recurring_match,
        "hour_deviation": round(hour_dev / 12, 2),
        "failed_attempts_24h": sum(1 for t in last_24h if t.errors),
        "credential_errors_24h": sum(1 for t in last_24h if CREDENTIAL_ERRORS & set(t.errors)),
        "recent_credential_error": any(CREDENTIAL_ERRORS & set(t.errors) for t in last_24h),
        "history_len": len(hist),
    }


# How each feature maps to [0, 1] for the pre-score. Booleans are 0/1.
PRESCORE_NORMALISERS = {
    "amount_zscore": lambda v: min(max(v / 10, 0.0), 1.0),
    "amount_ratio_max": lambda v: min(max((v - 1) / 4, 0.0), 1.0),
    "hour_deviation": lambda v: min(max((v - 0.1) / 0.4, 0.0), 1.0),
    "tx_count_1h": lambda v: min(max((v - 2) / 5, 0.0), 1.0),
    "dd_amount_vs_mandate_history": lambda v: min(max((v - 1.5) / 3, 0.0), 1.0),
    "credential_errors_24h": lambda v: min(v / 3, 1.0),
}


def normalise(name: str, value) -> float:
    if isinstance(value, bool):
        return float(value)
    fn = PRESCORE_NORMALISERS.get(name)
    if fn is None:
        raise KeyError(f"feature '{name}' has no pre-score normaliser")
    return fn(value)


def summarise_history(req: ScoringRequest) -> dict:
    """Compact, model-friendly summary of the history (numbers precomputed)."""
    hist = req.history
    amounts = [t.amount for t in hist]
    hours = sorted(t.timestamp.hour for t in hist)
    channels: dict[str, int] = {}
    for t in hist:
        channels[t.channel] = channels.get(t.channel, 0) + 1
    return {
        "n": len(hist),
        "median_amount": round(statistics.median(amounts), 2) if amounts else None,
        "max_amount": max(amounts, default=None),
        "countries": sorted({x for t in hist if (x := tx_country(t))}),
        "usual_hours": f"{hours[0]:02d}-{hours[-1]:02d}" if hours else None,
        "channels": channels,
        "known_beneficiaries": len({t.beneficiary.iban for t in hist if t.beneficiary}),
        "known_devices": len({t.device_id for t in hist if t.device_id}),
    }
