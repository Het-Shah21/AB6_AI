# AB6 AI Mentor — Unified 8-Stage Adaptive Learning Engine

## Overview

The AB6 AI Mentor is an **8-stage adaptive learning agent** for the
AB6 Robotics Education platform. It replaces the previous OODA-loop
agent and the standalone YouTube analytics pipeline with a single
unified pipeline:

```
PRIOR INFO -> OBSERVE -> ANALYZE -> INFERENCE -> INTERPRET
                                                  |
                                                  v
                                              INTELLIGENCE
                                                  |
                                                  v
                                              INTERVENTION
                                                  |
                                                  v
                                               FEEDBACK -> END
```

Built with **LangGraph**, persisted to **PostgreSQL**, streamed over
**WebSocket**, exposed via **FastAPI**, controlled by a **Streamlit**
UI.

## Two launch modes

| Mode   | What it needs | Persistence | Start with |
|--------|---------------|-------------|------------|
| **With Docker** (production-like) | Docker Desktop, Python 3.11+ | Postgres + Redis + pgvector | `.\start-live.ps1` |
| **Without Docker** (zero install)  | Python 3.11+ only | In-memory dict OR single SQLite file | `.\start-nodocker.ps1` |

Both modes expose the same API and UI; the only difference is where
state is stored.

### With Docker (default, full stack)

```bash
.\start-live.ps1              # API + ARQ worker
.\start-live.ps1 -WithUi      # API + ARQ worker + Streamlit
```

This brings up Postgres 16 + pgvector and Redis 7 via `docker compose`,
runs `alembic upgrade head`, and starts the API and the ARQ worker as
background processes. UI on <http://127.0.0.1:8501>, API on
<http://127.0.0.1:8000>.

### Without Docker (no install)

```bash
.\start-nodocker.ps1                # pure in-memory, no file at all
.\start-nodocker.ps1 -UseSqlite     # persists to mentor_data.db
.\start-nodocker.ps1 -UseSqlite -WithUi
```

This sets `MENTOR_BACKEND=memory` (or `=sqlite`) and
`MENTOR_SESSION_BACKEND=memory` so the mentor runs entirely in-process.
The ARQ worker is skipped (no real Redis to subscribe to). The
observation log, learner profile, wisdom store, and curriculum
lookups all degrade gracefully when their tables are absent — the
mentor still produces interventions, it just doesn't persist them
across restarts.

## Switching backends at runtime

The backend is selected by two env vars (read by `src/config/settings.py`):

| Env var                   | Values                  | Default    |
|---------------------------|-------------------------|------------|
| `MENTOR_BACKEND`          | `postgres` / `sqlite` / `memory` | `postgres` |
| `MENTOR_SESSION_BACKEND`  | `redis` / `memory`      | `redis`    |
| `MENTOR_DB_PATH`          | path                    | `mentor_data.db` |

The matrix is:

| `MENTOR_BACKEND` | `MENTOR_SESSION_BACKEND` | What runs | File / service |
|------------------|--------------------------|-----------|----------------|
| `postgres`       | `redis`                  | Real Postgres + Redis (Docker or native) | `docker compose` |
| `sqlite`         | `memory`                 | aiosqlite + fakeredis | `mentor_data.db` |
| `memory`         | `memory`                 | in-process dicts | nothing |
| `postgres`       | `memory`                 | Postgres + in-process session | Docker Postgres only |

To switch, set the env var in your shell, then launch:

```bash
# PowerShell
$env:MENTOR_BACKEND = "memory"
$env:MENTOR_SESSION_BACKEND = "memory"
.\stop-live.ps1
.\start-nodocker.ps1 -WithUi
```

## API endpoints

| Method | Path                                | Purpose                          |
|--------|-------------------------------------|----------------------------------|
| `POST` | `/mentor/cycle`                     | Run a full 8-stage cycle         |
| `POST` | `/mentor/approve`                   | Resume a paused HITL cycle       |
| `GET`  | `/mentor/users`                     | List learners from `user_details`|
| `GET`  | `/mentor/pending/{user_id}`         | List HITL-queued cycles          |
| `GET`  | `/mentor/history/{user_id}`         | Recent observation_log rows      |
| `WS`   | `/mentor/ws?user_id=<uuid>`         | Live event streaming             |
| `GET`  | `/healthz`                          | Liveness probe                   |
| `GET`  | `/readyz`                           | Readiness probe (DB ping)         |

## Architecture

```
src/
├── mentor/         # Canonical: 8-stage pipeline
│   ├── stages/     # prior_info, observe, analyze, inference, interpret,
│   │               # intelligence, intervention, feedback
│   ├── memory/     # personal, global_wisdom, curriculum, session, observation_log
│   ├── graph.py    # LangGraph assembly with HITL interrupt
│   ├── policies.py # action whitelist + HITL rule engine
│   ├── state.py    # Pydantic per-stage payloads + MentorState TypedDict
│   └── observability.py
├── db/             # SQLAlchemy engine + SQLite + in-memory backends
├── llm/            # Shared multi-provider LLM abstraction
├── config/         # Pydantic Settings + LLM config
└── shared/         # Events, exceptions, telemetry math
mentor_app.py       # FastAPI entry point — the primary service
ui/                 # Streamlit control panel

legacy/             # Deprecated OODA + YouTube code (kept for tests)
```

## Testing

```bash
pytest tests/ -v
```

## Smoke test (no LLM keys needed)

```bash
# After start-nodocker.ps1
$resp = Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/mentor/cycle `
       -ContentType application/json -Body (Get-Content .\sample_cycle.json -Raw)
$resp | Format-List
```

The cycle returns a chosen action, rationale, confidence, and
delivered content even with no `OPENAI_API_KEY` set — the LLM
provider in `src/llm/provider.py` falls back to a hard-coded
response when all providers fail.
