import asyncio
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="AB6 AI Agent Live Demo")


async def run_ooda_demo() -> dict:
    from src.agent.graph import build_ooda_graph, create_initial_state

    graph = build_ooda_graph()
    agent = graph.compile()

    state = await create_initial_state("demo-user", "demo-session", max_cycles=1)

    state["raw_events"] = [
        {"event_type": "start_attempt", "challenge_id": "ik-challenge-1", "is_correct": None},
        {"event_type": "end_attempt", "challenge_id": "ik-challenge-1", "score": 0.3, "is_correct": False},
        {"event_type": "run_code", "challenge_id": "ik-challenge-1"},
        {"event_type": "run_code", "challenge_id": "ik-challenge-1"},
        {"event_type": "end_attempt", "challenge_id": "ik-challenge-1", "score": 0.35, "is_correct": False},
        {"event_type": "page_view", "page": "/video/inverse-kinematics"},
    ]

    result = await agent.ainvoke(state)

    traces = []
    for m in result.get("messages", []):
        traces.append(m.get("content", ""))

    intervention = result.get("intervention_delivered")
    return {
        "cycle_count": result.get("cycle_count", 0),
        "engagement_score": result.get("engagement_score", 0.5),
        "should_pause": result.get("should_pause", False),
        "diagnosed_struggles": result.get("diagnosed_struggles", []),
        "intervention": intervention,
        "delivery_channel": result.get("delivery_channel", ""),
        "traces": traces,
    }


def build_html(data: dict) -> str:
    inter = data.get("intervention")
    inter_html = ""
    if inter:
        inter_html = f"""
<div style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:1rem;margin-top:0.5rem">
  <div style="display:inline-block;background:#1f6feb33;color:#58a6ff;font-size:0.75rem;font-weight:600;padding:0.25rem 0.6rem;border-radius:4px;text-transform:uppercase">{inter['type']}</div>
  <div style="margin-top:0.5rem;color:#e6edf3;font-size:0.95rem">{inter['content']['body']}</div>
  <div style="margin-top:0.5rem;font-size:0.8rem;color:#8b949e">Channel: {data.get('delivery_channel','')} &middot; ID: {inter['intervention_id'][:8]}</div>
</div>"""
    else:
        inter_html = '<p style="color:#8b949e;font-style:italic">No intervention delivered.</p>'

    struggles = data.get("diagnosed_struggles", [])
    struggles_str = ", ".join(struggles) if struggles else '<span style="color:#3fb950">None</span>'

    traces = data.get("traces", [])
    traces_str = "\n".join(t for t in traces)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AB6 AI Agent — Live Demo</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0d1117;color:#e6edf3;display:flex;flex-direction:column;align-items:center;padding:2rem 1rem}}
  .container{{max-width:800px;width:100%}}
  h1{{font-size:2rem;font-weight:700;color:#58a6ff}}
  .subtitle{{color:#8b949e;margin-bottom:2rem;font-size:0.9rem}}
  .card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1.5rem;margin-bottom:1rem}}
  .card h2{{font-size:1.1rem;color:#58a6ff;margin-bottom:1rem;padding-bottom:0.5rem;border-bottom:1px solid #21262d}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:0.75rem}}
  .stat{{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:0.75rem}}
  .stat-lbl{{font-size:0.75rem;color:#8b949e;text-transform:uppercase}}
  .stat-val{{font-size:1.5rem;font-weight:700;margin-top:0.25rem}}
  .trace-box{{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:0.75rem;font-family:'Cascadia Code','Fira Code',monospace;font-size:0.82rem;line-height:1.6;white-space:pre-wrap}}
  .arch{{margin-top:1.5rem;display:flex;justify-content:center;gap:0}}
  .arch-step{{background:#23863622;border:1px solid #238636;color:#3fb950;padding:0.5rem 0.75rem;font-size:0.75rem;font-weight:600}}
  .arch-step:first-child{{border-radius:6px 0 0 6px}}
  .arch-step:last-child{{border-radius:0 6px 6px 0}}
  .arch-arrow{{color:#30363d;display:flex;align-items:center;font-size:1rem}}
  .btn{{display:inline-flex;align-items:center;gap:0.5rem;padding:0.75rem 2rem;font-size:1rem;font-weight:600;border:none;border-radius:6px;cursor:pointer;background:#238636;color:#fff;text-decoration:none}}
  .btn:hover{{background:#2ea043}}
  .green{{color:#3fb950}} .blue{{color:#58a6ff}} .yellow{{color:#d29922}} .red{{color:#f85149}}
</style>
</head>
<body>
<div class="container">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2rem">
    <div>
      <h1>AB6 AI Agent</h1>
      <div class="subtitle">OODA Loop &mdash; Observe &rarr; Orient &rarr; Decide &rarr; Act</div>
    </div>
    <a href="/" class="btn">&#x21bb; Re-run Demo</a>
  </div>

  <div class="card">
    <h2>Cycle Results</h2>
    <div class="grid">
      <div class="stat"><div class="stat-lbl">Cycle Count</div><div class="stat-val blue">{data["cycle_count"]}</div></div>
      <div class="stat"><div class="stat-lbl">Engagement Score</div><div class="stat-val green">{data["engagement_score"]:.2f}</div></div>
      <div class="stat"><div class="stat-lbl">Should Pause</div><div class="stat-val {"yellow" if data["should_pause"] else "green"}">{"Yes" if data["should_pause"] else "No"}</div></div>
      <div class="stat"><div class="stat-lbl">Diagnosed Struggles</div><div class="stat-val {"red" if struggles else "green"}" style="font-size:1rem">{struggles_str}</div></div>
    </div>
  </div>

  <div class="card">
    <h2>Intervention Delivered</h2>
    {inter_html}
  </div>

  <div class="card">
    <h2>Execution Trace</h2>
    <div class="trace-box">{traces_str}</div>
  </div>

  <div class="arch">
    <div class="arch-step">Observe</div><div class="arch-arrow">&rarr;</div>
    <div class="arch-step">Orient</div><div class="arch-arrow">&rarr;</div>
    <div class="arch-step">Decide</div><div class="arch-arrow">&rarr;</div>
    <div class="arch-step">Act</div>
  </div>
</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    result = await run_ooda_demo()
    return build_html(result)


if __name__ == "__main__":
    print("=" * 50)
    print("AB6 AI Agent — Live Web Demo")
    print("=" * 50)
    print("Open http://127.0.0.1:8000 in your browser")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
