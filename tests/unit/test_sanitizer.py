"""Tests for the PII sanitizer."""

from __future__ import annotations

from src.llm.sanitizer import sanitize_pii, strip_pii


def test_strip_email() -> None:
    out = strip_pii("contact jane.doe@example.com please")
    assert "[EMAIL]" in out
    assert "jane.doe" not in out


def test_strip_phone() -> None:
    out = strip_pii("call 415-555-1234 tomorrow")
    assert "[PHONE]" in out
    assert "415-555" not in out


def test_strip_card() -> None:
    out = strip_pii("card 4111111111111111 here")
    assert "[CARD]" in out


def test_name_with_blocklist() -> None:
    assert strip_pii("Inverse Kinematics is fun") == "Inverse Kinematics is fun"
    assert strip_pii("Forward Kinematics lab") == "Forward Kinematics lab"


def test_name_redacts_personal_name() -> None:
    out = strip_pii("Jane Doe submitted work")
    assert "[NAME]" in out
    assert "Jane Doe" not in out


def test_sanitize_pii_dict() -> None:
    payload = {
        "user": "jane.doe@example.com",
        "note": "Jane Doe did 415-555-1234 today",
        "nested": {"card": "4111111111111111"},
    }
    out = sanitize_pii(payload)
    assert "[EMAIL]" in out["user"]
    assert "[PHONE]" in out["note"]
    assert "[CARD]" in out["nested"]["card"]
    assert "[NAME]" in out["note"]


def test_sanitize_pii_list() -> None:
    out = sanitize_pii(["a@b.com", "Jane Doe"])
    assert "[EMAIL]" in out[0]
    assert "[NAME]" in out[1]
