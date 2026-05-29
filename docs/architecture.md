# AB6 AI Agent Architecture

## Core Pattern: OODA Loop (Observe → Orient → Decide → Act)

Each active learner session runs a continuous OODA loop via a LangGraph state machine. The agent never blocks—it observes asynchronously, diagnoses in the background, and delivers interventions invisibly.

## System Stack

| Layer | Technology |
|---|---|
| AI Agent Framework | LangGraph (Python) |
| LLM Providers | OpenAI (primary), Anthropic, Gemini (fallbacks) |
| Agent Memory | PostgreSQL (AsyncPostgresSaver) + Redis |
| Event Pipeline | Redis Streams |
| Primary Database | PostgreSQL 16 + pgvector |
| Concept Graph | PostgreSQL (adjacency list + recursive CTEs) |
| Task Queue | ARQ (async Redis queue) |
| Backend API | FastAPI |
| Cache / Session | Redis JSON |

## Key Components

1. **Event Ingestion Pipeline** — Redis Streams consuming observations, telemetry, and domain events
2. **OODA Agent** — LangGraph state machine with 5 nodes (observe, orient, decide, act, pause)
3. **Dual Memory** — Personal Memory (per-user mastery map) + Global Wisdom Store (cross-user intervention effectiveness)
4. **Concept Graph** — DAG of concepts with prerequisite edges, auto-built from video titles
5. **Intervention Engine** — Thompson Sampling selection, dynamic challenge generation, WebSocket delivery

## Scaling

- Stage 1 (500 users): Single server, all-in-one
- Stage 2 (5,000): 2-3 FastAPI instances, Redis Cluster, Postgres read replicas
- Stage 3 (20,000): K8s with HPA, dedicated ARQ workers
