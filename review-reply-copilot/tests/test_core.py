"""Tests that run offline: Regolo is replaced by a small fake."""
from app import brands, classify, guardrails, reply, store
from app.regolo import Meter, strip_reasoning

BRAND = brands.get_brand("acme-outdoor")
REVIEW = {"id": "r1", "title": "Late", "text": "Order took 14 days.", "rating": 2}


class FakeClient:
    """Answers Clef-Flash questions from a table and writes a fixed reply."""

    def __init__(self, choices=None, reply_text="Thanks for the feedback about the delay. Write to support@acme-outdoor.example."):
        self.choices = choices or {}
        self.reply_text = reply_text
        self.meter = Meter()
        self.decide_calls = []

    def decide(self, sentences, questions):
        self.decide_calls.append((sentences, questions))
        out = {}
        for qid, q in questions.items():
            kind = qid.split("_", 1)[-1]
            options = list(q["criteria"])
            choice = self.choices.get(kind) or self.choices.get(qid) or options[0]
            out[qid] = {"type": "choice", "choice": choice, "confidence": 0.97, "probabilities": {o: (0.97 if o == choice else 0.03 / max(1, len(options) - 1)) for o in options}}
        return out

    def write(self, messages, temperature=0.3, max_tokens=1400):
        self.last_messages = messages
        return self.reply_text


def test_strip_reasoning_removes_think_blocks():
    assert strip_reasoning("<think>plan</think>Hello") == "Hello"
    assert strip_reasoning("reasoning text</think>Hello") == "Hello"


def test_classify_builds_one_request_per_review_with_five_questions():
    client = FakeClient()
    reviews = [{"title": "a", "text": "one"}, {"title": "b", "text": "two"}, {"title": "c", "text": "three"}]
    labels = classify.classify_reviews(client, BRAND, reviews)
    assert len(labels) == 3 and len(client.decide_calls) == 3  # BATCH is 1
    for sentences, questions in client.decide_calls:
        assert len(questions) == 5 and len(sentences) == 1
    assert set(labels[0]) >= {"sentiment", "topic", "escalation", "priority", "language", "low_confidence"}


def test_classify_flags_low_confidence():
    client = FakeClient()
    original = client.decide

    def shaky(sentences, questions):
        out = original(sentences, questions)
        first = next(iter(out))
        out[first]["confidence"] = 0.55
        return out

    client.decide = shaky
    assert classify.classify_reviews(client, BRAND, [{"title": "", "text": "x"}])[0]["low_confidence"] is True


def test_topics_come_from_the_brand_profile():
    saas = brands.get_brand("northwind-cloud")
    _, questions = classify.build_request(saas, [{"title": "", "text": "x"}])
    assert "bugs_performance" in questions["r0_topic"]["criteria"]
    assert "shipping_delivery" not in questions["r0_topic"]["criteria"]


def test_rule_checks_catch_forbidden_phrases_contacts_and_length():
    bad = "We apologize for any inconvenience. Email me at someone@else.com or call +34 600 123 456. " + "x" * 800
    checks = {c["id"]: c for c in guardrails.rule_checks(BRAND, bad)}
    assert not checks["forbidden_phrases"]["passed"]
    assert not checks["contact_details"]["passed"]
    assert not checks["length"]["passed"]
    good = "Thanks for the details. Write to support@acme-outdoor.example and we will look into it with you."
    assert all(c["passed"] for c in guardrails.rule_checks(BRAND, good))


def test_empty_body_is_a_blocking_failure():
    checks = {c["id"]: c for c in guardrails.rule_checks(BRAND, BRAND["signature"])}
    assert not checks["not_empty"]["passed"] and checks["not_empty"]["blocking"]


def test_status_escalate_beats_ready():
    assert guardrails.status_from([], escalate=True) == "escalate"
    assert guardrails.status_from([{"passed": False, "blocking": True}], escalate=False) == "needs_edit"
    assert guardrails.status_from([{"passed": False, "blocking": False}], escalate=False) == "ready"


def test_draft_reply_retries_once_when_a_blocking_check_fails():
    client = FakeClient(choices={"compensation": "yes"})  # Clef-Flash says the draft promises compensation
    labels = classify.classify_reviews(client, BRAND, [REVIEW])[0]
    result = reply.draft_reply(client, BRAND, REVIEW, labels)
    assert result["attempts"] == 2 and result["status"] == "needs_edit"
    assert any(c["id"] == "compensation" and not c["passed"] for c in result["checks"])
    assert "failed these checks" in client.last_messages[-1]["content"]


def test_draft_reply_is_ready_when_checks_pass_and_signed():
    client = FakeClient(choices={"compensation": "no", "blame": "no", "personal_data": "no", "tone": "no", "competitor": "no",
                                 "language": "yes", "unsupported_claim": "no", "acknowledges": "yes"})
    labels = classify.classify_reviews(client, BRAND, [REVIEW])[0]
    result = reply.draft_reply(client, BRAND, REVIEW, labels)
    assert result["status"] == "ready" and result["attempts"] == 1
    assert result["text"].endswith(BRAND["signature"])


def test_escalation_gives_a_holding_reply_and_status_escalate():
    client = FakeClient(choices={"escalation": "escalate"})
    labels = classify.classify_reviews(client, BRAND, [REVIEW])[0]
    result = reply.draft_reply(client, BRAND, REVIEW, labels)
    assert result["status"] == "escalate"
    assert "holding reply" in client.last_messages[0]["content"]


def test_store_deduplicates_and_keeps_drafts():
    rows = [{"author": "A", "rating": "5", "title": "t", "text": "great", "date": "2026-01-01"}]
    assert store.add_reviews("acme-outdoor", "csv", rows) == 1
    assert store.add_reviews("acme-outdoor", "csv", rows) == 0
    rid = store.list_reviews("acme-outdoor")[0]["id"]
    draft = store.save_draft(rid, "hello", [], "ready", 1)
    assert store.latest_drafts("acme-outdoor")[rid]["id"] == draft["id"]
    assert store.approve_draft(draft["id"])["status"] == "approved"
    store.clear_brand("acme-outdoor")
    assert store.list_reviews("acme-outdoor") == []
