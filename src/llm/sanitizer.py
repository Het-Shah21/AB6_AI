import re
from typing import Any


PII_PATTERNS = [
    (r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[EMAIL]"),
    (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]"),
    (r"\b\d{16,19}\b", "[CARD]"),
]

# Two-token names — bounded so it does not match "Inverse Kinematics"
# or other legitimate two-word technical terms. Only fires when
# surrounded by sentence-like boundaries.
_NAME_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<n>[A-Z][a-z]{1,15})\s+(?P<m>[A-Z][a-z]{1,15})(?![A-Za-z])"
)
# Suppress list of capitalized two-word phrases that are NOT personal
# names.  This is small and curated; expand as new false-positives are
# reported.
_NAME_BLOCKLIST = {
    ("inverse", "kinematics"),
    ("forward", "kinematics"),
    ("unit", "vector"),
    ("unit", "matrix"),
    ("world", "coordinates"),
    ("state", "machine"),
    ("state", "space"),
    ("graph", "search"),
    ("linked", "list"),
    ("binary", "search"),
    ("decision", "tree"),
    ("monte", "carlo"),
    ("ray", "tracing"),
    ("ros", "publisher"),
    ("ros", "subscriber"),
}


def _strip_names(text: str) -> str:
    def _sub(match: re.Match[str]) -> str:
        first, second = match.group("n").lower(), match.group("m").lower()
        if (first, second) in _NAME_BLOCKLIST:
            return match.group(0)
        return "[NAME]"

    return _NAME_PATTERN.sub(_sub, text)


def strip_pii(text: str) -> str:
    if text is None:
        return text
    result = str(text)
    for pattern, replacement in PII_PATTERNS:
        result = re.sub(pattern, replacement, result)
    result = _strip_names(result)
    return result


def sanitize_pii(value: Any) -> Any:
    """Recursively strip PII from a JSON-like value."""
    if isinstance(value, str):
        return strip_pii(value)
    if isinstance(value, dict):
        return {k: sanitize_pii(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_pii(v) for v in value]
    if isinstance(value, tuple):
        return tuple(sanitize_pii(v) for v in value)
    return value


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
