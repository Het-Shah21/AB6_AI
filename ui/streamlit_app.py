"""Streamlit UI for the AB6 Mentor.

Run with:
    streamlit run ui/streamlit_app.py --server.port 8501

Set MENTOR_API env var to point at a different host (default
http://127.0.0.1:8000).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import streamlit as st

API = os.environ.get("MENTOR_API", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="AB6 AI Mentor",
    page_icon="\U0001f9ea",
    layout="wide",
)


def _check_health() -> dict[str, Any]:
    out: dict[str, Any] = {"api": API}
    try:
        r = httpx.get(f"{API}/healthz", timeout=2.0)
        out["live"] = r.status_code == 200
    except Exception as exc:
        out["live"] = False
        out["live_error"] = str(exc)
    try:
        r = httpx.get(f"{API}/readyz", timeout=2.0)
        out["ready"] = r.status_code == 200
    except Exception as exc:
        out["ready"] = False
        out["ready_error"] = str(exc)
    return out


def _list_users() -> list[dict[str, Any]]:
    try:
        r = httpx.get(f"{API}/mentor/users", params={"limit": 50}, timeout=5.0)
        r.raise_for_status()
        return r.json().get("users", [])
    except Exception as exc:
        st.error(f"user lookup failed: {exc}")
        return []


def _list_pending(user_id: str) -> list[dict[str, Any]]:
    try:
        r = httpx.get(
            f"{API}/mentor/pending/{user_id}", timeout=5.0
        )
        r.raise_for_status()
        return r.json().get("pending", [])
    except Exception as exc:
        st.error(f"pending lookup failed: {exc}")
        return []


def _user_history(user_id: str) -> list[dict[str, Any]]:
    try:
        r = httpx.get(
            f"{API}/mentor/history/{user_id}",
            params={"limit": 20},
            timeout=5.0,
        )
        r.raise_for_status()
        return r.json().get("cycles", [])
    except Exception as exc:
        st.error(f"history lookup failed: {exc}")
        return []


def _post_cycle(
    user_id: str,
    session_id: str,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    body = {
        "user_id": user_id,
        "session_id": session_id,
        "cycle_id": str(uuid.uuid4()),
        "events": events,
    }
    try:
        r = httpx.post(f"{API}/mentor/cycle", json=body, timeout=60.0)
        if r.status_code == 200:
            return r.json()
        st.error(f"cycle failed: {r.status_code} {r.text}")
        return None
    except Exception as exc:
        st.error(f"cycle call failed: {exc}")
        return None


def _post_approve(
    user_id: str,
    cycle_id: str,
    approved: bool,
    reviewer: str = "streamlit-ui",
    notes: str = "",
) -> dict[str, Any] | None:
    body = {
        "user_id": user_id,
        "cycle_id": cycle_id,
        "approved": approved,
        "reviewer": reviewer,
        "notes": notes,
    }
    try:
        r = httpx.post(f"{API}/mentor/approve", json=body, timeout=60.0)
        if r.status_code == 200:
            return r.json()
        st.error(f"approve failed: {r.status_code} {r.text}")
        return None
    except Exception as exc:
        st.error(f"approve call failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Sidebar — connection + user selection
# ---------------------------------------------------------------------------


with st.sidebar:
    st.title("AB6 AI Mentor")
    health = _check_health()
    if health["live"]:
        st.success(f"API live  \n{health['api']}/healthz")
    else:
        st.error(f"API not reachable  \n{health['api']}")
    if health.get("ready"):
        st.success("DB ready  \n/readyz OK")
    else:
        st.warning("DB not ready (will still attempt calls)")

    st.divider()
    st.subheader("Learner")
    users = _list_users()
    user_options: dict[str, str] = {}
    for u in users:
        label = (
            f"{u.get('full_name') or u['email']}  \u2014  {u['email']}"
        )
        user_options[label] = u["id"]
    if user_options:
        picked = st.selectbox(
            "Select a learner", list(user_options.keys())
        )
        selected_user_id = user_options[picked]
    else:
        st.info("No learners in DB \u2014 use the manual box below.")
        selected_user_id = st.text_input(
            "Or paste a user UUID",
            value=str(uuid.uuid4()),
            help="Will only persist if the user exists in ab6_user_data.user_details.",
        )

    st.divider()
    st.subheader("Session")
    default_session = st.session_state.get("session_id", str(uuid.uuid4()))
    session_id = st.text_input("Session ID", value=default_session)
    st.session_state["session_id"] = session_id

    if st.button("New session"):
        new_sid = str(uuid.uuid4())
        st.session_state["session_id"] = new_sid
        st.session_state.pop("events", None)
        st.rerun()

    st.divider()
    st.caption("Mentor: 8-stage LangGraph pipeline")
    st.caption("Stages: PRIOR \u2192 OBSERVE \u2192 ANALYZE \u2192 INFER \u2192")
    st.caption("INTERPRET \u2192 INTEL \u2192 INTERVENE \u2192 FEEDBACK")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


tabs = st.tabs(
    [
        "1. Events",
        "2. Run cycle",
        "3. Pending (HITL)",
        "4. History",
        "5. Raw",
    ]
)


with tabs[0]:
    st.header("Event stream")
    st.caption(
        "Each event is buffered in Redis (mentor:session:<user>:events) "
        "and also persisted to ab6_learning_data.mentor_observation_log. "
        "Press **Run cycle** to trigger a full 8-stage pipeline."
    )

    if "events" not in st.session_state:
        st.session_state["events"] = []

    with st.form("event_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            event_type = st.selectbox(
                "event_type",
                [
                    "page_view",
                    "code_run",
                    "code_execution",
                    "challenge_submit",
                    "submission",
                    "start_attempt",
                    "end_attempt",
                    "hint_request",
                    "show_hint",
                    "ask_help",
                    "page_navigate",
                    "tab_switch",
                ],
                index=0,
            )
        with c2:
            challenge_id = st.text_input("challenge_id", value="ik-challenge-1")
        with c3:
            page = st.text_input("page", value="/challenge/ik-challenge-1")

        c4, c5, c6, c7 = st.columns(4)
        with c4:
            score = st.number_input("score", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
        with c5:
            is_correct = st.checkbox("is_correct", value=False)
        with c6:
            attempt_no = st.number_input("attempt_no", min_value=1, value=1, step=1)
        with c7:
            run_no = st.number_input("run_no", min_value=0, value=0, step=1)

        c8, c9 = st.columns(2)
        with c8:
            action = st.text_input("action", value="submit")
        with c9:
            metadata = st.text_input(
                "metadata (JSON, optional)",
                value='{"time_spent": 90}',
            )

        submitted = st.form_submit_button("Add event")
        if submitted:
            try:
                meta_obj = json.loads(metadata) if metadata.strip() else {}
            except json.JSONDecodeError:
                meta_obj = {"raw": metadata}
                st.warning("metadata was not valid JSON, stored as string.")
            ev: dict[str, Any] = {
                "event_id": str(uuid.uuid4()),
                "session_id": st.session_state["session_id"],
                "user_id": selected_user_id,
                "timestamp": datetime.now(timezone.utc).timestamp(),
                "event_type": event_type,
                "page": page or None,
                "challenge_id": challenge_id or None,
                "score": score,
                "is_correct": is_correct,
                "attempt_no": int(attempt_no),
                "run_no": int(run_no),
                "action": action or None,
                "metadata": meta_obj,
            }
            st.session_state["events"].append(ev)
            st.success(f"event {len(st.session_state['events'])} added")

    st.divider()
    st.subheader(f"Buffered events ({len(st.session_state['events'])})")
    if st.session_state["events"]:
        st.dataframe(
            [
                {
                    "i": i,
                    "event_type": e["event_type"],
                    "challenge_id": e.get("challenge_id"),
                    "score": e.get("score"),
                    "is_correct": e.get("is_correct"),
                }
                for i, e in enumerate(st.session_state["events"])
            ],
            hide_index=True,
            use_container_width=True,
        )
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("Clear buffer"):
                st.session_state["events"] = []
                st.rerun()
        with cc2:
            st.download_button(
                "Download events as JSON",
                data=json.dumps(st.session_state["events"], indent=2),
                file_name="events.json",
                mime="application/json",
            )
    else:
        st.info("No events yet. Use the form above to add some.")


with tabs[1]:
    st.header("Run a cycle")
    st.caption(
        "POSTs the buffered events to `/mentor/cycle`, which runs the "
        "full 8-stage pipeline and returns the chosen intervention."
    )

    disabled = not st.session_state.get("events")
    if st.button(
        "Run cycle",
        type="primary",
        disabled=disabled,
        use_container_width=True,
    ):
        with st.spinner("Running 8-stage cycle ..."):
            resp = _post_cycle(
                user_id=selected_user_id,
                session_id=st.session_state["session_id"],
                events=st.session_state["events"],
            )
        if resp is not None:
            st.session_state["last_response"] = resp
            st.success(f"cycle {resp['cycle_id']} completed")

    resp = st.session_state.get("last_response")
    if resp:
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Action", resp.get("chosen_action") or "—")
        c2.metric(
            "Confidence",
            f"{float(resp['confidence']):.2f}" if resp.get("confidence") else "—",
        )
        delivered = "yes" if resp.get("delivered") else "blocked"
        c3.metric("Delivered", delivered)
        c4.metric(
            "HITL needed",
            "yes" if resp.get("requires_approval") else "no",
        )

        st.subheader("Rationale")
        st.code(resp.get("rationale") or "(no rationale)", language="text")

        st.subheader("Intervention content")
        st.markdown(resp.get("content") or "_(no content)_")

        st.subheader("Stage history")
        st.dataframe(
            resp.get("stage_history", []),
            hide_index=True,
            use_container_width=True,
        )


with tabs[2]:
    st.header("Pending HITL approvals")
    st.caption(
        "High-stakes interventions (challenge_swap, revision_prompt) "
        "are queued in Redis until a human approves or rejects them."
    )
    if st.button("Refresh pending", key="refresh_pending"):
        st.session_state["pending"] = _list_pending(selected_user_id)
    if "pending" not in st.session_state:
        st.session_state["pending"] = _list_pending(selected_user_id)
    pending = st.session_state["pending"]
    if not pending:
        st.info("No pending cycles for this user.")
    for item in pending:
        cid = item.get("cycle_id", "?")
        with st.expander(f"cycle {cid[:8]}…  queued at {item.get('queued_at','?')}"):
            st.json(item)
            c1, c2, c3 = st.columns(3)
            with c1:
                reviewer = st.text_input(
                    "reviewer", value="streamlit-ui", key=f"rev_{cid}"
                )
            with c2:
                if st.button("Approve", key=f"ok_{cid}", type="primary"):
                    out = _post_approve(
                        user_id=selected_user_id,
                        cycle_id=cid,
                        approved=True,
                        reviewer=reviewer,
                    )
                    if out:
                        st.success(f"approved \u2014 delivered={out.get('delivered')}")
                        st.session_state["pending"] = _list_pending(selected_user_id)
                        st.rerun()
            with c3:
                if st.button("Reject", key=f"no_{cid}"):
                    out = _post_approve(
                        user_id=selected_user_id,
                        cycle_id=cid,
                        approved=False,
                        reviewer=reviewer,
                        notes="rejected via Streamlit UI",
                    )
                    if out:
                        st.warning("rejected")
                        st.session_state["pending"] = _list_pending(selected_user_id)
                        st.rerun()


with tabs[3]:
    st.header("Recent cycles (observation_log)")
    st.caption(
        "Pulls from `ab6_learning_data.mentor_observation_log`. Newest first."
    )
    if st.button("Refresh history", key="refresh_history"):
        st.session_state["history"] = _user_history(selected_user_id)
    if "history" not in st.session_state:
        st.session_state["history"] = _user_history(selected_user_id)
    hist = st.session_state["history"]
    if hist:
        st.dataframe(hist, hide_index=True, use_container_width=True)
    else:
        st.info("No cycles yet for this user.")


with tabs[4]:
    st.header("Raw API state")
    st.subheader("Health")
    st.json(health)
    st.subheader("Selected user_id")
    st.code(selected_user_id)
    st.subheader("Session ID")
    st.code(st.session_state["session_id"])
    st.subheader("Buffered events (full payload)")
    st.json(st.session_state.get("events", []))
    st.subheader("Last cycle response")
    st.json(st.session_state.get("last_response", {}))
