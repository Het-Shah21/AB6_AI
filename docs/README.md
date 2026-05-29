# AB6 AI Agent — Full Codebase Documentation

## Overview

The **AB6 AI Agent** is a continuous OODA-loop (Observe–Orient–Decide–Act) adaptive learning agent for a robotics education platform. It watches student behavior in real time, diagnoses conceptual struggles using LLMs, selects interventions via Thompson Sampling bandits, and delivers them through WebSocket/SSE channels.

**Core architecture:** LangGraph StateGraph with 5 nodes running in a cyclic loop, backed by PostgreSQL (pgvector), Redis streams, and 3 LLM providers (OpenAI, Anthropic, Google GenAI) with automatic fallback.

**Project structure:**
```
ab6_ai_vscode/
├── pyproject.toml          # Project config, dependencies, tool settings
├── .env.example            # Template for environment variables
├── .gitignore              # Git ignore rules
├── docker-compose.yml      # PostgreSQL 18 + Redis 7 + API server
├── alembic/                # Database migrations
│   ├── alembic.ini
│   └── versions/
│       └── 001_initial.py
├── src/
│   ├── __init__.py
│   ├── agent/              # OODA StateGraph, nodes, tools, prompts
│   ├── api/                # FastAPI app, routers, middleware
│   ├── config/             # Settings + LLM configuration
│   ├── concept_graph/      # Concept extraction, embeddings, CTE queries
│   ├── db/                 # Engine, 7 ORM models, 5 repositories
│   ├── ingestion/          # Redis streams, telemetry aggregator, ARQ worker
│   ├── intervention/       # Thompson selector, challenge generator, delivery
│   ├── llm/                # Provider with fallback chain, rate limiter, PII sanitizer
│   ├── memory/             # Personal, global wisdom, session cache, benchmarks
│   └── shared/             # Exceptions, event models, telemetry math
├── tests/
│   └── unit/               # 21 unit tests across 7 files
├── demo.py                 # CLI single-cycle demo
├── web_demo.py             # Server-rendered HTML demo
├── interactive_demo.py     # Interactive form-based demo (currently running)
└── docs/                   # This documentation
```

## Phases (matching the Master System Design)

| Phase | Directory | Files | Purpose |
|-------|-----------|-------|---------|
| **1 – Foundation** | `docs/phase-01-foundation/` | 8 files | Project setup, config, DB engine, 7 ORM models, 5 repos, shared utils, alembic |
| **2 – LLM Integration** | `docs/phase-02-llm/` | 3 files | Provider with fallback chain, rate limiter, PII sanitizer |
| **3 – Event Pipeline** | `docs/phase-03-event-pipeline/` | 4 files | Redis streams, schemas, consumer, aggregator, ARQ worker |
| **4 – Concept Graph** | `docs/phase-04-concept-graph/` | 4 files | Graph models, embeddings, builder, recursive CTE queries |
| **5 – OODA Agent Core** | `docs/phase-05-ooda-agent/` | 16 files | State, graph wiring, 5 nodes, 6 tool sets, 4 prompt templates |
| **6 – Dual Memory** | `docs/phase-06-dual-memory/` | 4 files | Personal, global wisdom, session cache, population benchmarks |
| **7 – Intervention Engine** | `docs/phase-07-intervention/` | 4 files | Thompson selector, challenge generator, effectiveness tracker, delivery |
| **8 – API Layer** | `docs/phase-08-api/` | 7 files | FastAPI app, 5 routers, PII middleware |
| **9 – Testing & Demo** | `docs/phase-09-testing-demo/` | 5 files | 21 unit tests, CLI demo, web demos |

## How Each README Is Structured

Every code-file README follows this format:

1. **System Design Reference** — Which part of the master design it implements
2. **Purpose** — What this file does at a high level
3. **Line-by-Line Explanation** — Every line of code, what it does and why
4. **How It Connects** — Which other files/modules this file interacts with
5. **PoC Presentation Idea** — How to demonstrate this piece in a proof-of-concept
