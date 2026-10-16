"""Check a draft reply before a person sees it.

Two kinds of check run on every draft. Rules are plain code (length, forbidden phrases, contact
details). Clef-Flash answers yes or no questions about meaning (promises compensation, blames the
customer, defensive tone, other language). A failed *blocking* check keeps the draft from being
marked ready. Neither kind is a guarantee: a person approves every reply.
"""
from __future__ import annotations

import re

from app.regolo import RegoloClient

YES_NO = {"yes": "The statement is true for the reply.", "no": "The statement is not true for the reply."}

# id, label, question about sentence [1] (the reply), fail_if, blocking
CLEF_CHECKS = [
    ("compensation", "No promise of refund or compensation",
     "Does the reply in sentence [1] promise or offer a refund, replacement, discount, credit or other compensation?", "yes", True),
    ("blame", "Does not blame the customer",
     "Does the reply in sentence [1] blame, criticise or argue with the customer?", "yes", True),
    ("personal_data", "Does not ask for personal details in public",
     "Does the reply in sentence [1] ask the customer to write personal or account details in the public thread (such as an order number, email address, phone number, address or payment details)? Pointing to the company's own contact email does not count.", "yes", True),
    ("tone", "Tone is not defensive or dismissive",
     "Is the tone of the reply in sentence [1] defensive, dismissive, sarcastic or cold?", "yes", True),
    ("competitor", "Does not mention competitors",
     "Does the reply in sentence [1] mention or compare with another company or competitor?", "yes", True),
    ("language", "Same language as the review",
     "Is the reply in sentence [1] written in the same language as the review in sentence [0]?", "no", True),
    ("unsupported_claim", "Only states facts from the brand profile",
     "Does the reply in sentence [1] state a fact, policy, deadline or number that does not appear in sentence [2]?", "yes", False),
    ("acknowledges", "Acknowledges the customer's issue",
     "Does the reply in sentence [1] acknowledge the problem or feeling the customer describes in sentence [0]?", "no", False),
]

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"https?://\S+|www\.\S+")
PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d")


def rule_checks(brand: dict, text: str) -> list[dict]:
    results = []
    body = text.replace(brand.get("signature", ""), "").strip()
    results.append({"id": "not_empty", "label": "Has a written reply", "passed": len(body) >= 30, "blocking": True,
                    "source": "rule", "detail": f"{len(body)} characters before the signature", "confidence": None})
    limit = int(brand.get("max_chars", 700))
    results.append({"id": "length", "label": f"At most {limit} characters", "passed": len(text) <= limit, "blocking": True,
                    "source": "rule", "detail": f"{len(text)} characters", "confidence": None})
    lowered = text.lower()
    hits = [p for p in brand.get("forbidden_phrases", []) if p.lower() in lowered]
    results.append({"id": "forbidden_phrases", "label": "No forbidden phrases", "passed": not hits, "blocking": True,
                    "source": "rule", "detail": ("found: " + ", ".join(hits)) if hits else "none found", "confidence": None})
    allowed = (brand.get("support_contact") or "").lower()
    extra = [e for e in EMAIL.findall(text) if e.lower() != allowed] + URL.findall(text) + PHONE.findall(text)
    results.append({"id": "contact_details", "label": "Only the brand's own contact email", "passed": not extra, "blocking": True,
                    "source": "rule", "detail": ("found: " + ", ".join(extra[:3])) if extra else "ok", "confidence": None})
    shouts = text.count("!")
    results.append({"id": "exclamations", "label": "Calm punctuation", "passed": shouts <= 2, "blocking": False,
                    "source": "rule", "detail": f"{shouts} exclamation marks", "confidence": None})
    return results


def clef_checks(client: RegoloClient, brand: dict, review: dict, labels: dict | None, text: str) -> list[dict]:
    sentiment = ((labels or {}).get("sentiment") or {}).get("label")
    active = []
    for cid, label, question, fail_if, blocking in CLEF_CHECKS:
        if cid == "compensation" and brand.get("allow_compensation"):
            continue
        if cid == "acknowledges" and sentiment not in ("negative", "mixed"):
            continue
        active.append((cid, label, question, fail_if, blocking))
    facts = " ".join(brand.get("facts", [])) or "No facts available."
    sentences = [
        {"id": 0, "text": f"{(review.get('title') or '').strip()}. {review['text']}".strip(". ")[:1500]},
        {"id": 1, "text": text[:1500]},
        {"id": 2, "text": facts},
    ]
    questions = {cid: {"type": "choice", "criteria": YES_NO, "instructions": question} for cid, _, question, _, _ in active}
    answers = client.decide(sentences, questions)
    out = []
    for cid, label, _, fail_if, blocking in active:
        a = answers[cid]
        failed = a["choice"] == fail_if
        out.append({"id": cid, "label": label, "passed": not failed, "blocking": blocking, "source": "clef",
                    "detail": f"Clef-Flash answered {a['choice']}", "confidence": round(float(a.get("confidence") or 0), 3)})
    return out


def run_checks(client: RegoloClient, brand: dict, review: dict, labels: dict | None, text: str) -> list[dict]:
    return rule_checks(brand, text) + clef_checks(client, brand, review, labels, text)


def status_from(checks: list[dict], escalate: bool) -> str:
    if escalate:
        return "escalate"
    return "ready" if all(c["passed"] for c in checks if c["blocking"]) else "needs_edit"
