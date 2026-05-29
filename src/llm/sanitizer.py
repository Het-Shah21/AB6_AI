import re
from typing import Any


PII_PATTERNS = [
    (r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[EMAIL]"),
    (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]"),
    (r"\b\d{16,19}\b", "[CARD]"),
    (r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", "[NAME]"),
]


def strip_pii(text: str) -> str:
    result = text
    for pattern, replacement in PII_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def sanitize_observation_event(event: dict[str, Any]) -> dict[str, Any]:
    safe = event.copy()
    safe.pop("user_id", None)
    safe.pop("session_id", None)
    safe["metadata"] = strip_pii(str(safe.get("metadata", "")))
    return safe


def sanitize_learner_summary(summary: dict[str, Any]) -> dict[str, Any]:
    safe = summary.copy()
    safe.pop("user_id", None)
    safe.pop("session_id", None)
    if "recent_errors" in safe:
        safe["recent_errors"] = [
            strip_pii(str(e)) for e in safe["recent_errors"]
        ]
    return safe
