# AB6 AI Agent — Adaptive Learning Engine

## Overview

AI-powered adaptive learning agent for the AB6 Robotics Education platform.
Uses an **OODA Loop** (Observe → Orient → Decide → Act) per learner to
deliver invisible, personalized interventions.

## Quick Start

```bash
# Start infrastructure
docker-compose up -d

# Install dependencies
pip install -e .

# Run database migrations
alembic upgrade head

# Seed initial wisdom
python scripts/seed_wisdom.py

# Start API server
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

> **First time here?** Open [`docs/README.md`](docs/README.md) — it's the
> navigation manual for the whole codebase and tells you exactly what to
> read, in what order. For the visual one-page system overview, open
> [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md).

## Try it without any setup (demos work offline)

The 3-way LLM fallback chain lets the demos run with **no API keys**:

```bash
python demo.py --event wrong --max-cycles 1
python interactive_demo.py    # then open http://127.0.0.1:8001
```

You'll see three "LLM provider failed" warnings — that's expected. The
fallback returns hardcoded text so the cycle still completes.

## Architecture

See [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) for the full system
design (one picture, phase roster, end-to-end request trace, data-flow
tables, critical invariants).

See [`docs/architecture.md`](docs/architecture.md) for the original prose
overview.

See [`docs/EMBEDDED_SYSTEM_ARCHITECTURE.md`](docs/EMBEDDED_SYSTEM_ARCHITECTURE.md)
for how the agent fits into a Frontend → Proxy → Backend → Middleware →
Robot pipeline, plus robustness/scalability analysis, Go + gRPC
compatibility, and tech-stack migration recipes.

## Project Structure

```
src/
├── agent/          # OODA Agent (LangGraph state machine)
├── api/            # FastAPI routers & middleware
├── concept_graph/  # Knowledge graph extraction & query
├── config/         # Pydantic Settings + LLM config
├── db/             # SQLAlchemy models & repositories
├── ingestion/      # Redis Streams event pipeline
├── intervention/   # Thompson Sampling selector + generators
├── llm/            # Multi-provider LLM abstraction
├── memory/         # Personal & Global Wisdom services
└── shared/         # Events, exceptions, telemetry math
```

## API Endpoints

| Prefix | Description |
|---|---|
| `POST /api/v1/ai/events` | Ingest observation events |
| `WS /api/v1/ai/telemetry/ws` | Real-time telemetry |
| `WS /api/v1/ai/interventions/{id}/ws` | Intervention delivery |
| `POST /api/v1/ai/agent/sessions/{id}/cycle` | Run OODA cycle |

Full API docs at [`docs/api.md`](docs/api.md).

## Documentation Map

| Document | Purpose |
|---|---|
| [`docs/README.md`](docs/README.md) | **Start here** — the navigation manual |
| [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) | Master visual system design |
| [`docs/EMBEDDED_SYSTEM_ARCHITECTURE.md`](docs/EMBEDDED_SYSTEM_ARCHITECTURE.md) | Embedded-system fit, robustness, scalability, Go/gRPC migration |
| `docs/architecture.md` | Original prose architecture overview |
| `docs/api.md` | API reference |
| `docs/concept_graph.md` | Concept graph deep-dive |
| `docs/intervention_types.md` | Intervention type catalog |
| `docs/phase-0X-…/00-system-design.md` | Visual diagrams per phase |
| `docs/phase-0X-…/0N-*.md` | Line-by-line prose per code file |

## Testing

```bash
pytest tests/ -v
```

21 unit tests across 5 files guard the contracts established by the 9
phases. See [`docs/phase-09-testing-and-demo/00-system-design.md`](docs/phase-09-testing-and-demo/00-system-design.md)
for the test pyramid and which test guards which bug.
