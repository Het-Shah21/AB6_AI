"""Tests for the policy engine."""

from __future__ import annotations

from src.mentor.policies import (
    HIGH_STAKES,
    LOW_STAKES,
    evaluate,
)


def test_challenge_swap_is_high_stakes() -> None:
    assert "challenge_swap" in HIGH_STAKES


def test_revision_prompt_is_high_stakes() -> None:
    assert "revision_prompt" in HIGH_STAKES


def test_hint_is_low_stakes() -> None:
    assert "hint" in LOW_STAKES


def test_evaluate_returns_approval_for_high_stakes() -> None:
    decision = evaluate(
        candidate_actions=["challenge_swap", "hint"],
        inferred=None,  # type: ignore[arg-type]
        prior=None,  # type: ignore[arg-type]
    )
    assert decision.requires_human_approval is True
    assert "challenge_swap" in decision.decision


def test_evaluate_returns_no_approval_for_low_stakes() -> None:
    decision = evaluate(
        candidate_actions=["hint", "encouragement"],
        inferred=None,  # type: ignore[arg-type]
        prior=None,  # type: ignore[arg-type]
    )
    assert decision.requires_human_approval is False
