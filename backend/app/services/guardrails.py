import re

from app.config import settings


class GuardrailError(ValueError):
    pass


_INJECTION = [
    re.compile(p, re.I)
    for p in [
        r"ignore (all |any )?(the )?(previous|prior|above) (instructions|rules)",
        r"(reveal|show|print) (me )?(your |the )?(system )?prompt",
        r"disregard .{0,40}(instructions|rules)",
        r"you are now (?!an? hr)",
        r"act as (?:an? )?(?:dan|developer mode)",
    ]
]

_PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[PAN]"),
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[AADHAAR]"),
    (re.compile(r"\b(?:\+?91[- ]?)?[6-9]\d{9}\b"), "[PHONE]"),
]


def check_input(text: str) -> str:
    """First line of defence. Not sufficient alone: real protection is that the LLM
    never has data or tools the user isn't already entitled to."""
    text = (text or "").strip()
    if not text:
        raise GuardrailError("Message is empty.")
    if len(text) > settings.max_message_chars:
        raise GuardrailError(f"Message too long (max {settings.max_message_chars} characters).")
    if any(p.search(text) for p in _INJECTION):
        raise GuardrailError("I can only help with HR questions.")
    return text


def redact(text: str) -> str:
    """Mask PII before anything goes to logs or the audit trail."""
    for pattern, repl in _PII:
        text = pattern.sub(repl, text)
    return text
