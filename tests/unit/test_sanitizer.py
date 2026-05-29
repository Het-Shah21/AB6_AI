import pytest

from src.llm.sanitizer import strip_pii, sanitize_observation_event


def test_strip_email():
    assert "[EMAIL]" in strip_pii("user@example.com")


def test_strip_phone():
    assert "[PHONE]" in strip_pii("Call 123-456-7890 now")


def test_strip_no_pii():
    text = "This is a plain text about robotics kinematics."
    assert strip_pii(text) == text


def test_sanitize_observation():
    event = {
        "user_id": "abc-123",
        "session_id": "session-xyz",
        "event_type": "click",
        "metadata": {"email": "test@test.com"},
    }
    safe = sanitize_observation_event(event)
    assert "user_id" not in safe
    assert "session_id" not in safe
    assert "[EMAIL]" in safe["metadata"]
