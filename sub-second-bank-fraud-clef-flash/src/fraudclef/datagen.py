"""European retail & SME payment datasets: 27 named reference scenarios (24 benchmarked + 3 DORA/shadow
resilience checks) and a multi-channel Eurozone portfolio generator."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

CET = timezone(timedelta(hours=2))
EET = timezone(timedelta(hours=3))
NOW = datetime(2026, 11, 10, 15, 0, tzinfo=CET)

MILAN = {"lat": 45.4642, "lon": 9.1900, "country": "IT"}
ROME = {"lat": 41.9028, "lon": 12.4964, "country": "IT"}
FRANKFURT = {"lat": 50.1109, "lon": 8.6821, "country": "DE"}
MUNICH = {"lat": 48.1351, "lon": 11.5820, "country": "DE"}
PARIS = {"lat": 48.8566, "lon": 2.3522, "country": "FR"}
LYON = {"lat": 45.7640, "lon": 4.8357, "country": "FR"}
MADRID = {"lat": 40.4168, "lon": -3.7038, "country": "ES"}
BARCELONA = {"lat": 41.3874, "lon": 2.1686, "country": "ES"}
AMSTERDAM = {"lat": 52.3676, "lon": 4.9041, "country": "NL"}
BUCHAREST = {"lat": 44.4268, "lon": 26.1025, "country": "RO"}
SOFIA = {"lat": 42.6977, "lon": 23.3219, "country": "BG"}

HOME_DEVICE = "dev-home-iphone16"
LANDLORD_IBAN = "IT60X0542811101000000123456"
FRANKFURT_LANDLORD_IBAN = "DE44500105175407324931"
MUNICH_SUPPLIER_IBAN = "DE89700202700015843120"

ENEL = {"creditor_id": "IT98ZZZ0000000883641", "mandate_id": "MND-ENEL-2023-0042", "signed_at": "2023-03-01T10:00:00+01:00"}
MAINOVA = {"creditor_id": "DE98ZZZ0999990012345", "mandate_id": "MND-MAINOVA-2022-1108", "signed_at": "2022-11-08T09:00:00+01:00"}
EDF = {"creditor_id": "FR14ZZZ409812", "mandate_id": "MND-EDF-2023-7741", "signed_at": "2023-05-14T11:00:00+02:00"}
IBERDROLA = {"creditor_id": "ES29000A48010615", "mandate_id": "MND-IBER-2023-3390", "signed_at": "2023-02-19T10:30:00+01:00"}


def _ts(dt: datetime) -> str:
    return dt.isoformat()


def _card(tid, dt, amount, name, mcc, loc=MILAN, channel="card_present", **kw):
    tx = {"transaction_id": tid, "timestamp": _ts(dt), "amount": amount, "channel": channel,
          "merchant": {"name": name, "mcc": mcc, "country": loc["country"]}}
    if channel in ("card_present", "atm"):
        tx["location"] = dict(loc)
    else:
        tx["device_id"] = kw.pop("device_id", HOME_DEVICE)
        tx["ip_country"] = kw.pop("ip_country", loc["country"])
        tx["authentication"] = kw.pop("authentication", "sca")
    tx.update(kw)
    return tx


def _transfer(tid, dt, amount, iban, name, channel="sepa_credit_transfer", vop="match", device=HOME_DEVICE, ip="IT", auth="sca"):
    return {"transaction_id": tid, "timestamp": _ts(dt), "amount": amount, "channel": channel,
            "beneficiary": {"iban": iban, "name": name, "vop_result": vop},
            "device_id": device, "ip_country": ip, "authentication": auth}


def _sdd(tid, dt, amount, mandate, recurring=True):
    return {"transaction_id": tid, "timestamp": _ts(dt), "amount": amount, "channel": "sepa_direct_debit",
            "mandate": dict(mandate), "recurring": recurring}


def base_history(now: datetime = NOW) -> list[dict]:
    """Ten habitual transactions of a Milan-based retail customer."""
    d = lambda days, hour: (now - timedelta(days=days)).replace(hour=hour, minute=12)
    return [
        _card("h01", d(20, 18), 62.40, "ESSELUNGA VIALE PIAVE MILANO", "5411"),
        _sdd("h02", d(18, 9), 74.00, ENEL),
        _card("h03", d(15, 20), 38.50, "TRATTORIA MILANESE BRERA", "5812"),
        _card("h04", d(12, 8), 55.00, "ENI STATION VIALE CERTOSA", "5541"),
        _card("h05", d(10, 10), 13.99, "NETFLIX EUROPE BV", "4899", loc={"country": "NL"}, channel="card_not_present",
              ip_country="IT", recurring=True, authentication="exemption"),
        _card("h06", d(8, 19), 48.20, "ESSELUNGA VIALE PIAVE MILANO", "5411"),
        _card("h07", d(6, 11), 22.90, "FARMACIA BRERA MILANO", "5912"),
        _transfer("h08", d(5, 9), 650.00, LANDLORD_IBAN, "Giulia Rossi"),
        _card("h09", d(3, 18), 71.30, "ESSELUNGA VIALE PIAVE MILANO", "5411"),
        _card("h10", d(1, 21), 44.00, "OSTERIA DEL CORSO MILANO", "5812"),
    ]


def frankfurt_history(now: datetime = NOW, device: str = "dev-de-iphone15") -> list[dict]:
    """Ten habitual transactions of a Frankfurt am Main retail customer."""
    d = lambda days, hour: (now - timedelta(days=days)).replace(hour=hour, minute=18)
    return [
        _card("fh01", d(21, 18), 54.80, "REWE ZEIL FRANKFURT", "5411", loc=FRANKFURT),
        _sdd("fh02", d(19, 8), 82.00, MAINOVA),
        _card("fh03", d(16, 12), 19.40, "DM DROGERIE HAUPTWACHE", "5912", loc=FRANKFURT),
        _card("fh04", d(13, 8), 64.20, "ARAL TANKSTELLE HANAUER LANDSTR", "5541", loc=FRANKFURT),
        _card("fh05", d(11, 19), 49.00, "DB FERNVERKEHR AG", "4112", loc=FRANKFURT, channel="card_not_present", device_id=device, ip_country="DE"),
        _card("fh06", d(9, 18), 61.10, "REWE ZEIL FRANKFURT", "5411", loc=FRANKFURT),
        _transfer("fh07", d(6, 9), 920.00, FRANKFURT_LANDLORD_IBAN, "Sabine Hoffmann", ip="DE", device=device),
        _card("fh08", d(4, 13), 28.50, "APOTHEKE AM GOETHEPLATZ", "5912", loc=FRANKFURT),
        _card("fh09", d(2, 20), 46.90, "APFELWEIN WAGNER SACHSENHAUSEN", "5812", loc=FRANKFURT),
        _card("fh10", d(1, 17), 37.60, "ALNATURA SUPER NATUR MARKT", "5411", loc=FRANKFURT),
    ]


def paris_history(now: datetime = NOW, device: str = "dev-fr-iphone15") -> list[dict]:
    """Ten habitual transactions of a Paris retail customer."""
    d = lambda days, hour: (now - timedelta(days=days)).replace(hour=hour, minute=24)
    return [
        _card("ph01", d(20, 19), 48.60, "MONOPRIX OPERA PARIS", "5411", loc=PARIS),
        _sdd("ph02", d(17, 9), 68.50, EDF),
        _card("ph03", d(14, 13), 24.00, "PHARMACIE MONGE PARIS", "5912", loc=PARIS),
        _card("ph04", d(11, 9), 52.00, "SNCF CONNECT", "4112", loc=PARIS, channel="card_not_present", device_id=device, ip_country="FR"),
        _card("ph05", d(8, 20), 56.00, "BISTROT RICHELIEU PARIS", "5812", loc=PARIS),
        _card("ph06", d(6, 18), 41.30, "CARREFOUR CITY SAINT GERMAIN", "5411", loc=PARIS),
        _transfer("ph07", d(5, 10), 880.00, "FR7630004000031234567890143", "Claire Dubois", ip="FR", device=device),
        _card("ph08", d(3, 19), 33.90, "FNAC SAINT LAZARE", "5732", loc=PARIS),
        _card("ph09", d(2, 12), 16.40, "BOULANGERIE POILANE PARIS", "5462", loc=PARIS),
        _card("ph10", d(1, 19), 52.10, "MONOPRIX OPERA PARIS", "5411", loc=PARIS),
    ]


MAX_HISTORY = 30


def older_history(n: int = MAX_HISTORY - 10, now: datetime = NOW, loc=MILAN, habits=None, landlord_iban=LANDLORD_IBAN, landlord_name="Giulia Rossi", sdd_mandate=ENEL, ip="IT", device=HOME_DEVICE) -> list[dict]:
    """Habitual payments 21 to ~90 days before base_history."""
    habits = habits or [
        ("ESSELUNGA VIALE PIAVE MILANO", "5411", 40, 75),
        ("TRATTORIA MILANESE BRERA", "5812", 30, 60),
        ("ENI STATION VIALE CERTOSA", "5541", 45, 70),
        ("FARMACIA BRERA MILANO", "5912", 10, 35),
        ("OSTERIA DEL CORSO MILANO", "5812", 35, 55),
    ]
    out = []
    for k in range(n):
        dt = (now - timedelta(days=21 + k * 3.4)).replace(hour=9 + (k * 5) % 12, minute=7)
        if k % 10 == 3:
            out.append(_transfer(f"o{k:02d}", dt, 650.00, landlord_iban, landlord_name, ip=ip, device=device))
        elif k % 10 == 7:
            out.append(_sdd(f"o{k:02d}", dt, 71.00 + k % 3, sdd_mandate))
        else:
            name, mcc, lo, hi = habits[k % len(habits)]
            out.append(_card(f"o{k:02d}", dt, round(lo + (hi - lo) * ((k * 37) % 100) / 100, 2), name, mcc, loc=loc))
    return sorted(out, key=lambda t: t["timestamp"])


def _customer(**kw) -> dict:
    c = {"id": "cust-0001", "segment": "retail", "vulnerable": False, "account_age_days": 1450,
         "home_country": "IT", "recent_profile_changes": []}
    c.update(kw)
    return c


SCENARIO_TYPES = {
    "01_usual_groceries": "habitual",
    "02_amount_spike_ecommerce": "stolen_card_online",
    "03_impossible_travel": "cloned_card",
    "04_card_testing": "card_testing",
    "05_account_takeover_instant": "account_takeover",
    "06_fake_bank_operator": "impersonation_scam",
    "07_trip_spain": "unusual_legit",
    "08_sanctioned_country": "sanctions",
    "09_vulnerable_unusual_transfer": "impersonation_scam",
    "10_atm_cashout_abroad": "atm_cashout",
    "11_sdd_new_creditor": "rogue_direct_debit",
    "12_recurring_subscription": "habitual",
    "13_backend_down_card_present": "habitual",
    "14_backend_down_instant": "habitual",
    "16_frankfurt_spoofed_hotline_app": "impersonation_scam",
    "17_interbank_mule_intelligence_hit": "impersonation_scam",
    "18_munich_sme_invoice_iban_swap": "impersonation_scam",
    "19_paris_habitual_bakery_contactless": "habitual",
    "20_paris_crypto_exchange_ramp": "risky_merchant",
    "21_frankfurt_munich_ice_rail_trip": "unusual_legit",
    "22_madrid_vulnerable_foreign_instant": "impersonation_scam",
    "23_milan_monthly_rent_transfer": "habitual",
    "24_amsterdam_klm_family_booking": "unusual_legit",
    "25_frankfurt_utility_sdd_recurring": "habitual",
    "26_rome_night_foreign_ip_luxury_cnp": "stolen_card_online",
    "27_lyon_daily_segment_limit_breach": "stolen_card_online",
}


def _scenario(name, description, expected, label, candidate, history=None, customer=None, older=None, **extra) -> dict:
    hist = history if history is not None else base_history()
    old = older if older is not None else older_history()
    return {
        "name": name, "description": description, "expected": expected, "label": label,
        "type": SCENARIO_TYPES.get(name, label), **extra,
        "request": {"customer": customer or _customer(), "history": (old + hist[-10:])[-MAX_HISTORY:],
                    "candidate": candidate},
    }


def scenarios() -> list[dict]:
    m = lambda minutes: NOW - timedelta(minutes=minutes)
    de_older = older_history(
        loc=FRANKFURT,
        habits=[("REWE ZEIL FRANKFURT", "5411", 35, 70), ("DM DROGERIE HAUPTWACHE", "5912", 12, 30),
                ("ARAL TANKSTELLE HANAUER LANDSTR", "5541", 50, 80), ("APFELWEIN WAGNER SACHSENHAUSEN", "5812", 30, 60)],
        landlord_iban=FRANKFURT_LANDLORD_IBAN, landlord_name="Sabine Hoffmann", sdd_mandate=MAINOVA, ip="DE", device="dev-de-iphone15",
    )
    fr_older = older_history(
        loc=PARIS,
        habits=[("MONOPRIX OPERA PARIS", "5411", 30, 65), ("PHARMACIE MONGE PARIS", "5912", 10, 30),
                ("BISTROT RICHELIEU PARIS", "5812", 35, 65), ("BOULANGERIE POILANE PARIS", "5462", 8, 22)],
        landlord_iban="FR7630004000031234567890143", landlord_name="Claire Dubois", sdd_mandate=EDF, ip="FR", device="dev-fr-iphone15",
    )

    out = []

    # 01-12: Core multi-rail European scenarios
    out.append(_scenario("01_usual_groceries", "Habitual grocery card tap at Esselunga Viale Piave, Milan",
                         ["approve"], "legit", _card("c01", NOW, 38.90, "ESSELUNGA VIALE PIAVE MILANO", "5411")))

    out.append(_scenario("02_amount_spike_ecommerce", "EUR 1,249 electronics e-commerce spike (x20 median) at MediaWorld IT",
                         ["step_up", "hold"], "fraud",
                         _card("c02", NOW.replace(hour=20, minute=30), 1249.00, "MEDIAWORLD ONLINE IT", "5732",
                               loc={"country": "IT"}, channel="card_not_present")))

    hist = base_history()[1:] + [_card("h11", m(40), 3.50, "CAFFE BRERA MILANO", "5814")]
    out.append(_scenario("03_impossible_travel", "POS tap in Milan followed 40 minutes later by EUR 890 POS in Bucharest",
                         ["block"], "fraud",
                         _card("c03", NOW.astimezone(EET), 890.00, "ELECTRO MALL BUCURESTI", "5732", loc=BUCHAREST), history=hist))

    burst = [_card(f"h2{i}", m(8 - i), round(1.0 + i * 0.25, 2), f"DIGITAL-KEY-SHOP-{i}", "5999",
                   loc={"country": "US"}, channel="card_not_present", device_id="dev-unknown-7", ip_country="US",
                   authentication="none") for i in range(5)]
    out.append(_scenario("04_card_testing", "Five unauthenticated USD/EUR micro-charges in 8 minutes, then a sixth",
                         ["block"], "fraud",
                         _card("c04", NOW, 1.50, "DIGITAL-KEY-SHOP-6", "5999", loc={"country": "US"}, channel="card_not_present",
                               device_id="dev-unknown-7", ip_country="US", authentication="none"),
                         history=base_history()[5:] + burst))

    out.append(_scenario("05_account_takeover_instant", "Phone changed 20h ago + new Android device + EUR 2,400 SEPA Instant to Frankfurt IBAN",
                         ["hold", "block"], "fraud",
                         _transfer("c05", NOW, 2400.00, "DE89370400440532013000", "Lukas Schneider", channel="sepa_instant",
                                   vop="close_match", device="dev-android-new", ip="IT"),
                         customer=_customer(recent_profile_changes=[{"field": "phone_number", "at": _ts(NOW - timedelta(hours=20))}])))

    out.append(_scenario("06_fake_bank_operator", "Spoofed bank-security call (APP scam): EUR 4,900 SEPA Instant, VoP no match",
                         ["hold"], "fraud",
                         _transfer("c06", NOW.replace(hour=11), 4900.00, "IT40S0542811101000000654321", "Conto Sicurezza Interbancario",
                                   channel="sepa_instant", vop="no_match")))

    trip = base_history()[3:] + [
        _card("h31", NOW - timedelta(days=1, hours=2), 45.00, "TAPAS 24 BARCELONA", "5812", loc=BARCELONA),
        _card("h32", NOW - timedelta(hours=20), 18.50, "FARMACIA RAMBLA CATALUNYA", "5912", loc=BARCELONA),
        _card("h33", NOW - timedelta(hours=4), 32.00, "CAFE ZURICH PLACA CATALUNYA", "5814", loc=BARCELONA),
    ]
    out.append(_scenario("07_trip_spain", "Milan customer on a consistent weekend trip in Barcelona (El Corte Ingles EUR 180)",
                         ["approve", "step_up"], "legit",
                         _card("c07", NOW, 180.00, "EL CORTE INGLES DIAGONAL", "5311", loc=BARCELONA), history=trip))

    out.append(_scenario("08_sanctioned_country", "E-commerce card payment to a merchant in an EU-sanctioned jurisdiction",
                         ["block"], "fraud",
                         _card("c08", NOW, 120.00, "OOO TORGSERVIS MOSKVA", "5999", loc={"country": "RU"}, channel="card_not_present")))

    out.append(_scenario("09_vulnerable_unusual_transfer", "Vulnerable retiree: unusual EUR 900 transfer to unverified investment company",
                         ["step_up", "hold"], "fraud",
                         _transfer("c09", NOW.replace(hour=10), 900.00, "IT21Q0306909606100000012345", "Rendita Garantita Europa Srl"),
                         customer=_customer(vulnerable=True, account_age_days=9000)))

    hist = base_history()[3:] + [
        _card("h41", m(50), 27.80, "ESSELUNGA VIALE PIAVE MILANO", "5411"),
        _card("h42", m(20), 500.00, "ATM UNICREDIT BULBANK SOFIA", "6011", loc=SOFIA, channel="atm"),
        _card("h43", m(10), 500.00, "ATM UNICREDIT BULBANK SOFIA", "6011", loc=SOFIA, channel="atm"),
    ]
    out.append(_scenario("10_atm_cashout_abroad", "Third EUR 500 ATM withdrawal in Sofia 50 minutes after a Milan supermarket tap",
                         ["block"], "fraud",
                         _card("c10", NOW.astimezone(EET), 500.00, "ATM UNICREDIT BULBANK SOFIA", "6011", loc=SOFIA, channel="atm"),
                         history=hist))

    new_mandate = {"creditor_id": "IT11ZZZ0000099999999", "mandate_id": "MND-NEW-0001", "signed_at": _ts(NOW - timedelta(hours=6))}
    out.append(_scenario("11_sdd_new_creditor", "First EUR 750 SEPA Direct Debit on an unknown creditor mandate signed 6h ago",
                         ["hold"], "fraud", _sdd("c11", NOW, 750.00, new_mandate, recurring=False)))

    out.append(_scenario("12_recurring_subscription", "Established monthly Netflix Europe subscription (same merchant and amount)",
                         ["approve"], "legit",
                         _card("c12", NOW, 13.99, "NETFLIX EUROPE BV", "4899", loc={"country": "NL"}, channel="card_not_present",
                               ip_country="IT", recurring=True, authentication="exemption")))

    # 16-27: Additional localized DACH / FR / ES / NL / IT real-world banking scenarios
    out.append(_scenario("16_frankfurt_spoofed_hotline_app",
                         "Frankfurt caller-ID spoofing (069 bank hotline APP scam): EUR 3,850 SEPA Instant, VoP no match",
                         ["hold"], "fraud",
                         _transfer("c16", NOW.replace(hour=14, minute=10), 3850.00, "DE62500105179928174610",
                                   "Treuhand Sicherungskonto Frankfurt", channel="sepa_instant", vop="no_match",
                                   device="dev-de-iphone15", ip="DE"),
                         history=frankfurt_history(), older=de_older,
                         customer=_customer(id="cust-de-0102", home_country="DE", account_age_days=2190)))

    out.append(_scenario("17_interbank_mule_intelligence_hit",
                         "SEPA Instant EUR 1,650 to an IBAN flagged on German interbank fraud-intelligence feed",
                         ["block"], "fraud",
                         _transfer("c17", NOW.replace(hour=16, minute=5), 1650.00, "DE75512108001245126199",
                                   "Kevin Hartmann", channel="sepa_instant", vop="match",
                                   device="dev-de-iphone15", ip="DE"),
                         history=frankfurt_history(), older=de_older,
                         customer=_customer(id="cust-de-0103", home_country="DE", account_age_days=1800)))

    sme_hist = frankfurt_history()[2:] + [
        _transfer("sh01", NOW - timedelta(days=15), 6200.00, MUNICH_SUPPLIER_IBAN, "Bavaria Industrietechnik GmbH", ip="DE", device="dev-de-macbook"),
        _transfer("sh02", NOW - timedelta(days=4), 4800.00, MUNICH_SUPPLIER_IBAN, "Bavaria Industrietechnik GmbH", ip="DE", device="dev-de-macbook"),
    ]
    out.append(_scenario("18_munich_sme_invoice_iban_swap",
                         "Mittelstand supplier BEC scam: EUR 8,400 SEPA Instant to redirected Lithuanian IBAN, VoP no match",
                         ["hold"], "fraud",
                         _transfer("c18", NOW.replace(hour=11, minute=45), 8400.00, "LT843500010014928371",
                                   "Bavaria Industrietechnik GmbH", channel="sepa_instant", vop="no_match",
                                   device="dev-de-macbook", ip="DE"),
                         history=sme_hist, older=de_older,
                         customer=_customer(id="cust-de-sme-09", segment="business", home_country="DE", account_age_days=3100)))

    out.append(_scenario("19_paris_habitual_bakery_contactless",
                         "Habitual contactless EUR 14.80 card tap at Boulangerie Poilane, Paris",
                         ["approve"], "legit",
                         _card("c19", NOW.replace(hour=9, minute=15), 14.80, "BOULANGERIE POILANE PARIS", "5462", loc=PARIS),
                         history=paris_history(), older=fr_older,
                         customer=_customer(id="cust-fr-0201", home_country="FR", account_age_days=1640)))

    out.append(_scenario("20_paris_crypto_exchange_ramp",
                         "Paris retail account: first-time EUR 980 card-not-present deposit to Maltese crypto exchange",
                         ["step_up", "hold"], "fraud",
                         _card("c20", NOW.replace(hour=22, minute=50), 980.00, "MALTA DIGITAL EXCHANGE LTD", "6051",
                               loc={"country": "MT"}, channel="card_not_present", device_id="dev-fr-iphone15", ip_country="FR"),
                         history=paris_history(), older=fr_older,
                         customer=_customer(id="cust-fr-0202", home_country="FR", account_age_days=920)))

    ice_hist = frankfurt_history()[1:] + [
        _card("ih01", m(240), 79.90, "DB BAHN TICKET FRANKFURT HBF", "4112", loc=FRANKFURT),
    ]
    out.append(_scenario("21_frankfurt_munich_ice_rail_trip",
                         "Frankfurt customer pays EUR 142 at a Munich restaurant 4 hours after buying a DB ICE rail ticket",
                         ["approve", "step_up"], "legit",
                         _card("c21", NOW, 142.00, "AUGUSTINER BRAUSTUBEN MUNCHEN", "5812", loc=MUNICH),
                         history=ice_hist, older=de_older,
                         customer=_customer(id="cust-de-0109", home_country="DE", account_age_days=2400)))

    es_hist = [
        _card("eh01", NOW - timedelta(days=18), 42.30, "MERCADONA CASTELLANA MADRID", "5411", loc=MADRID),
        _sdd("eh02", NOW - timedelta(days=15), 63.10, IBERDROLA),
        _card("eh03", NOW - timedelta(days=11), 19.80, "FARMACIA MAYOR MADRID", "5912", loc=MADRID),
        _card("eh04", NOW - timedelta(days=8), 36.50, "CASA DANI MERCADO PAZ", "5812", loc=MADRID),
        _card("eh05", NOW - timedelta(days=5), 48.90, "MERCADONA CASTELLANA MADRID", "5411", loc=MADRID),
        _card("eh06", NOW - timedelta(days=2), 21.40, "RENFE CERCANIAS MADRID", "4112", loc=MADRID),
    ]
    out.append(_scenario("22_madrid_vulnerable_foreign_instant",
                         "Vulnerable Madrid pensioner: first SEPA Instant EUR 1,150 to unfamiliar Cyprus IBAN",
                         ["step_up", "hold", "block"], "fraud",
                         _transfer("c22", NOW.replace(hour=19, minute=40), 1150.00, "CY17002001280000001200527600",
                                   "Elena Petrou", channel="sepa_instant", vop="close_match", device="dev-es-ipad", ip="ES"),
                         history=es_hist,
                         older=older_history(loc=MADRID, habits=[("MERCADONA CASTELLANA MADRID", "5411", 30, 55), ("FARMACIA MAYOR MADRID", "5912", 10, 28)],
                                             landlord_iban="ES9121000418450200051332", landlord_name="Carlos Navarro", sdd_mandate=IBERDROLA, ip="ES", device="dev-es-ipad"),
                         customer=_customer(id="cust-es-0304", home_country="ES", vulnerable=True, account_age_days=7800)))

    rent_hist = base_history()
    rent_hist[7] = {**rent_hist[7], "recurring": True}
    out.append(_scenario("23_milan_monthly_rent_transfer",
                         "Established monthly EUR 650 standing-order rent transfer to Giulia Rossi (VoP match)",
                         ["approve"], "legit",
                         {**_transfer("c23", NOW.replace(hour=9, minute=30), 650.00, LANDLORD_IBAN, "Giulia Rossi",
                                      channel="sepa_credit_transfer", vop="match", device=HOME_DEVICE, ip="IT"),
                          "recurring": True},
                         history=rent_hist))

    nl_hist = [
        _card("nh01", NOW - timedelta(days=19), 51.20, "ALBERT HEIJN MUSEUMPLEIN", "5411", loc=AMSTERDAM),
        _card("nh02", NOW - timedelta(days=14), 28.40, "NS REIZIGERS AMSTERDAM", "4112", loc=AMSTERDAM),
        _card("nh03", NOW - timedelta(days=9), 64.10, "HEMA KALVERSTRAAT", "5311", loc=AMSTERDAM),
        _card("nh04", NOW - timedelta(days=6), 44.80, "ALBERT HEIJN MUSEUMPLEIN", "5411", loc=AMSTERDAM),
        _card("nh05", NOW - timedelta(days=3), 39.00, "BOL.COM UTRECHT", "5942", loc=AMSTERDAM, channel="card_not_present", device_id="dev-nl-iphone", ip_country="NL"),
        _card("nh06", NOW - timedelta(days=1), 47.50, "CAFE LOETJE OOST", "5812", loc=AMSTERDAM),
    ]
    out.append(_scenario("24_amsterdam_klm_family_booking",
                         "Amsterdam customer books EUR 460 KLM flight on known iPhone and home NL IP with SCA",
                         ["approve", "step_up"], "legit",
                         _card("c24", NOW.replace(hour=13, minute=10), 460.00, "KLM ROYAL DUTCH AIRLINES", "4511",
                               loc=AMSTERDAM, channel="card_not_present", device_id="dev-nl-iphone", ip_country="NL", authentication="sca"),
                         history=nl_hist,
                         older=older_history(loc=AMSTERDAM, habits=[("ALBERT HEIJN MUSEUMPLEIN", "5411", 35, 65), ("CAFE LOETJE OOST", "5812", 30, 55)],
                                             landlord_iban="NL91ABNA0417164300", landlord_name="Jan de Vries", sdd_mandate=MAINOVA, ip="NL", device="dev-nl-iphone"),
                         customer=_customer(id="cust-nl-0401", home_country="NL", account_age_days=2050)))

    out.append(_scenario("25_frankfurt_utility_sdd_recurring",
                         "Established monthly EUR 82.00 SEPA Direct Debit for Mainova Frankfurt electricity",
                         ["approve"], "legit",
                         _sdd("c25", NOW.replace(hour=8, minute=30), 82.00, MAINOVA, recurring=True),
                         history=frankfurt_history(), older=de_older,
                         customer=_customer(id="cust-de-0115", home_country="DE", account_age_days=2600)))

    out.append(_scenario("26_rome_night_foreign_ip_luxury_cnp",
                         "Stolen card credentials at 03:20 CET: EUR 1,580 online jewelry charge from UAE IP and unknown device",
                         ["step_up", "hold", "block"], "fraud",
                         _card("c26", NOW.replace(hour=3, minute=20), 1580.00, "DUBAI GOLD SOUK ONLINE", "5944",
                               loc={"country": "AE"}, channel="card_not_present", device_id="dev-unknown-99", ip_country="AE")))

    big_day = base_history()[1:] + [
        _card("bh01", m(180), 3200.00, "POLTRONESOFA MILANO", "5712", loc=MILAN),
    ]
    out.append(_scenario("27_lyon_daily_segment_limit_breach",
                         "Retail daily cumulative spend exceeds EUR 5,000 limit across two high-ticket purchases",
                         ["step_up", "hold"], "fraud",
                         _card("c27", NOW, 2400.00, "ROCHE BOBOIS LYON", "5712", loc=LYON),
                         history=big_day))

    # 13-15: DORA resilience & shadow-mode single-run checks (excluded from batch throughput runs)
    out.append(_scenario("13_backend_down_card_present", "DORA stand-in check: model unreachable during EUR 25 tap at Panificio Davide Longoni",
                         ["approve"], "legit", _card("c13", NOW, 25.00, "PANIFICIO DAVIDE LONGONI MILANO", "5462"),
                         routing="always", simulate_backend_failure=True))

    out.append(_scenario("14_backend_down_instant", "DORA instant fail-safe: model unreachable during EUR 2,000 SEPA Instant to known landlord",
                         ["step_up"], "legit",
                         _transfer("c14", NOW.replace(hour=10), 2000.00, LANDLORD_IBAN, "Giulia Rossi", channel="sepa_instant"),
                         simulate_backend_failure=True))

    s15 = json.loads(json.dumps(out[5]))
    s15.update(name="15_shadow_mode", description="Shadow-mode rollout check: fake bank-operator scam logged without acting",
               policy_overrides={"governance": {"mode": "shadow"}})
    out.append(s15)
    return out


# ── Localized Eurozone multi-channel portfolio dataset (default n = 2,000) ────

HUB_PROFILES = [
    {
        "city": "Milan", "loc": MILAN, "country": "IT",
        "pos": [("ESSELUNGA MILANO", "5411", 22, 95), ("TRATTORIA BRERA", "5812", 18, 68),
                ("ENI STATION MILANO", "5541", 35, 82), ("FARMACIA CENTRALE MILANO", "5912", 8, 38),
                ("LA FELTRINELLI DUOMO", "5942", 12, 46)],
        "cnp_habit": ("TRENITALIA ONLINE", "4112", 16, 75),
        "cnp_travel": ("ITA AIRWAYS ROMA", "4511", 180, 620),
        "cnp_shop": ("MEDIAWORLD ITALIA", "5732", 140, 480),
        "landlord": ("IT60X0542811101000000123456", "Giulia Rossi", 720.0),
        "sdd": ENEL,
    },
    {
        "city": "Rome", "loc": ROME, "country": "IT",
        "pos": [("CONAD PRATI ROMA", "5411", 20, 88), ("OSTERIA TRASTEVERE", "5812", 22, 72),
                ("Q8 STAZIONE FLAMINIA", "5541", 30, 78), ("FARMACIA SAN GIOVANNI", "5912", 7, 34),
                ("LIBRERIA MONDADORI ROMA", "5942", 11, 42)],
        "cnp_habit": ("ITALO TRENO SPA", "4112", 19, 84),
        "cnp_travel": ("BOOKING.COM AMSTERDAM", "7011", 210, 680),
        "cnp_shop": ("UNIEURO ONLINE", "5732", 130, 440),
        "landlord": ("IT88K0306905000100000045812", "Marco Conti", 690.0),
        "sdd": {"creditor_id": "IT44ZZZ0000001192837", "mandate_id": "MND-ACEA-2023-1902", "signed_at": "2023-04-10T09:00:00+02:00"},
    },
    {
        "city": "Frankfurt", "loc": FRANKFURT, "country": "DE",
        "pos": [("REWE ZEIL FRANKFURT", "5411", 24, 96), ("APFELWEIN WAGNER", "5812", 20, 74),
                ("ARAL HANAUER LANDSTR", "5541", 40, 92), ("DM DROGERIE HAUPTWACHE", "5912", 9, 42),
                ("HUGENDUBEL STEINWEG", "5942", 14, 52)],
        "cnp_habit": ("DB FERNVERKEHR AG", "4112", 24, 98),
        "cnp_travel": ("LUFTHANSA GERMAN AIRLINES", "4511", 240, 790),
        "cnp_shop": ("SATURN ONLINE DE", "5732", 150, 520),
        "landlord": (FRANKFURT_LANDLORD_IBAN, "Sabine Hoffmann", 940.0),
        "sdd": MAINOVA,
    },
    {
        "city": "Munich", "loc": MUNICH, "country": "DE",
        "pos": [("EDEKA MARIENPLATZ MUNCHEN", "5411", 25, 102), ("AUGUSTINER BRAUSTUBEN", "5812", 24, 80),
                ("SHELL MITTLERER RING", "5541", 42, 95), ("RATS APOTHEKE MUNCHEN", "5912", 10, 44),
                ("THALIA BUCHHANDLUNG", "5942", 15, 48)],
        "cnp_habit": ("ZALANDO SE BERLIN", "5651", 29, 110),
        "cnp_travel": ("DEUTSCHE LUFTHANSA MUC", "4511", 260, 840),
        "cnp_shop": ("CYBERPORT GMBH", "5732", 160, 560),
        "landlord": ("DE19700500000024918273", "Thomas Bauer", 1050.0),
        "sdd": {"creditor_id": "DE22ZZZ000005582910", "mandate_id": "MND-SWM-2022-8812", "signed_at": "2022-09-01T08:00:00+02:00"},
    },
    {
        "city": "Paris", "loc": PARIS, "country": "FR",
        "pos": [("MONOPRIX OPERA PARIS", "5411", 22, 90), ("BISTROT RICHELIEU", "5812", 20, 76),
                ("TOTALENERGIES PERIPHERIQUE", "5541", 38, 86), ("PHARMACIE MONGE PARIS", "5912", 8, 36),
                ("FNAC SAINT LAZARE", "5942", 14, 54)],
        "cnp_habit": ("SNCF CONNECT PARIS", "4112", 22, 92),
        "cnp_travel": ("AIR FRANCE PARIS", "4511", 220, 740),
        "cnp_shop": ("DARTY FRANCE ONLINE", "5732", 140, 490),
        "landlord": ("FR7630004000031234567890143", "Claire Dubois", 890.0),
        "sdd": EDF,
    },
    {
        "city": "Madrid", "loc": MADRID, "country": "ES",
        "pos": [("MERCADONA CASTELLANA", "5411", 19, 84), ("CASA DANI MADRID", "5812", 16, 62),
                ("REPSOL PASEO DEL PRADO", "5541", 32, 78), ("FARMACIA MAYOR MADRID", "5912", 6, 32),
                ("CASA DEL LIBRO GRAN VIA", "5942", 12, 40)],
        "cnp_habit": ("RENFE VIAJEROS", "4112", 18, 76),
        "cnp_travel": ("IBERIA LINEAS AEREAS", "4511", 195, 660),
        "cnp_shop": ("EL CORTE INGLES ONLINE", "5311", 120, 430),
        "landlord": ("ES9121000418450200051332", "Carlos Navarro", 680.0),
        "sdd": IBERDROLA,
    },
]

MULE_LIST = ["LT601010012345678901", "IT02L1234512345123456789012", "DE75512108001245126199", "FR7630006000011234567890189"]

RANDOM_TYPES = {
    "spike_cnp": "stolen_card_online",
    "foreign_cnp": "stolen_card_online",
    "card_testing_cnp": "card_testing",
    "ato_transfer": "account_takeover",
    "app_scam_instant": "impersonation_scam",
    "mule_instant": "impersonation_scam",
    "atm_abroad": "atm_cashout",
    "cloned_pos": "cloned_card",
    "rogue_sdd": "rogue_direct_debit",
    "high_risk_mcc": "risky_merchant",
    "habitual_pos": "habitual",
    "habitual_cnp": "habitual",
    "habitual_transfer": "habitual",
    "habitual_sdd": "habitual",
}


def random_dataset(n: int = 2000, fraud_rate: float = 0.12, grey_rate: float = 0.14, seed: int = 7) -> list[dict]:
    """Generate a realistic multi-channel Eurozone banking portfolio (default 2,000 customers)."""
    rnd = random.Random(seed)
    items = []
    for i in range(n):
        hub = rnd.choice(HUB_PROFILES)
        loc, home = hub["loc"], hub["country"]
        device = f"dev-{home.lower()}-{i:04d}"
        landlord_iban, landlord_name, rent_amt = hub["landlord"]
        hist = []

        for k in range(10):
            dt = (NOW - timedelta(days=28 - k * 2.7)).replace(hour=rnd.randint(8, 21), minute=rnd.randint(0, 59))
            if k == 3:
                hist.append(_transfer(f"r{i}h{k}", dt, rent_amt, landlord_iban, landlord_name, ip=home, device=device))
            elif k == 4:
                cname, cmcc, clo, chi = hub["cnp_habit"]
                hist.append(_card(f"r{i}h{k}", dt, round(rnd.uniform(clo, chi), 2), cname, cmcc,
                                  loc={"country": home}, channel="card_not_present", device_id=device, ip_country=home))
            elif k == 7:
                hist.append(_sdd(f"r{i}h{k}", dt, round(rnd.uniform(58, 92), 2), hub["sdd"]))
            else:
                name, mcc, lo, hi = rnd.choice(hub["pos"])
                hist.append(_card(f"r{i}h{k}", dt, round(rnd.uniform(lo, hi), 2), name, mcc, loc=loc))

        old = random.Random(seed * 100_003 + i)
        for k in range(MAX_HISTORY - 10):
            dt = (NOW - timedelta(days=30 + k * 3)).replace(hour=old.randint(8, 21), minute=old.randint(0, 59))
            if k % 9 == 2:
                hist.append(_transfer(f"r{i}o{k:02d}", dt, rent_amt, landlord_iban, landlord_name, ip=home, device=device))
            elif k % 9 == 6:
                hist.append(_sdd(f"r{i}o{k:02d}", dt, round(old.uniform(58, 92), 2), hub["sdd"]))
            else:
                name, mcc, lo, hi = old.choice(hub["pos"])
                hist.append(_card(f"r{i}o{k:02d}", dt, round(old.uniform(lo, hi), 2), name, mcc, loc=loc))
        hist.sort(key=lambda t: t["timestamp"])

        is_business = rnd.random() < 0.08
        cust = _customer(
            id=f"cust-{home.lower()}-{i:04d}",
            segment="business" if is_business else "retail",
            home_country=home,
            vulnerable=(not is_business) and (rnd.random() < 0.06),
            account_age_days=rnd.randint(320, 4200),
        )

        r = rnd.random()
        if r < fraud_rate:
            label = "fraud"
            kind = rnd.choices(
                ["spike_cnp", "foreign_cnp", "card_testing_cnp", "ato_transfer", "app_scam_instant",
                 "mule_instant", "atm_abroad", "cloned_pos", "rogue_sdd", "high_risk_mcc"],
                weights=[16, 14, 10, 14, 14, 6, 8, 6, 6, 6],
            )[0]
            if kind == "spike_cnp":
                sname, smcc, _, _ = hub["cnp_shop"]
                cand = _card(f"r{i}c", NOW, round(rnd.uniform(950, 2900), 2), sname, smcc,
                             loc={"country": home}, channel="card_not_present", device_id=f"dev-unseen-{i}", ip_country=home)
            elif kind == "foreign_cnp":
                cand = _card(f"r{i}c", NOW.replace(hour=rnd.choice([2, 3, 4])), round(rnd.uniform(280, 1450), 2),
                             "DUBAI LUXURY WATCHES ONLINE", "5944", loc={"country": "AE"},
                             channel="card_not_present", device_id=f"dev-ae-{i}", ip_country="AE")
            elif kind == "card_testing_cnp":
                for b in range(5):
                    hist.append(_card(f"r{i}b{b}", NOW - timedelta(minutes=8 - b), round(0.95 + b * 0.2, 2),
                                      f"GIFT-CODES-{b}", "5999", loc={"country": "US"}, channel="card_not_present",
                                      device_id="dev-bot", ip_country="US", authentication="none"))
                hist.sort(key=lambda t: t["timestamp"])
                cand = _card(f"r{i}c", NOW, 1.80, "GIFT-CODES-6", "5999", loc={"country": "US"},
                             channel="card_not_present", device_id="dev-bot", ip_country="US", authentication="none")
            elif kind == "ato_transfer":
                cust["recent_profile_changes"] = [{"field": "phone_number", "at": _ts(NOW - timedelta(hours=rnd.randint(2, 36)))}]
                cand = _transfer(f"r{i}c", NOW, round(rnd.uniform(1200, 4600), 2),
                                 f"LT60101001{rnd.randint(10**9, 10**10 - 1)}", "Tomasz Kowalski",
                                 channel="sepa_instant", vop=rnd.choice(["close_match", "no_match"]),
                                 device=f"dev-ato-{i}", ip=rnd.choice(["LT", "NL", home]))
            elif kind == "app_scam_instant":
                scam_names = ["Treuhand Sicherungskonto", "Conto Sicurezza Interbancario", "Cellule Securite Bancaire", "Cuenta Custodia Segura"]
                cand = _transfer(f"r{i}c", NOW, round(rnd.uniform(1400, 4950), 2),
                                 f"DE8937040044{rnd.randint(10**9, 10**10 - 1)}", rnd.choice(scam_names),
                                 channel="sepa_instant", vop="no_match", device=device, ip=home)
            elif kind == "mule_instant":
                cand = _transfer(f"r{i}c", NOW, round(rnd.uniform(750, 2800), 2),
                                 rnd.choice(MULE_LIST), "Interbank Flagged Account",
                                 channel="sepa_instant", vop="match", device=device, ip=home)
            elif kind == "atm_abroad":
                hist.append(_card(f"r{i}p1", NOW - timedelta(minutes=45), 24.50, hub["pos"][0][0], "5411", loc=loc))
                hist.sort(key=lambda t: t["timestamp"])
                cand = _card(f"r{i}c", NOW.astimezone(EET), 500.00, "ATM UNICREDIT SOFIA", "6011", loc=SOFIA, channel="atm")
            elif kind == "cloned_pos":
                hist.append(_card(f"r{i}p1", NOW - timedelta(minutes=38), 18.20, hub["pos"][1][0], "5812", loc=loc))
                hist.sort(key=lambda t: t["timestamp"])
                cand = _card(f"r{i}c", NOW.astimezone(EET), round(rnd.uniform(420, 1250), 2),
                             "ELECTRO MALL BUCURESTI", "5732", loc=BUCHAREST, channel="card_present")
            elif kind == "rogue_sdd":
                rogue = {"creditor_id": f"{home}99ZZZ000099{i:04d}", "mandate_id": f"MND-ROGUE-{i:04d}",
                         "signed_at": _ts(NOW - timedelta(hours=rnd.randint(3, 28)))}
                cand = _sdd(f"r{i}c", NOW, round(rnd.uniform(550, 1600), 2), rogue, recurring=False)
            else:
                cand = _card(f"r{i}c", NOW, round(rnd.uniform(350, 1100), 2), "MALTA CRYPTO RAMP", "6051",
                             loc={"country": "MT"}, channel="card_not_present", device_id=device, ip_country=home)
        elif r < fraud_rate + grey_rate:
            label = "legit"
            kind = rnd.choice(["ikea_pos", "airline_cnp", "electronics_cnp", "family_instant"])
            if kind == "ikea_pos":
                cand = _card(f"r{i}c", NOW, round(rnd.uniform(140, 390), 2), f"IKEA {hub['city'].upper()}", "5712", loc=loc)
            elif kind == "airline_cnp":
                aname, amcc, alo, ahi = hub["cnp_travel"]
                cand = _card(f"r{i}c", NOW, round(rnd.uniform(alo, ahi), 2), aname, amcc,
                             loc={"country": home}, channel="card_not_present", device_id=device, ip_country=home)
            elif kind == "electronics_cnp":
                sname, smcc, slo, shi = hub["cnp_shop"]
                cand = _card(f"r{i}c", NOW, round(rnd.uniform(slo, shi), 2), sname, smcc,
                             loc={"country": home}, channel="card_not_present", device_id=device, ip_country=home)
            else:
                cand = _transfer(f"r{i}c", NOW, round(rnd.uniform(180, 620), 2), landlord_iban, landlord_name,
                                 channel="sepa_instant", vop="match", device=device, ip=home)
        else:
            label = "legit"
            kind = rnd.choices(
                ["habitual_pos", "habitual_cnp", "habitual_transfer", "habitual_sdd"],
                weights=[52, 22, 16, 10],
            )[0]
            if kind == "habitual_pos":
                name, mcc, lo, hi = rnd.choice(hub["pos"])
                cand = _card(f"r{i}c", NOW, round(rnd.uniform(lo, hi), 2), name, mcc, loc=loc)
            elif kind == "habitual_cnp":
                cname, cmcc, clo, chi = hub["cnp_habit"]
                cand = _card(f"r{i}c", NOW, round(rnd.uniform(clo, chi), 2), cname, cmcc,
                             loc={"country": home}, channel="card_not_present", device_id=device, ip_country=home)
            elif kind == "habitual_transfer":
                cand = _transfer(f"r{i}c", NOW, rent_amt, landlord_iban, landlord_name,
                                 channel="sepa_credit_transfer", vop="match", device=device, ip=home)
            else:
                cand = _sdd(f"r{i}c", NOW, round(rnd.uniform(62, 84), 2), hub["sdd"], recurring=True)

        desc_ch = cand["channel"].replace("_", " ")
        target = (cand.get("merchant") or {}).get("name") or (cand.get("beneficiary") or {}).get("name") or "SEPA Direct Debit"
        items.append({
            "name": f"eu_{home.lower()}_{i:04d}",
            "description": f"{hub['city']} ({home}): {cand['amount']:.2f} EUR via {desc_ch} — {target}",
            "label": label,
            "type": RANDOM_TYPES.get(kind, "unusual_legit"),
            "expected": None,
            "request": {"customer": cust, "history": hist, "candidate": cand},
        })
    return items


def write_scenarios(out_dir: str | Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old_file in out_dir.glob("*.json"):
        old_file.unlink()
    paths = []
    for s in scenarios():
        p = out_dir / f"{s['name']}.json"
        p.write_text(json.dumps(s, indent=2) + "\n")
        paths.append(p)
    return paths
