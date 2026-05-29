# AB6 AI Agent — Adaptive Learning Engine

## Overview

AI-powered adaptive learning agent for the AB6 Robotics Education platform. Uses an **OODA Loop** (Observe → Orient → Decide → Act) per learner to deliver invisible, personalized interventions.

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

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system design.

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

Full API docs at [docs/api.md](docs/api.md).

## Testing

```bash
pytest tests/ -v
```
