# Streamlit UI for the AB6 Mentor

A minimal control panel for the live `mentor_app` API.

## Run

```bash
# 1. Make sure the mentor API is up
.\start-live.ps1

# 2. In a separate shell, launch the UI
pip install streamlit httpx
streamlit run ui/streamlit_app.py --server.port 8501
```

The UI opens at <http://127.0.0.1:8501>.

To point the UI at a different API host:

```bash
export MENTOR_API=http://my-mentor-host:8000   # PowerShell: $env:MENTOR_API=...
streamlit run ui/streamlit_app.py
```

## Tabs

| Tab        | What it does                                                   |
|------------|----------------------------------------------------------------|
| 1. Events  | Build a buffered event stream; events go to Redis + Postgres   |
| 2. Run cycle | POSTs buffered events to `/mentor/cycle`, shows intervention |
| 3. Pending | Lists HITL-queued cycles; approve / reject inline             |
| 4. History | Pulls recent cycles from `ab6_learning_data.mentor_observation_log` |
| 5. Raw     | Health, current user/session, full payloads for debugging     |

## What it does NOT do

- Auth.  Do not expose the API or this UI to the public internet
  without putting a real auth layer in front.
- Streaming interventions.  For real-time intervention delivery use
  the WebSocket at `ws://<api>/mentor/ws?user_id=<uuid>`.
- Multi-user comparison.  Pick a learner from the sidebar; pick a
  different one to switch.
