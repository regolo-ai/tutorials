"""Write with a chat model, check with Clef-Flash.

The model gets the brand profile (voice, facts, things it must never do), the review and the
labels Clef-Flash produced. The draft then goes through the guardrail checks. If a blocking check
fails, the model gets the list of problems and tries once more. A person always approves.
"""
from __future__ import annotations

from app import guardrails
from app.regolo import RegoloClient

LANGUAGE_NAMES = {"en": "English", "it": "Italian", "de": "German", "fr": "French", "es": "Spanish"}


def system_prompt(brand: dict, language: str, holding: bool) -> str:
    limit = int(brand.get("max_chars", 700)) - len(brand.get("signature", "")) - 6
    never = "\n".join(f"- {rule}" for rule in brand.get("never", []))
    facts = "\n".join(f"- {fact}" for fact in brand.get("facts", []))
    forbidden = ", ".join(f'"{p}"' for p in brand.get("forbidden_phrases", [])) or "none"
    mode = (
        "This review needs a person before any detail is discussed. Write a short, neutral holding reply: thank the customer, say the "
        "team is looking into it, and point to the support contact. Do not admit fault, do not discuss legal, safety or privacy details."
        if holding else
        "For a positive review, thank the customer and mention one specific detail from the review. For a negative or mixed review, "
        "acknowledge the specific problem in plain words and say what happens next using only the listed facts."
    )
    return (
        f"You write public replies to customer reviews on behalf of {brand['name']}. {brand.get('about', '')}\n"
        f"Voice: {', '.join(brand.get('voice', []))}.\n"
        f"Never do any of these:\n{never}\n"
        f"Forbidden phrases: {forbidden}.\n"
        f"The only facts you may state:\n{facts}\n"
        f"The contact email you may mention is {brand.get('support_contact', '')}.\n"
        f"{mode}\n"
        f"Sound like a person on the team, not a template: do not start with 'Thank you for sharing', 'We hear that' or 'We are sorry to hear', vary the opening, and use the customer's own words for the problem. "
        f"Write in {language}. Use 2 to 4 sentences and at most {limit} characters. No emojis, no hashtags, no markdown. "
        "Do not sign the reply, the signature is added afterwards. Return only the reply text."
    )


def user_prompt(review: dict, labels: dict | None, problems: list[str] | None, feedback: str | None) -> str:
    parts = [f"Review ({review.get('rating') or 'no'} stars): {(review.get('title') or '').strip()}\n{review['text']}"]
    if labels:
        parts.append(f"Labels: sentiment {labels['sentiment']['label']}, topic {labels['topic']['label']}.")
    if feedback:
        parts.append(f"Extra instruction from the team: {feedback.strip()}")
    if problems:
        parts.append("Your previous draft failed these checks, fix them: " + "; ".join(problems))
    return "\n\n".join(parts)


def draft_reply(client: RegoloClient, brand: dict, review: dict, labels: dict | None, feedback: str | None = None,
                max_attempts: int = 2) -> dict:
    escalate = bool(labels and labels["escalation"]["label"] == "escalate")
    code = (labels or {}).get("language", {}).get("label", "en")
    language = LANGUAGE_NAMES.get(code, "the same language as the review")
    messages_system = system_prompt(brand, language, holding=escalate)
    problems: list[str] | None = None
    text, checks, attempts = "", [], 0
    for attempts in range(1, max_attempts + 1):
        body = client.write([{"role": "system", "content": messages_system},
                             {"role": "user", "content": user_prompt(review, labels, problems, feedback)}])
        text = f"{body.strip()}\n\n{brand.get('signature', '')}".strip()
        checks = guardrails.run_checks(client, brand, review, labels, text)
        failed = [c for c in checks if c["blocking"] and not c["passed"]]
        if not failed:
            break
        problems = [f"{c['label']} ({c['detail']})" for c in failed]
    return {"text": text, "checks": checks, "attempts": attempts, "status": guardrails.status_from(checks, escalate)}


def recheck(client: RegoloClient, brand: dict, review: dict, labels: dict | None, text: str) -> dict:
    escalate = bool(labels and labels["escalation"]["label"] == "escalate")
    checks = guardrails.run_checks(client, brand, review, labels, text)
    return {"checks": checks, "status": guardrails.status_from(checks, escalate)}
