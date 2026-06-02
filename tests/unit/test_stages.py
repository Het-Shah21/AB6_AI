"""Tests for the analyze and feedback stages.

These are pure-Python heuristic stages; we can run them with a
synthetic MentorState and assert the outputs without any DB.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.mentor.stages import analyze, feedback
from src.mentor.state import (
    AnalyzedPattern,
    InferredState,
    InterventionDecision,
    MentorEvent,
    MentorState,
    ObservedSignals,
    PriorSnapshot,
)


def _state(events: list[MentorEvent]) -> MentorState:
    observed = ObservedSignals(
        event_count=len(events),
        events=events,
        type_counts={},
        page_counts={},
        challenge_counts={},
        focus_challenge_id="c1",
        focus_page="/challenge/c1",
        session_id="s1",
    )
    prior = PriorSnapshot(
        user_id=uuid.uuid4(),
        mastery={"c1": 0.5},
        struggles=[],
        completed_challenges=[],
        recent_attempts=[],
    )
    inferred = InferredState(
        inferred_concept="c1",
        concept_mastery=0.4,
        unmastered_challenges=["c1"],
        skill_bucket="stuck",
        confidence=0.6,
        rationale="test",
    )
    intervention = InterventionDecision(
        cycle_id=uuid.uuid4(),
        user_id=prior.user_id,
        action="hint",
        target_concept="c1",
        target_challenge="c1",
        rationale="test",
        confidence=0.5,
        requires_approval=False,
    )
    return {
        "user_id": str(prior.user_id),
        "session_id": "s1",
        "cycle_id": uuid.uuid4(),
        "messages": [],
        "prior": prior.model_dump(mode="json"),
        "observed": observed.model_dump(mode="json"),
        "analyzed": {},
        "inferred": inferred.model_dump(mode="json"),
        "interpreted": {},
        "intervention": intervention.model_dump(mode="json"),
        "delivered": {},
        "feedback": {},
        "stage_history": [],
    }


def _run_with_caps(cids: list[str], fails: int) -> AnalyzedPattern:
    events: list[MentorEvent] = []
    for i in range(5):
        events.append(
            MentorEvent(
                event_id=f"e{i}",
                session_id="s1",
                user_id=uuid.uuid4(),
                timestamp=datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc).timestamp() + i,
                event_type="code_run",
                challenge_id="c1",
                is_correct=i >= 3,
                score=20.0 if i < 3 else 80.0,
            )
        )
    state = _state(events)
    out = analyze.run(state)  # type: ignore[arg-type]
    return AnalyzedPattern.model_validate(out["analyzed"])


def test_analyze_detects_struggle() -> None:
    pattern = _run_with_caps(["c1"], fails=2)
    assert "c1" in pattern.struggle_challenges
    assert pattern.failed_runs.get("c1", 0) >= 1


def test_analyze_handles_empty_stream() -> None:
    state = _state([])
    out = analyze.run(state)  # type: ignore[arg-type]
    pattern = AnalyzedPattern.model_validate(out["analyzed"])
    assert pattern.event_count == 0 or pattern.struggle_challenges == []


def test_feedback_records_outcome() -> None:
    events: list[MentorEvent] = []
    state = _state(events)
    out = feedback.run(state)  # type: ignore[arg-type]
    assert "feedback" in out
    fb = out["feedback"]
    assert "success" in fb
    assert "score_delta" in fb
