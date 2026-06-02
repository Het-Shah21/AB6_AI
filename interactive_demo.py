import logging
from typing import Any

import uvicorn
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="AB6 AI Agent — Interactive Demo")

# In-memory agent state (survives across requests)
_agent_state: dict[str, Any] = {}
_initialized = False

EVENT_TEMPLATES = {
    "correct": {"event_type": "end_attempt", "challenge_id": "ik-challenge-1", "score": 0.9, "is_correct": True},
    "wrong": {"event_type": "end_attempt", "challenge_id": "ik-challenge-1", "score": 0.3, "is_correct": False},
    "run_code": {"event_type": "run_code", "challenge_id": "ik-challenge-1"},
    "page_view": {"event_type": "page_view", "page": "/video/inverse-kinematics"},
    "start_attempt": {"event_type": "start_attempt", "challenge_id": "ik-challenge-1", "is_correct": None},
    "wrong_kinematics": {"event_type": "end_attempt", "challenge_id": "forward-kinematics", "score": 0.25, "is_correct": False},
    "wrong_angles": {"event_type": "end_attempt", "challenge_id": "joint-angles", "score": 0.2, "is_correct": False},
}


async def init_state():
    global _initialized, _agent_state
    if _initialized:
        return
    from legacy.agent.graph import create_initial_state
    _agent_state = await create_initial_state("interactive-user", "interactive-session", max_cycles=3)
    _initialized = True


async def run_agent() -> dict:
    global _agent_state
    from legacy.agent.graph import build_ooda_graph
    graph = build_ooda_graph()
    agent = graph.compile()
    _agent_state = await agent.ainvoke(_agent_state)
    return _agent_state


def build_page(state: dict) -> str:
    inter = state.get("intervention_delivered")
    struggles = state.get("diagnosed_struggles", [])
    traces = [m.get("content", "") for m in state.get("messages", []) if m.get("content")]

    inter_html = '<p style="color:#8b949e">None yet</p>'
    if inter:
        inter_html = f"""
<div style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:1rem">
  <span style="display:inline-block;background:#1f6feb33;color:#58a6ff;font-size:0.75rem;font-weight:600;padding:0.25rem 0.6rem;border-radius:4px;text-transform:uppercase">{inter['type']}</span>
  <div style="margin-top:0.5rem;color:#e6edf3">{inter['content']['body']}</div>
</div>"""

    struggles_html = ", ".join(struggles) if struggles else '<span style="color:#3fb950">None</span>'

    traces_html = ""
    for t in traces[-8:]:
        color = "#8b949e"
        if "OBSERVE" in t: color = "#58a6ff"
        elif "ORIENT" in t: color = "#d29922"
        elif "DECIDE" in t: color = "#f0883e"
        elif "ACT" in t or "PAUSE" in t: color = "#3fb950"
        traces_html += f'<div style="color:{color}">{t}</div>\n'

    events = state.get("raw_events", [])
    events_html = ""
    for e in events[-10:]:
        et = e.get("event_type", "")
        cid = e.get("challenge_id", e.get("page", ""))
        score = e.get("score", "")
        correct = e.get("is_correct", "")
        lbl = f"[{et}] {cid}"
        if score != "" and isinstance(score, (int, float)):
            lbl += f" score={score:.1f}"
        if correct is not None:
            lbl += f" {'✓' if correct else '✗'}"
        events_html += f'<div style="font-size:0.82rem;color:#8b949e;padding:0.15rem 0">{lbl}</div>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AB6 AI Agent — Interactive Demo</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0d1117;color:#e6edf3;padding:1.5rem;display:flex;flex-direction:column;align-items:center}}
  .container{{max-width:900px;width:100%}}
  h1{{font-size:1.6rem;font-weight:700;color:#58a6ff;margin-bottom:0.25rem}}
  .subtitle{{color:#8b949e;font-size:0.85rem;margin-bottom:1.5rem}}
  .layout{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}
  @media(max-width:700px){{.layout{{grid-template-columns:1fr}}}}
  .card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1rem;margin-bottom:1rem}}
  .card h2{{font-size:1rem;color:#58a6ff;margin-bottom:0.75rem;padding-bottom:0.4rem;border-bottom:1px solid #21262d}}
  .stat-row{{display:flex;gap:0.5rem;flex-wrap:wrap}}
  .stat{{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:0.5rem 0.75rem;flex:1;min-width:80px;text-align:center}}
  .stat-lbl{{font-size:0.65rem;color:#8b949e;text-transform:uppercase}}
  .stat-val{{font-size:1.2rem;font-weight:700}}
  .green{{color:#3fb950}} .blue{{color:#58a6ff}} .yellow{{color:#d29922}} .red{{color:#f85149}}
  .btn{{display:inline-block;padding:0.5rem 1rem;font-size:0.8rem;font-weight:600;border:none;border-radius:6px;cursor:pointer;color:#fff;text-decoration:none;margin:0.2rem;transition:all 0.1s}}
  .btn-event{{background:#1f6feb;color:#fff}}
  .btn-event:hover{{background:#388bfd}}
  .btn-reset{{background:#da3633}}
  .btn-reset:hover{{background:#f85149}}
  .btn-ooda{{background:#238636;display:block;width:100%;padding:0.75rem;font-size:0.95rem;margin:0.5rem 0 0.25rem 0}}
  .btn-ooda:hover{{background:#2ea043}}
  .btn:disabled{{opacity:0.4;cursor:not-allowed}}
  .event-log{{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:0.5rem;max-height:240px;overflow-y:auto;font-family:'Cascadia Code','Fira Code',monospace;font-size:0.78rem;line-height:1.5}}
  .trace-box{{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:0.5rem;max-height:240px;overflow-y:auto;font-family:'Cascadia Code','Fira Code',monospace;font-size:0.8rem;line-height:1.5}}
  .btn-grid{{display:flex;flex-wrap:wrap;gap:0.3rem;margin-bottom:0.5rem}}
  .label{{font-size:0.75rem;color:#8b949e;margin-bottom:0.25rem}}
</style>
</head>
<body>
<div class="container">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <h1>AB6 AI Agent</h1>
      <div class="subtitle">Interactive OODA Demo &mdash; Click events to feed the agent, then run the cycle</div>
    </div>
    <form method="POST" action="/reset" style="display:inline">
      <button class="btn btn-reset" type="submit">Reset</button>
    </form>
  </div>

  <div class="layout">
    <div>
      <div class="card">
        <h2>Agent State</h2>
        <div class="stat-row">
          <div class="stat"><div class="stat-lbl">Cycle</div><div class="stat-val blue">{state.get("cycle_count", 0)}</div></div>
          <div class="stat"><div class="stat-lbl">Engagement</div><div class="stat-val green">{state.get("engagement_score", 0.5):.2f}</div></div>
          <div class="stat"><div class="stat-lbl">Pause</div><div class="stat-val {"yellow" if state.get("should_pause") else "green"}">{"ON" if state.get("should_pause") else "OFF"}</div></div>
          <div class="stat"><div class="stat-lbl">Struggles</div><div class="stat-val {"red" if struggles else "green"}" style="font-size:0.9rem">{len(struggles)}</div></div>
        </div>
        <div style="margin-top:0.5rem">
          <div class="label">Diagnosed: {struggles_html}</div>
        </div>
      </div>

      <div class="card">
        <h2>Event Log</h2>
        <div class="event-log">{events_html or '<div style="color:#8b949e">No events yet. Click an event button below.</div>'}</div>
      </div>

      <div class="card">
        <h2>Steps walked</h2>
        <div style="display:flex;gap:0.25rem;margin-bottom:0">
          <div style="flex:1;text-align:center;padding:0.4rem;border-radius:4px;background:#23863622;border:1px solid #238636;color:#3fb950;font-size:0.7rem;font-weight:600">Observe</div>
          <div style="display:flex;align-items:center;color:#30363d">→</div>
          <div style="flex:1;text-align:center;padding:0.4rem;border-radius:4px;background:#1f6feb22;border:1px solid #1f6feb;color:#58a6ff;font-size:0.7rem;font-weight:600">Orient</div>
          <div style="display:flex;align-items:center;color:#30363d">→</div>
          <div style="flex:1;text-align:center;padding:0.4rem;border-radius:4px;background:#f0883e22;border:1px solid #f0883e;color:#f0883e;font-size:0.7rem;font-weight:600">Decide</div>
          <div style="display:flex;align-items:center;color:#30363d">→</div>
          <div style="flex:1;text-align:center;padding:0.4rem;border-radius:4px;background:#3fb95022;border:1px solid #3fb950;color:#3fb950;font-size:0.7rem;font-weight:600">Act</div>
        </div>
      </div>

      <div class="card">
        <h2>Intervention</h2>
        {inter_html}
      </div>
    </div>

    <div>
      <div class="card">
        <h2>Send Events</h2>
        <div class="btn-grid">
          <form method="POST" action="/send-event" style="display:inline">
            <input type="hidden" name="event" value="start_attempt">
            <button class="btn btn-event" type="submit">Start attempt</button>
          </form>
          <form method="POST" action="/send-event" style="display:inline">
            <input type="hidden" name="event" value="correct">
            <button class="btn btn-event" type="submit">Correct answer</button>
          </form>
          <form method="POST" action="/send-event" style="display:inline">
            <input type="hidden" name="event" value="wrong">
            <button class="btn btn-event" type="submit">Wrong answer</button>
          </form>
          <form method="POST" action="/send-event" style="display:inline">
            <input type="hidden" name="event" value="run_code">
            <button class="btn btn-event" type="submit">Run code</button>
          </form>
          <form method="POST" action="/send-event" style="display:inline">
            <input type="hidden" name="event" value="page_view">
            <button class="btn btn-event" type="submit">Watch video</button>
          </form>
          <form method="POST" action="/send-event" style="display:inline">
            <input type="hidden" name="event" value="wrong_kinematics">
            <button class="btn btn-event" type="submit">Fail kinematics</button>
          </form>
          <form method="POST" action="/send-event" style="display:inline">
            <input type="hidden" name="event" value="wrong_angles">
            <button class="btn btn-event" type="submit">Fail joint angles</button>
          </form>
        </div>
        <form method="POST" action="/run-ooda">
          <button class="btn btn-ooda" type="submit">Run OODA Cycle</button>
        </form>
      </div>

      <div class="card">
        <h2>Execution Trace</h2>
        <div class="trace-box">{traces_html or '<div style="color:#8b949e">Run the OODA cycle to see traces.</div>'}</div>
      </div>
    </div>
  </div>
</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    await init_state()
    return build_page(_agent_state)


@app.post("/send-event")
async def send_event(event: str = Form(...)):
    await init_state()
    template = EVENT_TEMPLATES.get(event)
    if template:
        _agent_state.setdefault("raw_events", []).append(dict(template))
    return build_page(_agent_state)


@app.post("/run-ooda")
async def run_ooda():
    await init_state()
    await run_agent()
    return build_page(_agent_state)


@app.post("/reset")
async def reset():
    global _initialized, _agent_state
    _initialized = False
    _agent_state = {}
    await init_state()
    return build_page(_agent_state)


if __name__ == "__main__":
    print("=" * 50)
    print("AB6 AI Agent — Interactive Demo")
    print("=" * 50)
    print("Open http://127.0.0.1:8000 in your browser")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
