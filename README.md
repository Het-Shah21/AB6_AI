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

The pipeline is built with **LangGraph**, persists to **PostgreSQL**,
streams over **WebSocket**, and is exposed via **FastAPI**.

## Quick start

```bash
# Full live stack (Postgres + Redis + uvicorn + ARQ worker)
.\start-live.ps1

# Or manually:
docker compose up -d postgres redis
pip install -e .
alembic upgrade head
uvicorn mentor_app:app --host 0.0.0.0 --port 8000
```

> **First time here?** Open [`docs/README.md`](docs/README.md) — it's
> the navigation manual for the whole codebase.  See
> [`LEGACY.md`](LEGACY.md) for the deprecation map.

## API endpoints

| Method | Path                                | Purpose                          |
|--------|-------------------------------------|----------------------------------|
| `POST` | `/mentor/cycle`                     | Run a full 8-stage cycle         |
| `POST` | `/mentor/approve`                   | Resume a paused HITL cycle       |
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
├── llm/            # Shared multi-provider LLM abstraction
├── db/             # Shared SQLAlchemy models, engine, repositories
├── config/         # Pydantic Settings + LLM config
└── shared/         # Events, exceptions, telemetry math
mentor_app.py       # FastAPI entry point — the primary service

legacy/             # Deprecated OODA agent + YouTube agent
├── agent/          # OODA graph and nodes
├── youtube_agent/  # YouTube analytics
├── api/            # OODA FastAPI routers
├── concept_graph/  # Knowledge graph builder/queries
├── memory/         # Legacy personal/global/session services
├── intervention/   # Legacy Thompson selector + generators
├── ingestion/      # Legacy Redis Streams consumer + ARQ worker
└── youtube_app.py  # Standalone FastAPI shim
```

## Testing

```bash
pytest tests/ -v
```

The suite covers the PII sanitizer, the policy engine, the analyze /
feedback stages, the legacy OODA unit tests, and the mentor
integration tests.

## Project structure

| Path                | Description                                      |
|---------------------|--------------------------------------------------|
| `src/mentor/`       | Canonical 8-stage mentor package                 |
| `legacy/`           | Deprecated OODA + YouTube code (kept for tests)  |
| `tests/`            | Pytest suite (unit + integration)                |
| `alembic/`          | Database migrations                              |
| `scripts/`          | One-shot DB scripts (seed wisdom, etc.)          |
| `docs/`             | Architecture and design notes                    |
| `mentor_app.py`     | FastAPI entry point                              |
| `LEGACY.md`         | What moved, what stayed, what to delete          |
