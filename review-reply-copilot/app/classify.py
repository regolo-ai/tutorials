"""Decide with Clef-Flash: sentiment, topic, escalation, reply priority and language for each review.

Five typed questions per review, one review per request, 8 requests in parallel.
We tried 12 reviews per request (60 questions, close to the limit of 64): Clef-Flash flagged about
more than twice as many reviews for escalation as it should. With 4 per request some false flags remained,
and with one review per request the flags matched what we expected, at lower token cost and the same
wall time. Subtle decisions need small batches, so the 64 question limit is a ceiling and not a target.
Each answer comes back with a confidence, and answers below ``LOW_CONFIDENCE`` are flagged
so a person looks at them first.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.regolo import RegoloClient

BATCH = 1
WORKERS = 8
LOW_CONFIDENCE = 0.8

SENTIMENT = {
    "positive": "The customer is satisfied and recommends or praises the company.",
    "neutral": "The customer reports facts or gives a plain opinion without clear praise or complaint.",
    "negative": "The customer is dissatisfied, complains or warns others.",
    "mixed": "The customer praises some things and complains about others.",
}
ESCALATION = {
    "none": "Ordinary feedback that the support team can answer in public. Complaints about delivery, product quality, price, discount codes, refunds, bugs or support speed belong here, even when the customer is angry or writes that they will tell others.",
    "escalate": "The review contains at least one of these: a legal threat or lawyer, a complaint to a regulator or consumer authority, a bank chargeback or payment dispute, a safety problem or injury, an accusation of fraud or a scam, a data protection or privacy request, a journalist or press. A person must handle it before any public reply.",
}
PRIORITY = {
    "reply_needed": "The customer has a problem, a question, a complaint or a clear request, so a public reply is expected.",
    "optional": "A short positive or neutral review where a reply is nice but not required.",
}
LANGUAGE = {
    "en": "English", "it": "Italian", "de": "German", "fr": "French", "es": "Spanish",
    "other": "Any other language.",
}
QUESTIONS = ("sentiment", "topic", "escalation", "priority", "language")


def _criteria(brand: dict) -> dict[str, dict]:
    return {
        "sentiment": SENTIMENT, "topic": brand["topics"], "escalation": ESCALATION,
        "priority": PRIORITY, "language": LANGUAGE,
    }


def _instruction(kind: str, i: int) -> str:
    asks = {
        "sentiment": "what is the overall sentiment of the customer review",
        "topic": "which topic is the main reason for the customer review",
        "escalation": "must a person handle this customer review before any public reply",
        "priority": "does this customer review need a public reply",
        "language": "in which language is the customer review written",
    }
    return f"In sentence [{i}], {asks[kind]}? Choose exactly one."


def build_request(brand: dict, reviews: list[dict]) -> tuple[list[dict], dict]:
    criteria = _criteria(brand)
    sentences = [{"id": i, "text": f"{(r.get('title') or '').strip()}. {r['text']}".strip(". ")[:1500]} for i, r in enumerate(reviews)]
    questions = {}
    for i in range(len(reviews)):
        for kind in QUESTIONS:
            questions[f"r{i}_{kind}"] = {"type": "choice", "criteria": criteria[kind], "instructions": _instruction(kind, i)}
    return sentences, questions


def parse_answers(reviews: list[dict], answers: dict) -> list[dict]:
    out = []
    for i in range(len(reviews)):
        labels = {}
        for kind in QUESTIONS:
            a = answers[f"r{i}_{kind}"]
            labels[kind] = {"label": a["choice"], "confidence": round(float(a.get("confidence") or 0), 3)}
        labels["low_confidence"] = any(labels[k]["confidence"] < LOW_CONFIDENCE for k in QUESTIONS)
        out.append(labels)
    return out


def _one_batch(client: RegoloClient, brand: dict, chunk: list[dict], on_progress=None) -> list[dict]:
    sentences, questions = build_request(brand, chunk)
    labels = parse_answers(chunk, client.decide(sentences, questions))
    if on_progress:
        on_progress(len(chunk))
    return labels


def classify_reviews(client: RegoloClient, brand: dict, reviews: list[dict], on_progress=None) -> list[dict]:
    """Returns one labels dict per review, in the same order. ``on_progress(n)`` is called after each request."""
    chunks = [reviews[start:start + BATCH] for start in range(0, len(reviews), BATCH)]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        batches = list(pool.map(lambda chunk: _one_batch(client, brand, chunk, on_progress), chunks))
    return [labels for batch in batches for labels in batch]
