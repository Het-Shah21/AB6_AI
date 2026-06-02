# AB6 AI Agent — Per-File Code Audit & Improvement Map

> Comprehensive file-by-file analysis of the current codebase.
> For each file: **what it does today**, **what could be improved**, and
> **what could be added/modified/changed/updated** to make it stronger.
>
> Scope: every tracked source file (Python, HTML, PowerShell, TOML, INI,
> Mako, env). Build artefacts under `src/ab6_ai_agent.egg-info/` are
> auto-generated and intentionally skipped.

---

## Table of contents

1. [Project root](#1-project-root)
2. [alembic/](#2-alembic)
3. [src/](#3-src)
4. [src/api/](#4-srcapi)
5. [src/agent/](#5-srcagent)
6. [src/concept_graph/](#6-srcconcept_graph)
7. [src/config/](#7-srcconfig)
8. [src/db/](#8-srcdb)
9. [src/ingestion/](#9-srcingestion)
10. [src/intervention/](#10-srcintervention)
11. [src/llm/](#11-srcllm)
12. [src/memory/](#12-srcmemory)
13. [src/shared/](#13-srcshared)
14. [src/youtube_agent/](#14-srcyoutube_agent)
15. [scripts/](#15-scripts)
16. [tests/](#16-tests)
17. [templates/](#17-templates)
18. [Cross-cutting improvements](#18-cross-cutting-improvements)

---

## 1. Project root

### `README.md`
**Currently:** Landing doc. Lists quick start (docker-compose + alembic +
seed + uvicorn), points at the one-shot `start-live.ps1` for the full
stack, lists the offline demo entry points, and points readers at
`docs/SYSTEM_DESIGN.md` and the phase docs. Calls out the "21 unit tests
across 5 files" claim and links to the test pyramid doc.

**What could be improved:**
- The claim "21 unit tests" is brittle (test count will rot); make it
  dynamic or drop it.
- The Quick Start says `docker-compose up -d` (v1 CLI). Project actually
  uses v2 (`docker compose`); fix or note both.
- Add a `Badges` row (CI, coverage, Python) and a screenshot/GIF of the
  interactive demo.

**What could be added/changed/updated:**
- Add a `Troubleshooting` section (Postgres not ready, LLM keys, port
  conflicts, Windows/Linux commands).
- Add a "Project Status" badge list (which phases are done, which are
  WIP).
- Add a `Security & PII` section pointing at `src/llm/sanitizer.py`.
- Add a `License` and `Contributing` link.
- Add a "How to run only the agent (no API)" subsection.
- Move the API table here instead of `docs/api.md` to make README
  self-contained.

---

### `pyproject.toml`
**Currently:** PEP-621 project manifest. Declares runtime deps
(FastAPI, uvicorn, langgraph, langchain-{openai,anthropic,google-genai},
asyncpg, SQLAlchemy, alembic, redis[hiredis], arq, pgvector, numpy,
pydantic, sse-starlette, sentry-sdk, httpx, tenacity, websockets) and
dev deps (pytest, pytest-asyncio, pytest-cov, mypy, ruff, matplotlib).
Configures ruff (line-length 100, E/F/I/W), mypy strict + missing
imports, and pytest (asyncio_mode=auto, testpaths=tests).

**What could be improved:**
- `name = "ab6-ai-agent"` vs the import root `ab6_ai_agent.egg-info`
  mismatch; align.
- No `requires-python` upper bound (3.14 might break langchain pins).
- No `project.urls` (Homepage, Repo, Issues).
- No tool configs for: bandit (security), vulture (dead code),
  pip-audit, pre-commit, coverage thresholds.
- `pytest.ini_options` lacks `asyncio_default_fixture_loop_scope` which
  is required by pytest-asyncio ≥0.23.
- No `[tool.coverage.*]` block — `pytest --cov` has no thresholds.

**What could be added/changed/updated:**
- Add `python = ">=3.11,<3.14"` cap.
- Add `bandit`, `pip-audit`, `pre-commit`, `vulture` to dev deps.
- Pin critical transitive deps (pgvector, sse-starlette are loose).
- Add a `[tool.coverage.run]` and `[tool.coverage.report]` with
  `fail_under = 70`.
- Add `[tool.ruff.lint.per-file-ignores]` for tests, scripts, alembic.
- Add `[tool.mypy.overrides]` for tests and `src/llm/*` (third-party
  stubs are weak).
- Add `[tool.pytest.ini_options] markers` (slow, integration, llm).

---

### `docker-compose.yml`
**Currently:** Two services: `postgres` (pgvector/pgvector:pg16, db
`ab6_ai`, user `ab6`, pass `ab6_pass`, port 5432, named volume
`pgdata`) and `redis` (redis:7-alpine, AOF persistence). No services
for the API or worker — those run on the host.

**What could be improved:**
- No `restart` policy; containers won't survive a daemon restart.
- No healthchecks for postgres/redis; the `start-live.ps1` polls
  `pg_isready` and `redis-cli ping` manually.
- No resource limits (`mem_limit`, `cpus`).
- Hard-coded credentials in plaintext; should use `.env` interpolation
  (compose `env_file:`).
- No `pgadmin`/`redis-commander` for dev; would help debugging.

**What could be added/changed/updated:**
- Add `healthcheck:` blocks for both services with `test:`, `interval:`,
  `retries:` and switch the script to `depends_on: { service_healthy }`.
- Add a `api` and `worker` service in compose so the entire stack
  (`docker compose up`) brings up everything (DOCKERFILE needed).
- Add a `network: ab6_net` for explicit isolation.
- Move secrets to `.env` (`POSTGRES_PASSWORD=${POSTGRES_PASSWORD}`).
- Add `logging:` driver config (json-file, rotation).
- Add an `init` container that runs `alembic upgrade head` once.

---

### `.env.example`
**Currently:** Documents DB, Redis, three LLM keys, agent/provider
config, rate limit, Sentry, log level. Does not document the stream
names, intervention cooldown, max events, or wisdom TTL that exist in
`src/config/settings.py`.

**What could be improved:**
- No comments on units (rpm vs rps).
- All values are placeholders; no defaults for the missing-`OPENAI_API_KEY`
  "demo mode" warning.
- No placeholders for new fields (`LLM_TEMPERATURE`, timeouts, etc.).

**What could be added/changed/updated:**
- Add the redis stream names, cooldown, and cache TTL entries.
- Add `LLM_REQUEST_TIMEOUT_S`, `LLM_MAX_RETRIES`.
- Add `SENTRY_TRACES_SAMPLE_RATE`.
- Add a "Demo mode" note next to `OPENAI_API_KEY` explaining the
  fallback chain.

---

### `.gitignore`
**Currently:** Standard Python + IDE + OS + logs. Reasonable defaults.

**What could be improved:**
- Missing `*.sqlite`, `*.db` (local dev DBs).
- Missing `.runtime-pids.json` (created by start-live.ps1) and
  `.runtime-logs/`.
- Missing `.venv/`, `venv/`, `env/`.
- Missing `coverage.xml`, `htmlcov/`.
- Missing `.mypy_cache/`, `.ruff_cache/`.

**What could be added/changed/updated:**
- Add `.runtime-pids.json` and `.runtime-logs/`.
- Add coverage/mypy/ruff cache directories.
- Add `.env.local` and `.env.*.local` overrides.

---

### `start-live.ps1`
**Currently:** Idempotent PowerShell bootstrap. Pre-flight (Docker v2,
Python 3.11+), `docker compose up -d postgres redis`, waits up to
`WaitSeconds` for health via `pg_isready`/`redis-cli ping`, creates
`.venv`, installs `.[dev]`, copies `.env.example` to `.env` if missing,
warns when no LLM key, runs `alembic upgrade head`, spawns `arq` worker
and `uvicorn` as hidden background processes, health-checks
`/health` 20×, persists PIDs to `.runtime-pids.json`, prints summary
with sample curl. Flags: `-SkipInstall`, `-SkipMigrate`, `-ApiPort`,
`-WaitSeconds`.

**What could be improved:**
- Windows-only (`py` launcher, `.exe` paths); there's no
  `start-live.sh` for Linux/macOS developers or CI.
- Hard-codes container names (`ab6-ai-vscode-postgres-1`); will break
  if the project is renamed or moved.
- PID file write uses BOM-included UTF-8 (`new($false)`) — fine, but
  no atomic rename.
- Background process restart on crash: none.
- LLM-key check matches literal `sk-...` sentinel only.

**What could be added/changed/updated:**
- Add a `start-live.sh` (and/or Makefile target) that mirrors the
  same flow on POSIX shells.
- Add `-ComposeProjectName` override so the script doesn't break when
  the dir name changes.
- Add `-NoWorker` to skip ARQ when only running the API.
- Add log rotation policy for `.runtime-logs/`.
- Add `-Reset` to `docker compose down -v` before up (destructive; gate
  behind confirmation).
- Trap Ctrl-C to cleanly stop both children.

---

### `stop-live.ps1`
**Currently:** Stops the two background processes by PID from
`.runtime-pids.json` with a "belt-and-suspenders" name-based kill pass.
Optional `-AlsoDocker` flag stops (but does not remove) the postgres +
redis containers.

**What could be improved:**
- Same Windows-only limitation.
- After stopping, container removal needs a separate `docker compose
  down`; confusing.
- No log cleanup.

**What could be added/changed/updated:**
- Add `-RemoveVolumes` that runs `docker compose down -v`.
- Add `-PurgeLogs` that wipes `.runtime-logs/`.
- Add a POSIX-equivalent `stop-live.sh`.
- Print a "what was running" summary (ports, PIDs) at start.

---

### `demo.py`
**Currently:** Pure-Python demo. Builds the OODA graph, creates an
initial state with 6 hard-coded events, runs one cycle, and prints a
text summary (cycle count, engagement, pause flag, struggles,
intervention). No DB, no LLM keys required (falls back to demo
strings).

**What could be improved:**
- Hard-coded event list makes regression checks impossible; move to a
  fixture file.
- Single-shot — can't iterate; add a `--replay` mode.
- Output is plain text; no JSON output for piping.

**What could be added/changed/updated:**
- Add `--json` for machine-readable output.
- Add `--max-cycles N`.
- Add a `--scenario {success,struggle,exploration,abandon}` flag with
  canned event sets.
- Add a `--seed` for Thompson sampling determinism.
- Compare against a golden snapshot in CI.

---

### `interactive_demo.py`
**Currently:** Self-contained FastAPI app on port 8000 with in-memory
agent state. Renders a dark-themed HTML page, lets the user click
buttons to append canned events, run a cycle, or reset. Uses POST
form submissions, not WebSockets. Logs to WARNING.

**What could be improved:**
- Global mutable state (`_agent_state`, `_initialized`) is not
  thread-safe; would break under multi-worker uvicorn.
- Same port (8000) as the real API; clashes with `start-live.ps1`.
- HTML is a 256-line f-string in code; no separation.
- No automated tests for the demo.

**What could be added/changed/updated:**
- Move HTML to `templates/interactive_demo.html`.
- Switch to a real WebSocket (SSE) for live trace updates.
- Add a `--port` flag (default 8001 to avoid clash).
- Add pytest cases that POST to each route.
- Add a "scenario runner" panel with the canned JSON.

---

### `web_demo.py`
**Currently:** Simpler one-shot FastAPI app. Every `GET /` builds a
fresh OODA graph, runs a single hard-coded cycle, and renders an HTML
page. No persistence.

**What could be improved:**
- Recompiles the graph on every request (wasteful).
- No way to feed real events.
- Hard-coded event set.
- No tests.

**What could be added/changed/updated:**
- Add event-form like `interactive_demo.py` but on a different port.
- Cache the compiled graph at startup.
- Extract HTML to a template.
- Add a `--port 8002` and a `--no-reload` flag.
- Optionally bind to the same event API as `interactive_demo.py` so one
  demo can be deprecated.

---

### `youtube_app.py`
**Currently:** Independent FastAPI app for YouTube-watching sessions
that uses `src.youtube_agent.*`. Hard-coded credentials
(`admin/admin123`, `demo/demo123`, `test/test123`), cookie-based
`user_id` session, in-memory `sessions` dict, three HTML pages
(login, watch, results) embedded as huge f-string constants. JS uses
the YouTube IFrame API to track play/pause/seek/tab-switch/timeupdate
events. The pipeline is "PRIOR INFO → OBSERVE → ANALYZE → INFERENCE →
INTERPRET → INTELLIGENCE → FEEDBACK" (a 7-step superset of the
LangGraph OODA).

**What could be improved:**
- Plaintext password dict is hard-coded; this is dev-only but should
  at least be env-driven and hashed.
- All HTML is f-string-inlined; huge memory footprint and not
  template-cached.
- Sessions dict grows forever; no eviction.
- `USER_CREDENTIALS` in code; should come from settings.
- No CSRF, no rate limit on `/login`.
- Templates exist under `templates/youtube_*.html` but are never
  loaded (the f-string copies are used instead).
- The `run_pipeline` is synchronous in spirit (state passes through
  dicts); concurrency will be limited.

**What could be added/changed/updated:**
- Move HTML to Jinja2 templates and use `Jinja2Templates` instead of
  the embedded f-strings.
- Replace cookie auth with a proper JWT or session middleware.
- Add persistence of `AgentState` to Redis (already have SessionCache).
- Add a YouTube-data-v3 transcript fetch so the agent can correlate
  playback segments with the actual spoken content.
- Add a real DB-backed `users` table.
- Add rate limiting on login + per-IP.
- Add unit tests for `YouTubeAnalytics.analyze` and `YouTubeAgent`.

---

## 2. `alembic/`

### `alembic.ini`
**Currently:** Standard alembic config. `script_location = alembic`,
`sqlalchemy.url` set to localhost string (overridden at runtime by
`env.py` from `Settings`). Logger config and a `console` handler.

**What could be improved:**
- Hard-coded `sqlalchemy.url` is misleading; can be removed since
  `env.py` overrides it.
- No `file_template` / `sourceless` config.

**What could be added/changed/updated:**
- Drop the hard-coded URL (or comment it "fallback only").
- Add `timezone = UTC` and `compare_type = true` in env.py for type-
  change detection.

---

### `alembic/env.py`
**Currently:** Async-compatible env. Reads `Settings().database_url`,
overrides `config.set_main_option`, runs `run_async_migrations` via
`asyncio.run`. Uses `Base.metadata` from `src.db.engine`.

**What could be improved:**
- Silently swallows `asyncio.get_running_loop()` differences.
- The `setup` call on the checkpointer is wrapped in bare `try/except`
  in `src/agent/graph.py`; env.py doesn't do any table-create.

**What could be added/changed/updated:**
- Enable `compare_type=True` and `compare_server_default=True` in
  `context.configure(...)` for safer schema diffs.
- Add a `run_migrations_offline` path for SQL-only diffs (CI).
- Add `include_schemas=True` so the `ab6_learning_data` schema diffs
  cleanly.

---

### `alembic/script.py.mako`
**Currently:** Default alembic template. Imports sqlalchemy + op,
defines `upgrade()` / `downgrade()` placeholders.

**What could be improved:**
- Imports `from typing import Sequence, Union` but doesn't add
  `pgvector` or `sqlalchemy.dialects.postgresql` for the project.

**What could be added/changed/updated:**
- Pre-import `from sqlalchemy.dialects import postgresql` and
  `from pgvector.sqlalchemy import Vector` since every future
  migration likely needs them.
- Add a docstring header template ("What this migration does").

---

### `alembic/versions/0001_initial_schema.py`
**Currently:** Creates the `ab6_learning_data` schema and 7 tables:
`ai_learner_profiles`, `ai_intervention_log`, `ai_wisdom_store`,
`ai_concepts` (with `vector(1536)`), `ai_concept_edges`,
`ai_concept_mappings`, `ai_population_benchmarks`. Indexes on
intervention user/type; unique constraint on
`(concept_id, intervention_type, profile_segment)` for wisdom.

**What could be improved:**
- References `ab6_user_data.user_details.id` (a foreign schema) that
  doesn't exist in this repo. Migration will fail on a fresh DB.
- No `pgvector` extension creation; relies on the image.
- No HNSW/IVFFlat index on `ai_concepts.embedding`; similarity search
  will be slow at scale.
- No `created_at` / `updated_at` triggers — only server defaults.
- Downgrade order drops tables alphabetically; should be in dependency
  order.

**What could be added/changed/updated:**
- Add `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` explicitly.
- Add `op.execute("CREATE INDEX ... USING hnsw (embedding
  vector_cosine_ops)")` for fast ANN search.
- Add a separate migration to create `ab6_user_data.user_details`
  (or document the external dependency).
- Add `CHECK` constraints on `engagement_score` (0..1) and
  `effectiveness_label` enum.
- Add partial unique index on `ai_population_benchmarks` (already
  `UNIQUE` on `concept_id`).

---

## 3. `src/`

### `src/__init__.py`
**Currently:** Empty.

**What could be improved:**
- Could expose top-level `__version__`.

**What could be added/changed/updated:**
- `__version__ = "0.1.0"` for runtime introspection.
- A `__all__` if anything is re-exported here.

---

## 4. `src/api/`

### `src/api/app.py`
**Currently:** FastAPI app factory. `lifespan` opens a Redis pool from
`Settings().redis_url`, registers it on `app.state`, logs lifecycle.
Includes 5 routers under `/api/v1/ai`. CORS wide-open. `/health`
returns `{"status": "ok"}`. Top-level `app = create_app()` for
`uvicorn src.api.app:app`.

**What could be improved:**
- CORS is `allow_origins=["*"]` — OK for dev, dangerous in prod.
- `app.state.redis` created in `lifespan` but `dependencies.py` lazily
  creates another one if missing — two paths to the same client.
- `/health` doesn't actually check Postgres or Redis.
- No Prometheus `/metrics`, no request-id middleware.

**What could be added/changed/updated:**
- Make CORS env-driven (`ALLOWED_ORIGINS`).
- Add a real `/health` that pings Postgres + Redis.
- Add `/ready` (readiness) and `/live` (liveness) K8s probes.
- Add a request-id middleware.
- Add Sentry init (`sentry_sdk.init(dsn=...)`) here.
- Add GZip middleware for large responses.
- Add TrustedHost middleware for prod.
- Add `slowapi` for per-IP rate limits.

---

### `src/api/dependencies.py`
**Currently:** Three FastAPI deps: `get_redis` (returns or creates
`app.state.redis`), `get_stream_consumer` (wraps redis), and
`get_session_cache` (wraps redis).

**What could be improved:**
- `get_stream_consumer` builds a new `RedisStreamConsumer` per
  request (cheap, but no shared state).
- No `get_db_session` dep — routers call repo methods that fetch their
  own session each time.

**What could be added/changed/updated:**
- Add `get_db_session` (yields an `AsyncSession` and closes it).
- Add a typed `CurrentUser` dep that pulls `user_id` from auth
  middleware.
- Add `get_settings` for endpoints that need config.
- Add `get_redis_pool` returning the underlying `aioredis.Redis` (not
  a wrapper).

---

### `src/api/middleware/__init__.py`
**Currently:** Empty.

**What could be added:**
- Re-exports: `PIISanitizationMiddleware`.

---

### `src/api/middleware/sanitizer.py`
**Currently:** `BaseHTTPMiddleware` that reads the body, calls
`strip_pii` on it, but does **not** actually replace the body — it
just logs when sanitization changed the string. So the body continues
unmodified.

**What could be improved:**
- The middleware is a no-op for the body; it only logs.
- No PII filter on response bodies.
- No PII filter on URL query params or headers.
- No way to enable/disable via env.

**What could be added/changed/updated:**
- Actually rewrite the request body using
  `Request(scope, receive=...)` so downstream code sees the
  sanitized version.
- Sanitize response payloads too (defense in depth).
- Add structured `audit_log` on hits.
- Add a `redact_pii_in_logs` filter on the Python logger.
- Make it env-gated (`PII_SANITIZATION_ENABLED=true`).

---

### `src/api/routers/__init__.py`
**Currently:** Re-exports 5 routers.

**What could be improved:** No issues; clean barrel.

---

### `src/api/routers/events.py`
**Currently:** Three POST endpoints:
- `/events` → push single `ObservationEventPayload` to
  `ai:observations`.
- `/events/batch` → loop and push each.
- `/domain-events` → push to `ai:domain_events`.

All return `{status, message_id}`.

**What could be improved:**
- Batch endpoint pushes events one-by-one (N round-trips); should use a
  pipeline.
- No `X-Idempotency-Key` header support; clients can duplicate.
- No backpressure / 429 if Redis is slow.
- No auth.

**What could be added/changed/updated:**
- Use `redis.pipeline()` for the batch.
- Add idempotency via a Redis `SETNX` keyed on a client-supplied key.
- Add a `?dry_run=true` flag.
- Add an `/events/replay` admin endpoint (dangerous; gate behind auth).
- Validate event counts against `Settings().max_events_per_cycle`.

---

### `src/api/routers/telemetry.py`
**Currently:** WebSocket `/telemetry/ws` accepts JSON, validates it as
`TelemetryEventPayload`, pushes it to the telemetry stream, and
echoes `{status, message_id}` back. Catches `WebSocketDisconnect` and
generic exceptions.

**What could be improved:**
- No client identification (`user_id`); events must carry it.
- No heartbeat beyond the default WS ping.
- No per-user rate limit.
- No backpressure handling if the client is slow.

**What could be added/changed/updated:**
- Read `user_id` from query/header on accept; require it.
- Send a server-initiated ping every 30s.
- Bound the per-connection buffer; drop or close on overflow.
- Add a `/telemetry/replay` HTTP endpoint for catch-up.

---

### `src/api/routers/interventions.py`
**Currently:** Two endpoints:
- WS `/interventions/{user_id}/ws` — registers the socket in
  `_active_connections` for that user, listens for `ping`, replies
  `pong`.
- GET `/interventions/{user_id}/stream` — SSE that only emits
  `{"event":"connected"}` once. **No actual SSE stream of
  interventions is wired up.**

**What could be improved:**
- SSE endpoint is a stub (single connected event, no data flow).
- WS handler accepts any `user_id` in the path with no auth.
- `delivery.deliver_via_sse` exists but is unused.
- No reconnect-token / last-event-id handling on SSE.

**What could be added/changed/updated:**
- Wire the SSE endpoint to an in-memory pubsub queue per user
  (asyncio.Queue), or use Redis pubsub.
- Add a `POST /interventions/{user_id}/send` for server-initiated push
  (used by the act node in real deployments).
- Add JWT auth on both transports.
- Persist "last delivered intervention_id" so SSE can replay missed
  events.

---

### `src/api/routers/agent.py`
**Currently:** Five endpoints under `/agent/sessions/{user_id}`:
- `POST /start` — creates state in Redis SessionCache, returns
  session_id.
- `POST /cycle` — pulls events from cache, runs `compile_ooda_agent`
  each time, persists state.
- `POST /stop` — clears session.
- `GET /state` — returns the cached state.
(No `DELETE` or `GET /sessions` listing.)

**What could be improved:**
- `compile_ooda_agent` is called **per request** — expensive.
- No concurrency lock per user; two simultaneous `/cycle` calls will
  race.
- No persistence of the final intervention delivery (caller has to
  read it from the response).
- `raw_events` are pulled from Redis list with `pop_events`, which
  **destroys** them — there's no way to replay a session.
- No structured error responses.

**What could be added/changed/updated:**
- Cache the compiled agent on `app.state` (lazy, single instance).
- Add a per-user `asyncio.Lock` (or Redis lock) to serialize cycles.
- Make `pop_events` non-destructive (rename to `drain_events` with
  peek mode).
- Add a `GET /agent/sessions/{user_id}/history` returning
  intervention log.
- Add OpenTelemetry spans for each node.

---

### `src/api/routers/concept_graph.py`
**Currently:** Four GET endpoints:
- `/concepts/{id}` — returns concept or 404-ish (`status: not_found`).
- `/concepts/{id}/neighbors?depth=2` — recursive prereq + dependents.
- `/concepts/{id}/prerequisites` — full chain via `get_prerequisite_chain`.
- `/concepts/search?query=...&top_k=5` — generates an OpenAI embedding
  on the fly and does pgvector ANN.

**What could be improved:**
- No POST for graph edits (rely on scripts/build_concept_graph.py).
- No bulk fetch.
- Search generates an embedding per request; no embedding cache.
- No HNSW index (per migration note).

**What could be added/changed/updated:**
- Add a `POST /concepts` (admin) to upsert nodes/edges.
- Add a `GET /concepts/{id}/learning-path` ordered from foundational.
- Add a `GET /concepts/{id}/videos` joining with `ai_concept_mappings`.
- Cache embeddings in Redis (key by hash of query).

---

## 5. `src/agent/`

### `src/agent/__init__.py`
**Currently:** Empty. Could export the public Agent API.

**What could be added:**
- Re-export `compile_ooda_agent`, `create_initial_state`,
  `build_ooda_graph`.

---

### `src/agent/state.py`
**Currently:** `OODAState(MessagesState)` TypedDict. Adds
user_id, session_id, raw_events, telemetry_window, learner_profile,
concept_state, diagnosed_struggles, engagement_score,
selected_intervention, intervention_candidates, exploration_flag,
intervention_delivered, delivery_channel, cycle_count,
last_cycle_timestamp, should_pause, max_cycles; `messages` is
`Annotated[list, operator.add]`.

**What could be improved:**
- Pydantic-less TypedDict; no runtime validation.
- `_derived_signals` is set in observe but not declared; missing
  declared state.
- No versioned schema for migration.

**What could be added/changed/updated:**
- Add a Pydantic `OODAStateModel` and use LangGraph's `pydantic_state`
  option.
- Add `_derived_signals: dict[str, Any]`.
- Add a `schema_version: int` for safe migrations.

---

### `src/agent/graph.py`
**Currently:** Builds a `StateGraph(OODAState)` with 5 nodes
(observe, orient, decide, act, pause). Edges: START→observe;
observe→(orient|END) via `continue_router`; orient→decide;
decide→(act|pause) via `decide_router`; act→observe; pause→observe.
`_get_checkpointer` tries PostgresSaver, falls back to MemorySaver.
`compile_ooda_agent` runs `checkpointer.setup()` (best-effort).
`create_initial_state` is a pure dict factory.

**What could be improved:**
- `_get_checkpointer` swallows the `asyncio.get_running_loop()`
  check; the PostgresSaver won't be `await`-initialized here.
- `MemorySaver` fallback would lose state across restarts; warn loudly.
- No `interrupt_before` / `interrupt_after` for human-in-the-loop.
- No subgraph composition.

**What could be added/changed/updated:**
- Add `langgraph.checkpoint.redis` as a second fallback (uses the
  existing Redis).
- Add `interrupt_before=["act"]` for "human approves intervention"
  flows.
- Add a `before_agent_callback` for Sentry breadcrumbs.
- Add a build flag to choose checkpointer.
- Add cycle-level metrics export.

---

### `src/agent/nodes/__init__.py`
**Currently:** Re-exports the 5 nodes.

**What could be improved:** None.

---

### `src/agent/nodes/observe.py`
**Currently:** A module-level singleton `TelemetryAggregator`. Reads
last 100 raw events, aggregates telemetry, computes
`time_on_page=0`, `attempt_velocity=0`, `error_rate`, totals,
`video_engagement=0.5`, `code_iterations`, and pulls smoothness from
the 2m window. Returns a partial state update including
`_derived_signals`.

**What could be improved:**
- The aggregator is **module-level** — shared across all users in one
  process; cross-user data leakage is possible if `clear()` is
  forgotten.
- `time_on_page`, `attempt_velocity`, `video_engagement` are hard-coded
  to 0/0/0.5; not actually computed.
- Single source of telemetry; no fallback to Redis streams.

**What could be added/changed/updated:**
- Move aggregator into per-user factory (DI).
- Compute `time_on_page` from `page_view` events with timestamps.
- Compute `attempt_velocity` as `attempts / elapsed_minutes`.
- Use `TelemetryAggregator` with explicit user_id scoping.

---

### `src/agent/nodes/orient.py`
**Currently:** Loads `LearnerProfileRepo`, `ConceptRepo`,
`BenchmarkRepo` (defensive try/except). Computes `diagnosed_struggles`
from mastery_map <0.5. Computes local engagement + trend. Builds a
sanitized learner summary, calls `get_llm_for_purpose("reasoning")`
for diagnosis. `ORIENT_SYSTEM_PROMPT` is duplicated here (also in
`prompts/orient_prompt.py`).

**What could be improved:**
- System prompt defined both here and in `prompts/orient_prompt.py` —
  drift risk.
- Constructs two `BenchmarkRepo` instances (lines 41 and 64) — one
  unused.
- `_compute_engagement_score` ignores `attempt_velocity`,
  `telemetry_smoothness`, `video_engagement` even though they exist
  in `_derived_signals`.
- Silent `except Exception` for DB load — will hide real errors in
  prod.

**What could be added/changed/updated:**
- Delete the inline `ORIENT_SYSTEM_PROMPT`, import from prompts.
- Remove the dead second `BenchmarkRepo()`.
- Use the rich derived signals in the engagement formula.
- Add structured logging (structlog) with cycle_id.
- Add a typed LLM response parser (Pydantic schema, structured output).

---

### `src/agent/nodes/decide.py`
**Currently:** Two helpers (`_segment_learner`, `decide_router`) and
`decide_node`. Asks the LLM for JSON decision, falls back to default
on parse error. Iterates 5 candidate intervention types, calls
`WisdomRepo.get_or_create` for each, draws Thompson samples
(`np.random.beta`), sorts, picks best. Exploration flag if
`total_trials<10`. The `DECIDE_SYSTEM_PROMPT` is duplicated
(here + in `prompts/decide_prompt.py`).

**What could be improved:**
- 5 hard-coded candidate types — should come from a config /
  catalog.
- The `intervention_type` chosen by the LLM is **overridden** by the
  Thompson-sampled best; the LLM is decorative.
- `np.random.beta` uses global RNG — not seeded.
- Prompt duplication.
- `decide_router` only checks `should_pause`; never returns "stop".

**What could be added/changed/updated:**
- Read candidate types from a registry / config.
- Let the LLM's choice act as a **prior** weighted into the
  Thompson sample.
- Use `default_rng(seed)` for reproducibility.
- Deduplicate prompts.
- Add contextual bandit features (time of day, prior success on
  neighboring concepts).

---

### `src/agent/nodes/act.py`
**Currently:** Templates for 6 intervention types (concept_explanation,
video_recommendation, prerequisite_nudge, challenge_hint,
encouragement, revision_prompt). Builds an intervention dict with
`content`, `display`, `metadata`, `delivered_at`. Persists to
`InterventionRepo` and `LearnerProfileRepo` (defensive try/except).
Increments `cycle_count`, returns delivery channel = `websocket`.

**What could be improved:**
- `_build_intervention_content` uses hard-coded placeholder values
  (`timestamp="3:42"`, `analogy="building blocks..."`) — never
  dynamic.
- No actual call to the LLM for personalized content despite having
  templates that *look* like prompt output.
- Increments `cycle_count` here — also incremented by other
  paths?
- The display `auto_dismiss_seconds` is hard-coded.

**What could be added/changed/updated:**
- Replace the hard-coded format values with real concept data
  (look up `concept_repo.get`) and an LLM call when an API key is
  available.
- Add a "scaffold" branch: when no LLM, use the template; when LLM is
  available, ask for a personalized body.
- Add per-intervention-type cooldown from `Settings()`.
- Use a per-user cooldown Redis key (already in SessionCache).

---

### `src/agent/nodes/pause.py`
**Currently:** Computes exponential cooldown
`min(2**(cycle_count//3), 30)` minutes. Returns `should_pause=True`
if last cycle <60s. Adds a PAUSE message.

**What could be improved:**
- Cooldown formula isn't actually used (just logged).
- No re-engagement logic (what to do AFTER pause expires).
- The 60s threshold is hard-coded.

**What could be added/changed/updated:**
- Use Redis `cooldown` key (SessionCache.is_cooldown_active).
- Add a `_should_offer_break` (different from cooldown) for
  long sessions.
- Surface the cooldown to the UI.

---

### `src/agent/prompts/__init__.py`
**Currently:** Empty.

**What could be added:** Re-export prompt constants.

---

### `src/agent/prompts/orient_prompt.py`
**Currently:** Defines `ORIENT_SYSTEM_PROMPT` for diagnosis.

**What could be improved:** Duplicate of the one in
`nodes/orient.py`.

**What could be added/changed/updated:**
- Add a `USER_PROMPT_TEMPLATE` for per-call injection.
- Add versioning (`ORIENT_SYSTEM_PROMPT_V2`).
- Add a few-shot example block.

---

### `src/agent/prompts/decide_prompt.py`
**Currently:** Defines `DECIDE_SYSTEM_PROMPT` enumerating 7
intervention types and asking for a JSON response.

**What could be improved:** Duplicate of the one in
`nodes/decide.py`.

**What could be added/changed/updated:**
- Move JSON schema to Pydantic and use
  `llm.with_structured_output(...)`.
- Add a `USER_PROMPT_TEMPLATE` for learner + state injection.

---

### `src/agent/prompts/generate_prompt.py`
**Currently:** `CHALLENGE_GENERATION_PROMPT` for MCQ/code and
`CRITIQUE_PROMPT` for QA review.

**What could be improved:** Not imported anywhere — the actual
generator in `src/intervention/generator.py` has its own copies.

**What could be added/changed/updated:**
- Make this the single source of truth (delete duplicates in
  generator.py).
- Add a "few-shot examples" block.
- Add per-domain templates (kinematics, dynamics, control).

---

### `src/agent/prompts/explain_prompt.py`
**Currently:** `EXPLANATION_SYSTEM_PROMPT` and
`EXPLANATION_USER_PROMPT`. **Not imported anywhere** — the generator
in `src/intervention/generator.py` inlines a shorter prompt.

**What could be added/changed/updated:**
- Use these in the generator.
- Add LaTeX-rendering instructions and a worked-example template.
- Add a "common misconceptions" appendix.

---

### `src/agent/tools/__init__.py`
**Currently:** Empty.

**What could be added:** Re-export the 6 tool modules.

---

### `src/agent/tools/concept_tools.py`
**Currently:** 3 LangChain `@tool`s: `query_concept_graph`,
`search_similar_concepts`, `get_prerequisite_chain_tool`.

**What could be improved:**
- Not bound to an LLM anywhere (the OODA graph doesn't pass them in
  `bind_tools`).
- Each call opens a new repo instance.

**What could be added/changed/updated:**
- Add `bind_tools(TOOLS)` in `compile_ooda_agent`.
- Add a `find_learning_path_tool` (ordered from fundamentals).
- Add a `get_popular_videos_for_concept_tool`.

---

### `src/agent/tools/delivery_tools.py`
**Currently:** Module-level dict `_active_websockets` (per-user
sockets list). Two tools: `deliver_intervention`,
`log_intervention`. Also two module functions to register/unregister.

**What could be improved:**
- Module-level dict has the same multi-user / multi-process pitfalls.
- `log_intervention` is already what `InterventionRepo` does; the
  tool is redundant with `act_node` which calls the same repo.
- A different module (`src/intervention/delivery.py`) **also** keeps
  its own `_active_connections` dict — two registries of WS clients.

**What could be added/changed/updated:**
- Unify into a single `ConnectionManager` in
  `src/intervention/delivery.py`.
- Use Redis pubsub for cross-process delivery.

---

### `src/agent/tools/generation_tools.py`
**Currently:** 3 tools: `generate_explanation`, `generate_challenge_tool`,
`recommend_video`. Each just wraps a function from
`src.intervention.*`.

**What could be improved:** Same — not bound to the agent.

**What could be added/changed/updated:**
- Add `bind_tools` integration.
- Add a `generate_revision_set_tool`.
- Add streaming versions of the generation calls.

---

### `src/agent/tools/logging_tools.py`
**Currently:** A single `log_agent_event` tool that just calls
`logger.info`.

**What could be improved:** No structured fields, no PII redaction.

**What could be added/changed/updated:**
- Use structlog with `cycle_id`, `user_id`, `node` fields.
- Send to both stdout and a Redis list for the admin UI.

---

### `src/agent/tools/mastery_tools.py`
**Currently:** `query_mastery(user, concept)`, `get_prior_baseline(user)`.

**What could be improved:** Calls `LearnerProfileRepo` directly; no
caching.

**What could be added/changed/updated:**
- Add a Redis cache (TTL 60s) keyed on `mastery:{user}:{concept}`.
- Add a `get_all_mastery_tool`.

---

### `src/agent/tools/wisdom_tools.py`
**Currently:** `query_wisdom`, `query_population_benchmark`.

**What could be improved:** No caching; no batching.

**What could be added/changed/updated:**
- Cache the wisdom row for `Settings().wisdom_cache_ttl`.
- Add a `query_top_k_interventions(concept_id, k)` returning sorted
  candidates.

---

## 6. `src/concept_graph/`

### `src/concept_graph/__init__.py`
**Currently:** Empty.

**What could be added:** Re-export `build_concept_graph`,
`ConceptNode`, etc.

---

### `src/concept_graph/builder.py`
**Currently:** `build_concept_graph(video_titles)` — LLM-extracts
concepts, embeds them, dedupes (cosine ≥0.92), bulk-inserts concepts
into Postgres, then pairwise LLM-calls to infer prerequisite edges.
Also defines `CONCEPT_EXTRACTION_PROMPT` and `EDGE_INFERENCE_PROMPT`.

**What could be improved:**
- O(N²) LLM calls for edge inference — will blow up at scale.
- Edge inference prompt is the same pair queried both ways
  (wasteful).
- No batching of embeddings.
- No re-build of mappings; only nodes + edges.

**What could be added/changed/updated:**
- Use one LLM call that returns a graph in one shot (within context
  size), or chunk by topological order.
- Add embeddings of *edges* for retrieval.
- Add `build_concept_mappings(videos, concepts)` to populate
  `ai_concept_mappings`.
- Add a `--from-youtube` flag in the script.

---

### `src/concept_graph/models.py`
**Currently:** Pydantic models `ConceptNode`, `ConceptEdge`,
`ConceptMapping`, `ConceptGraph`, `ExtractedConcept`.

**What could be improved:** No validators on `difficulty` (0..1) or
`weight` (>0).

**What could be added/changed/updated:**
- Add `Field(ge=0, le=1)` on difficulty.
- Add `model_validator` to ensure `from_id != to_id`.

---

### `src/concept_graph/embeddings.py`
**Currently:** Thin wrappers over `OpenAIEmbeddings` for single
embedding, batch, and `cosine_similarity` (numpy).

**What could be improved:**
- Hard-coded to OpenAI; no fallback.
- `cosine_similarity` re-imports numpy on every call (minor).

**What could be added/changed/updated:**
- Add a provider switch (OpenAI default, with HuggingFace/local
  fallback).
- Use a connection pool for the OpenAI client.
- Add a `normalize` option so L2-normalized vectors can use dot
  product.

---

### `src/concept_graph/queries.py`
**Currently:** Three async helpers: `get_prerequisite_chain` (recursive
CTE), `get_concept_learning_path` (reverses the chain),
`find_unmastered_prerequisites` (filters by `mastered_concepts`).

**What could be improved:** No batch fetch; no cache.

**What could be added/changed/updated:**
- Add `get_subgraph_for_concepts(ids, hops=2)` for bulk operations.
- Add a `redis_cache` layer.
- Add `get_concept_count()` for `/stats`.

---

## 7. `src/config/`

### `src/config/__init__.py`
**Currently:** Empty.

**What could be added:** Re-export `get_settings`.

---

### `src/config/settings.py`
**Currently:** Pydantic `BaseSettings` with all knobs (DB, Redis, 3
LLM keys, provider list, models, rate limit, sentry, log level, three
stream names, intervention cooldown, max events, wisdom TTL).
`get_settings()` is `lru_cache`d.

**What could be improved:**
- `max_events_per_cycle=100` is used in observe (`-100:])` but not
  centrally enforced.
- No per-provider rate limit (single `LLM_RATE_LIMIT_RPM`).
- No model temperature knob.
- `redis_stream_*` are hard-coded.

**What could be added/changed/updated:**
- Add `llm_temperature`, `llm_max_retries`, `llm_request_timeout_s`.
- Per-provider rate limits (`llm_rate_limit_rpm_per_provider`).
- `circuit_breaker_*` knobs.
- Validate `database_url` is `asyncpg` on startup.
- Validate `redis_url` parseable.

---

### `src/config/llm_config.py`
**Currently:** Hard-coded dict with 5 roles: primary, reasoning,
fallback_1, fallback_2, embedding. Provider restricted to
`openai | anthropic | google_genai`.

**What could be improved:** Not env-driven — overrides from
`Settings()` are ignored at this layer.

**What could be added/changed/updated:**
- Read provider/model from `Settings()` instead of hard-coding.
- Add `mistral`, `cohere`, `local` (Ollama) to the Literal.
- Add cost-per-1k-tokens per model for budgeting.
- Add a "purpose → config" indirection that supports A/B testing.

---

## 8. `src/db/`

### `src/db/__init__.py`
**Currently:** Empty.

**What could be added:** Re-export `get_engine`, `get_session`,
`Base`.

---

### `src/db/engine.py`
**Currently:** Async SQLAlchemy. `Base(DeclarativeBase)`,
`get_engine()` (singleton, pool_size=10, max_overflow=20),
`get_session_factory()`, `get_session()`, `close_engine()`.

**What could be improved:**
- `pool_size=10, max_overflow=20` is aggressive; consider
  `pool_pre_ping=True` to survive DB restarts.
- No `pool_recycle`.
- No SSL options for managed Postgres.

**What could be added/changed/updated:**
- Add `pool_pre_ping=True`, `pool_recycle=1800`.
- Add `connect_args={"ssl": "require"}` toggle for managed DBs.
- Add a `get_readonly_session` (separate engine pointing at a
  read-replica) for analytics queries.
- Add Prometheus counters for connection-pool usage.

---

### `src/db/models/__init__.py`
**Currently:** Re-exports the 7 models.

**What could be improved:** Could expose a `ALL_MODELS` list for
Alembic autogenerate.

---

### `src/db/models/ai_learner_profile.py`
**Currently:** SQLAlchemy model. `user_id` is a FK to
`ab6_user_data.user_details.id` (external). JSON columns for
mastery_map, learning_style, engagement_history, intervention_log,
struggle_patterns, prior_baseline. Uses `Mapped[]` type hints.

**What could be improved:**
- `Mapped` used but rest of the column is the classic `Column(...)`
  style — mixed.
- `datetime.utcnow` is deprecated in Py 3.12+.

**What could be added/changed/updated:**
- Migrate to fully typed `mapped_column(...)` style.
- Use `datetime.now(UTC)` instead of `utcnow`.
- Add a back-reference relationship to the external user table once
  the schema is in place.
- Add a JSON schema validator on `mastery_map` (pydantic v2 model).

---

### `src/db/models/ai_intervention_log.py`
**Currently:** Columns: id, user_id, session_id, cycle_number,
diagnosed_concepts (ARRAY), engagement_score, intervention_type (50),
intervention_data (JSON), was_exploration, arm_id, next_challenge_score,
score_delta, effectiveness_label (20), created_at.

**What could be improved:**
- `effectiveness_label` is a free string; should be enum or
  CHECK constraint.
- No index on `created_at` (for time-range queries).
- No index on `(user_id, created_at)` composite.

**What could be added/changed/updated:**
- Add `CHECK (effectiveness_label IN ('positive','neutral','negative'))`.
- Add composite index `(user_id, created_at DESC)`.
- Add `delivered_at` to distinguish created vs delivered.
- Add a `client_id` for multi-tenant deployments.

---

### `src/db/models/ai_wisdom_store.py`
**Currently:** Columns: id, concept_id, intervention_type,
profile_segment, alpha, beta_param, total_trials, success_rate,
insight_text, updated_at.

**What could be improved:** No CHECK on alpha/beta > 0; no index on
`(concept_id, intervention_type)`.

**What could be added/changed/updated:**
- `CHECK (alpha > 0 AND beta_param > 0)`.
- Composite index for the hot read path.
- Add a `version` column for optimistic locking.

---

### `src/db/models/ai_concept.py`
**Currently:** `id` is a string PK (e.g. dot-notation concept id);
`embedding` is `Vector(1536)`. `source_type`/`source_id` link back to
the source material.

**What could be improved:**
- `Vector(1536)` is hard-coded; if embedding model changes dim, you
  must migrate.
- No HNSW index (in migration).

**What could be added/changed/updated:**
- Make dim a setting; or store as `vector` (no dim) and check at
  insert.
- Add HNSW index in a follow-up migration.
- Add `last_used_at` for popularity-based eviction.

---

### `src/db/models/ai_concept_edge.py`
**Currently:** Composite unique on `(from, to, edge_type)`. Source
default "auto".

**What could be improved:** No CHECK that `from != to`.

**What could be added/changed/updated:**
- Add `CHECK (from_concept_id != to_concept_id)`.
- Add an index on `to_concept_id` for reverse traversal.
- Add a `confidence` column (currently weight doubles as confidence).

---

### `src/db/models/ai_concept_mapping.py`
**Currently:** Composite unique on `(concept, entity_type, entity_id)`.
Relevance 0..1.

**What could be improved:** No index on `(entity_type, entity_id)` for
reverse lookup.

**What could be added/changed/updated:**
- Reverse index.
- Add a `created_at` and an `expires_at` (TTL on stale mappings).

---

### `src/db/models/ai_population_benchmark.py`
**Currently:** One row per `concept_id` (unique). Stats: avg, median,
p25/p75 mastery, avg attempts, avg time-to-master, common prereq
gaps (ARRAY), sample_size, updated_at.

**What could be improved:** No partial unique guard; no index on
`updated_at` for "stale benchmark" detection.

**What could be added/changed/updated:**
- Add an `is_stale` boolean computed on read.
- Add a `version` for optimistic locking.
- Add a `domain` denormalized column for cross-domain queries.

---

### `src/db/repositories/__init__.py`
**Currently:** Re-exports 5 repos.

---

### `src/db/repositories/learner_profile_repo.py`
**Currently:** CRUD for `AILearnerProfile`. Methods: `get`,
`upsert_mastery`, `update_struggle_patterns`,
`append_intervention`. Defensive `if profile is None: return` (silent).

**What could be improved:**
- Magic 100-record cap on intervention log.
- Silent no-op on missing profile.
- `get` doesn't use `populate_existing` (could be slow after updates).
- `mastery_map` is mutated as a dict-of-dict; no schema enforcement.

**What could be added/changed/updated:**
- Add `bulk_upsert_mastery` and `get_mastery_batch`.
- Add a Pydantic schema for `mastery_map[concept_id]` (`{mastery,
  attempts, last_attempt_at, last_error}`).
- Raise on missing profile in `update_*` (or accept and create).
- Move the 100-cap to a setting.

---

### `src/db/repositories/intervention_repo.py`
**Currently:** `create`, `update_effectiveness`, `get_recent`.

**What could be improved:** No `get_by_id`, no `count_by_user`,
no `get_by_type`.

**What could be added/changed/updated:**
- Add `get_by_id`, `get_by_user_and_type`, `count_recent`.
- Add `get_effectiveness_summary(user_id)` for the admin UI.
- Add `list_pending_effectiveness` to drive the effectiveness loop.

---

### `src/db/repositories/wisdom_repo.py`
**Currently:** `get_or_create`, `update_beta`, `get_by_concept`.

**What could be improved:**
- `get_or_create` races under high concurrency (no UPSERT).
- `get_by_concept` returns `list[AIWisdomStore]` — could be large;
  no pagination.

**What could be added/changed/updated:**
- Use `INSERT ... ON CONFLICT DO NOTHING RETURNING` to avoid the
  race.
- Add `get_by_concept_and_type`, `get_top_k_for_concept`.
- Add `bulk_update_betas(outcomes)` to amortize the round trips.

---

### `src/db/repositories/concept_repo.py`
**Currently:** `get`, `get_with_neighbors` (two recursive CTEs +
N+1 SELECTs for prereqs/dependents), `search_similar` (pgvector
ANN), `get_prerequisite_chain`.

**What could be improved:**
- `get_with_neighbors` does an N+1 to hydrate concept rows.
- `search_similar` does not use the new HNSW index.
- Embedding passed as text-cast `::vector` — fragile.

**What could be added/changed/updated:**
- Use a single CTE that joins concept names.
- Use `embedding <=> $1` operator with proper binary binding.
- Add `get_by_domain(domain)`.
- Add `create_or_update(concept)` for the builder.

---

### `src/db/repositories/benchmark_repo.py`
**Currently:** `get`, `upsert`.

**What could be improved:** No `list_all`, no `get_stale`, no
incremental recompute.

**What could be added/changed/updated:**
- Add `list_all`, `get_stale(updated_before=...)`.
- Add an incremental upsert (only the changed concept).

---

## 9. `src/ingestion/`

### `src/ingestion/__init__.py`
**Currently:** Empty.

**What could be added:** Re-export `RedisStreamConsumer`, schemas.

---

### `src/ingestion/schemas.py`
**Currently:** Three Pydantic models + a `BatchObservationPayload` +
`STREAMS` map. The `event_type` regex allows 7 values.

**What could be improved:**
- `event_type` enum is a regex, not an `Enum`.
- `action` is free text.
- `STREAMS` is duplicated with `Settings().redis_stream_*`.

**What could be added/changed/updated:**
- Convert to `Enum`.
- Source of truth for streams = `Settings()`.
- Add a `client_event_id` for idempotency.

---

### `src/ingestion/aggregator.py`
**Currently:** `TelemetryAggregator` with three windows (30s, 2m, 5m)
keyed by `user_id`. Stores raw telemetry dicts and computes
smoothness/imu_samples/joint_samples. `compute_engagement` returns a
single number using the 2m smoothness.

**What could be improved:**
- No time-based eviction — the `defaultdict` grows forever.
- No thread-safety (but asyncio is single-threaded per loop, OK).
- Smoothness computed over a flat list of mixed joints (single vector
  across all joints).

**What could be added/changed/updated:**
- Cap each window to N items or evict by timestamp.
- Compute per-joint smoothness.
- Add a `merge_across_users_for_global_stats`.

---

### `src/ingestion/consumer.py`
**Currently:** `RedisStreamConsumer` wrapping redis.asyncio.
Push: observations, telemetry, domain events. Read: xreadgroup with
auto-group-create. Ack: xack. Maxlen 10k/5k/10k.

**What could be improved:**
- `maxlen=~` is approximate; messages can be lost on the read side
  with consumer groups.
- No retry on transient Redis errors.
- `read_events` decodes bytes manually (mixed with str when
  `decode_responses=True` is set on app side).

**What could be added/changed/updated:**
- Use `decode_responses=True` consistently.
- Add `retry_on_error` with exponential backoff.
- Add a `pending_count` admin endpoint.
- Switch to `decode_responses` and stop the manual decode.

---

### `src/ingestion/worker.py`
**Currently:** ARQ `WorkerSettings` with three near-empty
`process_*` functions that just log the event. Uses
`RedisSettings.from_dsn`, `keep_result=60`, `poll_delay=0.5`,
`max_tasks=10`.

**What could be improved:**
- The workers are stubs; they don't write to the DB or trigger OODA
  cycles.
- No retry / dead-letter handling.
- No healthcheck / metrics endpoint.

**What could be added/changed/updated:**
- Wire `process_observation` to enqueue an OODA cycle for the user.
- Wire `process_telemetry` to push to `TelemetryAggregator`.
- Add a `process_intervention_outcome` for delayed effectiveness.
- Add `max_tries=3`, `retry_backoff=True`.
- Expose ARQ's built-in `/health` if available.

---

## 10. `src/intervention/`

### `src/intervention/__init__.py`
**Currently:** Empty.

---

### `src/intervention/selector.py`
**Currently:** `select_intervention` does the Thompson sampling and
returns the best candidate; also a `segment_learner` helper and
`find_best_video_for_concept` (joins `ai_concept_mappings` to
`ab6_data.challenge_videos`).

**What could be improved:**
- Duplicates `_segment_learner` logic from `decide.py`.
- `find_best_video_for_concept` opens its own session and doesn't
  close it cleanly (uses `await session.close()` after a query — OK,
  but pattern is fragile).
- No support for `challenge_swap` or `revision_prompt` candidates.

**What could be added/changed/updated:**
- Move `_segment_learner` here, import from there everywhere.
- Add `find_best_challenge_for_concept`.
- Add a UCB1 variant alongside Thompson for A/B testing.

---

### `src/intervention/generator.py`
**Currently:** `generate_challenge` (LLM + critique + regenerate if
quality<0.7; calibrates difficulty). `generate_concept_explanation`
(brief inline prompt). The challenge prompt and critique prompt are
duplicated with `src/agent/prompts/generate_prompt.py`.

**What could be improved:**
- Prompt duplication.
- `calibrate_difficulty` is fine but averages a 0..1 LLM value with
  concept difficulty (also 0..1) — naive.
- No safety filter on generated content (could produce code with
  vulnerabilities for a code challenge).
- No max-token cap on LLM call.

**What could be added/changed/updated:**
- Use a Pydantic schema + `with_structured_output`.
- Use the prompts from `src/agent/prompts/generate_prompt.py`.
- Add per-domain few-shot examples.
- Add a static-analysis pass on generated code challenges.

---

### `src/intervention/delivery.py`
**Currently:** Module-level `_active_connections` dict. Three async
functions: `connect_websocket`, `disconnect_websocket`,
`deliver_via_websocket`, `deliver_via_sse`, `deliver_intervention`.

**What could be improved:**
- Duplicates the connection registry from
  `src/agent/tools/delivery_tools.py`.
- `deliver_via_sse` returns a dict, not an `EventSourceResponse`.
- `deliver_intervention` only handles `channel=websocket`; else
  returns False.
- No delivery receipt / ack.

**What could be added/changed/updated:**
- Consolidate into a `ConnectionManager` class.
- Add Redis pubsub for cross-process delivery.
- Add a `deliver_with_retry`.
- Add a delivery-status table / log.

---

### `src/intervention/effectiveness.py`
**Currently:** `measure_effectiveness` (computes delta, label, updates
intervention + struggle_patterns + wisdom). `calibrate_difficulty`.

**What could be improved:**
- Threshold of ±0.1 is hard-coded.
- "Effectiveness" is a noisy single-number signal; no smoothing.
- No A/B bucket tracking for exploration.

**What could be added/changed/updated:**
- Make thresholds configurable.
- Add a Bayesian smoothing factor.
- Add a `was_exploration` flag pass-through (it's set in act_node but
  effectiveness doesn't differentiate).

---

## 11. `src/llm/`

### `src/llm/__init__.py`
**Currently:** Empty.

**What could be added:** Re-export `get_llm_for_purpose`,
`llm_call`, `get_embedding_model`.

---

### `src/llm/provider.py`
**Currently:** Builds LangChain chat models from `LLM_CONFIG`. Has
`get_llm`, `get_llm_with_fallback` (tries primary → fallback_1 →
fallback_2, logs warning on each failure), `get_llm_for_purpose`
(just delegates), `get_embedding_model` (always OpenAI), `llm_call`
(high-level helper).

**What could be improved:**
- `init_chat_model` is called **on every call** — no caching.
- `get_llm_with_fallback` calls `init_chat_model` per provider in a
  loop, but if the **import** of the provider SDK fails (e.g.
  `langchain-google-genai` not installed), the loop will repeat the
  same ImportError 3×.
- `RateLimiter` is module-level with `rpm=100`; not per-purpose.
- `OpenAIEmbeddings` is hard-coded.

**What could be added/changed/updated:**
- Cache models by `_build_model_key` (LRU).
- Distinguish "provider SDK not installed" from "transient failure"
  and short-circuit the loop.
- Add Azure / Bedrock / local-Ollama providers.
- Add streaming + structured-output helpers.
- Add token usage tracking + Sentry breadcrumb.

---

### `src/llm/rate_limiter.py`
**Currently:** Simple sliding-window counter with per-provider lock.

**What could be improved:**
- The lock + sleep pattern means two concurrent tasks will both sleep
  for the same duration.
- No token-based limiting, only request-based.
- No priority queue.

**What could be added/changed/updated:**
- Token-bucket or leaky-bucket algorithm.
- Per-(provider, model) buckets.
- Surface metrics (`rate_limited_total`).
- Allow bursting above RPM for short periods.

---

### `src/llm/sanitizer.py`
**Currently:** 4 regex patterns (email, phone, card, "Firstname
Lastname"). `strip_pii(text)`, `sanitize_observation_event(dict)`,
`sanitize_learner_summary(dict)`.

**What could be improved:**
- The "[NAME]" regex will over-redact normal text like
  "Inverse Kinematics".
- "Card" is `\d{16,19}` — false positives on long numeric IDs.
- No international phone / SSN / address support.
- The functions mutate a copy; the original is left untouched.
- `sanitize_observation_event.metadata` is converted to `str` and
  re-wrapped in `{"metadata": "<str>"}` — drops structure.

**What could be added/changed/updated:**
- Use `scrubadub`, `presidio-analyzer`, or a small ML model.
- Add structured-field sanitization (per-key redaction).
- Add a PII-detection confidence score.
- Add unit tests for edge cases (emails in URLs, phone in formatted
  strings).

---

## 12. `src/memory/`

### `src/memory/__init__.py`
**Currently:** Empty.

---

### `src/memory/personal.py`
**Currently:** `PersonalMemoryService` with: `get_profile`,
`update_mastery`, `record_struggle`, `get_intervention_history`,
`update_engagement`. Touches `learner_profile_repo` and
`intervention_repo`.

**What could be improved:**
- `update_engagement` reaches into the repo's private `_get_session`
  and commits directly — coupling.
- No TTL or compaction on engagement_history (capped at 100).
- No batch update.

**What could be added/changed/updated:**
- Add a `record_batch(events)` to amortize writes.
- Add a `compute_engagement_velocity(user)` (trend slope).
- Add a `get_struggle_hotspots(user, n=5)`.

---

### `src/memory/global_wisdom.py`
**Currently:** `GlobalWisdomService` with `get_intervention_stats`,
`record_outcome`, `get_best_intervention`.

**What could be improved:**
- `get_best_intervention` requires `total_trials >= 3` — arbitrary
  threshold.
- `record_outcome` doesn't de-dup or batch.

**What could be added/changed/updated:**
- Add a confidence-interval output (Bayes posterior).
- Add a `get_top_k_interventions(concept, k=3)`.
- Add a TTL-based eviction for old/never-tried rows.

---

### `src/memory/population_benchmarks.py`
**Currently:** `PopulationBenchmarkService.recalculate_all` runs a
CTE to compute per-concept stats from `ai_learner_profiles` and
upserts the benchmark table.

**What could be improved:**
- Loads **all** profiles in one query — fine for small data, will
  OOM on millions of users.
- No incremental recompute.
- `await session.close()` after the loop, but the repo also uses
  `get_session()` internally — could double-close.

**What could be added/changed/updated:**
- Add a `recalculate_for_concept(concept_id)` (delta-friendly).
- Add a scheduled job (cron / arq cron).
- Add a "stale benchmark" view.

---

### `src/memory/session_cache.py`
**Currently:** Redis-backed session cache: `get_state`, `set_state`
(JSON), `push_event`, `pop_events` (destructive, lpush/ltrim to
100), `set_cooldown`, `is_cooldown_active`, `clear_session`.

**What could be improved:**
- `pop_events` **destroys** events on read — there is no replay.
- `rpop` in a loop is N round-trips.
- No type safety on the JSON payload.
- No transaction (multi/exec) when pushing multiple keys.

**What could be added/changed/updated:**
- Use `LRANGE` then `LTRIM` for atomic drain, or use Redis Streams
  (XADD + XREADGROUP).
- Add a `peek_events`.
- Add schema validation on the way in (using `ObservationEventPayload`).

---

## 13. `src/shared/`

### `src/shared/__init__.py`
**Currently:** Empty.

---

### `src/shared/events.py`
**Currently:** Four Pydantic models: `ObservationEvent`,
`TelemetryEvent`, `DomainEvent`, `InterventionEvent`.

**What could be improved:**
- `timestamp` is a free string; should be `datetime`.
- No `event_id` for dedupe.
- Duplicated in `src/ingestion/schemas.py` with stricter validation
  (regex on `event_type`).

**What could be added/changed/updated:**
- Convert `timestamp` to `datetime`.
- Add `event_id: uuid.UUID`.
- Make this the single source of truth; have `ingestion/schemas.py`
  import from here.

---

### `src/shared/exceptions.py`
**Currently:** A 12-class hierarchy rooted at `AB6AIError`. Reasonable
coverage: LLM, sanitization, concept-graph, intervention, agent,
memory, ingestion, challenge generation.

**What could be improved:**
- No `__str__` overrides; no structured fields.
- Some leaves are never raised (e.g. `LLMRateLimitError`).

**What could be added/changed/updated:**
- Add `code: str` + `http_status: int` on each.
- Add a `to_dict()` for JSON responses.
- Raise `LLMRateLimitError` from `RateLimiter` instead of sleeping
  silently.

---

### `src/shared/telemetry_math.py`
**Currently:** `compute_jerk`, `compute_smoothness` (1/log(1+jerk)),
`compute_angular_velocity`, `compute_engagement_from_telemetry`
(weighted: 0.3*smooth + 0.3*completion − 0.2*err + 0.2*min(att/10,1)).

**What could be improved:**
- Weights are hard-coded.
- Smoothness is in `[0,1]`; engagement formula assumes that.
- `dt=0.01` is hard-coded — 100 Hz assumption; needs to be a
  parameter.

**What could be added/changed/updated:**
- Move weights into `Settings()`.
- Add a `compute_spectral_arclength` (a common robotics smoothness
  metric).
- Add unit tests for each function.

---

## 14. `src/youtube_agent/`

### `src/youtube_agent/__init__.py`
**Currently:** Empty.

---

### `src/youtube_agent/schemas.py`
**Currently:** Five Pydantic models: `YouTubeEvent`, `WatchSession`,
`SegmentAnalysis`, `AnalysisResult`, `AgentState`.

**What could be improved:** `AgentState` and `AnalysisResult` overlap.

**What could be added/changed/updated:**
- Split `AgentState` from `AnalysisResult` clearly.
- Add a `Session` model that holds the player config separately.

---

### `src/youtube_agent/analytics.py`
**Currently:** `YouTubeAnalytics(segment_duration=10)`. Builds
`SegmentAnalysis` list, processes events (`play`, `pause`, `seek`,
`speed_change`, `tab_switch`, `timeupdate`), computes struggle
scores, engagement (1 − mean struggle), and recommendations.

**What could be improved:**
- `seg_idx = lambda t: ...` recomputes `segments[-1].end_time /
  len(segments)` for every event — O(N²).
- Skipped-segment marking is exclusive of `to_idx` (off-by-one).
- `tab_switch_count` is treated as positive signal for struggle but a
  user returning to the tab could also be high engagement.
- `SegmentAnalysis` has no `concept_id` linkage.

**What could be added/changed/updated:**
- Precompute the segment boundary once.
- Map segments to concepts via `ai_concept_mappings` if video is
  linked.
- Use the YouTube transcript API to label segments with the
  actually-spoken text.
- Add a streaming interface for real-time updates.

---

### `src/youtube_agent/agent.py`
**Currently:** `YouTubeAgent.run_pipeline` runs 7 phases:
`prior_info → observe → analyze → inference → interpret →
intelligence → feedback_loop`. Uses `YouTubeAnalytics` and
`WEAKNESS_KEYWORDS` (4 areas). Builds
`inferred_weaknesses`, `interpreted_context`,
`intelligence_recommendations`, and a `narrative`.

**What could be improved:**
- All phase methods are sync (`def`) but called from the FastAPI
  `async def finish_session` — the whole thing blocks the event loop
  on a large session.
- `prior_profile` is built from in-memory state; not persisted.
- `_inference` has a hard-coded `seg_text_map` with only 5 entries;
  falls back to `section_{i}` beyond.
- `narrative` is a f-string; not LLM-generated.
- The agent's "state" lives entirely on the request-scoped
  `AgentState` pydantic object; not in `SessionCache`.

**What could be added/changed/updated:**
- Make each phase `async` and add cancellation.
- Persist `AgentState` to Redis via `SessionCache`.
- Use the LLM to generate the narrative (not a template).
- Add a back-reference to the OODA agent's "intervention" delivery
  (push to WebSocket).
- Add a `confidence` per inferred weakness using a Bayesian model.

---

## 15. `scripts/`

### `scripts/benchmark_updater.py`
**Currently:** 21-line script that calls
`PopulationBenchmarkService.recalculate_all()` and logs the result.

**What could be improved:**
- No CLI args, no error handling, no dry-run.
- Imports `asyncio` but the function isn't using `nest_asyncio` if
  run inside Jupyter.

**What could be added/changed/updated:**
- Add `--since YYYY-MM-DD` (incremental).
- Add `--concepts` (comma list).
- Add `--dry-run` (print SQL).
- Add structured logging.

---

### `scripts/build_concept_graph.py`
**Currently:** 48-line script. Tries to fetch video titles from
`ab6_data.challenge_videos`; falls back to 3 hard-coded sample rows.
Calls `build_concept_graph(titles, session)`.

**What could be improved:**
- External schema `ab6_data` may not exist in the AI repo.
- 3 hard-coded rows is a poor fallback for prod.
- No concurrency / no batching of edge inference.

**What could be added/changed/updated:**
- Add `--from-csv path/to/titles.csv` and `--from-youtube-api`.
- Add a `--limit N` for incremental runs.
- Persist a build run log.
- Add a pre-flight check for `ab6_data` schema.

---

### `scripts/seed_wisdom.py`
**Currently:** Seeds 6 wisdom rows (DH params, IK Jacobian,
Newton-Euler, general encouragement) with hand-picked alpha/beta.

**What could be improved:**
- Hard-coded list — no way to seed per environment.
- Inserts via raw SQL; could use `WisdomRepo`.
- `trials` is `alpha + beta - 2` which assumes 1 success counted as
  alpha, 1 failure as beta — odd.

**What could be added/changed/updated:**
- Read seeds from a YAML/JSON file (`--from-file`).
- Use `WisdomRepo.upsert`.
- Document the `alpha`/`beta` convention (successes/failures + prior).

---

## 16. `tests/`

### `tests/conftest.py`
**Currently:** `event_loop` (session-scoped), 3 async fixtures
(`sample_observation_event`, `sample_telemetry_event`,
`sample_learner_profile`).

**What could be improved:**
- `event_loop` session-scope is deprecated in pytest-asyncio 0.23+;
  use `asyncio_mode=auto` (already set) and a fixture loop scope.
- Fixtures are async (`pytest_asyncio.fixture`) but only return
  dicts; could be sync.

**What could be added/changed/updated:**
- Add a `pg_session` fixture (skips if no DB; uses testcontainers
  otherwise).
- Add a `redis_client` fixture with flushdb teardown.
- Add a `wisdom_seeded` fixture.
- Add a `make_user(mastery=..., struggles=...)` factory.

---

### `tests/unit/test_observe.py`
**Currently:** One test (`test_observe_node_basic`) that feeds 3
events and asserts the result has `raw_events`, `telemetry_window`,
`messages`.

**What could be improved:** Only checks structural keys, not the
derived signals.

**What could be added/changed/updated:**
- Assert `error_rate`, `total_attempts`, `code_iteration_count`.
- Test with empty events, all-correct, all-wrong.
- Test the cap at 100 events.

---

### `tests/unit/test_orient.py`
**Currently:** Two tests. One is a stub `assert True`. The other
exercises `_compute_engagement_trend` with empty / single / declining
/ improving histories.

**What could be improved:** The first test is filler.

**What could be added/changed/updated:**
- Replace stub with a real orient_node test (with a mocked repo).
- Test `_compute_engagement_score` boundaries.
- Test sanitization in the LLM-bound branch.

---

### `tests/unit/test_decide.py`
**Currently:** 3 tests: `decide_router` for pause and act;
`_segment_learner` produces correct `mastery_range`, `learning_style`,
`struggle_count_gte`.

**What could be improved:** No tests for the actual
`decide_node` (Thompson sampling) since it requires a real DB.

**What could be added/changed/updated:**
- Mock `WisdomRepo` and test that the highest Thompson-sample wins.
- Test exploration flag for `total_trials < 10`.
- Test fallback when LLM returns invalid JSON.

---

### `tests/unit/test_act.py`
**Currently:** 2 tests for `_build_intervention_content`:
`concept_explanation` and `encouragement`.

**What could be improved:** No test for intervention persistence.

**What could be added/changed/updated:**
- Test all 6 intervention templates.
- Assert `display.position` and `auto_dismiss_seconds` differ by
  type.
- Test the cycle_count increment.
- Test the persistence call (with mocked `InterventionRepo`).

---

### `tests/unit/test_sanitizer.py`
**Currently:** 4 tests: email, phone, no-PII, full
`sanitize_observation_event` (drops user_id/session_id, masks
email).

**What could be improved:** No tests for card, name regex;
no-false-positive tests; no tests for `sanitize_learner_summary`.

**What could be added/changed/updated:**
- Add the missing positive/negative cases.
- Add `sanitize_learner_summary` tests.
- Add edge cases (URLs with emails, formatted phone numbers).

---

### `tests/unit/test_concept_graph.py`
**Currently:** 6 tests: cosine similarity (identical, orthogonal),
`_parse_llm_json` (valid object→[], array→one), `_deduplicate_concepts`
(empty, single).

**What could be improved:** `_parse_llm_json` test with a non-array
JSON object is a bit weird (asserts `== []`); the function only
parses arrays.

**What could be added/changed/updated:**
- Add `_parse_llm_json` test for arrays with extra prose around them.
- Test dedup threshold behavior (≥ threshold merges).
- Test embedding cosine with non-orthogonal vectors.
- Test `build_concept_graph` end-to-end (with mocked LLM).

---

### `tests/unit/test_thompson_sampling.py`
**Currently:** 3 tests: `segment_learner` empty + with data, and a
statistical sanity check on `np.random.beta`.

**What could be improved:** `beta(10,2)` should average ~0.83 — the
test uses 0.7..0.9; `beta(2,10)` should average ~0.167 — the test
uses 0.1..0.3. OK.

**What could be added/changed/updated:**
- Add a determinism test (set seed, assert exact samples).
- Add a confidence-interval test for the posterior.

---

### `tests/integration/test_ooda_cycle.py`
**Currently:** 2 tests: instantiate `OODAState` and `build_ooda_graph`
asserts the 5 nodes exist.

**What could be improved:** No real cycle run; no Postgres / Redis.

**What could be added/changed/updated:**
- Add a full cycle run with testcontainers.
- Add a `test_should_pause_branch` and `test_should_act_branch` with
  conditional edges.
- Add a test that the graph ends after `max_cycles`.

---

### `tests/integration/test_redis_streams.py`
**Currently:** 2 tests: `ObservationEventPayload` round-trip and a
batch of 2.

**What could be improved:** Doesn't actually push to a real Redis.

**What could be added/changed/updated:**
- Spin up a Redis testcontainer; push + read + ack.
- Test the `xadd`/`xreadgroup` round trip with a real consumer
  group.
- Test `BUSYGROUP` handling in `_ensure_group`.

---

### `tests/integration/test_intervention_delivery.py`
**Currently:** 3 tests: `calibrate_difficulty` (with concept and
without), `_build_intervention_content` for `video_recommendation`.

**What could be improved:** Doesn't test the WebSocket delivery
end-to-end.

**What could be added/changed/updated:**
- Add a real WS round-trip test (TestClient + a real listener).
- Add a `measure_effectiveness` test with a mocked repo.
- Add a `deliver_via_sse` test (assert the EventSource payload).

---

## 17. `templates/`

### `templates/youtube_login.html`
**Currently:** Static login form, cookie-based session, "Start
Learning Session" button, 7-step pipeline badge row. Uses Jinja-style
`{{ error }}` placeholder but `youtube_app.py` doesn't render this
template (uses an inlined f-string copy instead).

**What could be improved:** Template exists but is dead code.

**What could be added/changed/updated:**
- Wire it up with `Jinja2Templates(directory="templates")`.
- Add a "remember me" checkbox.
- Add a CSRF token field.
- Add OAuth / Google login option.

---

### `templates/youtube_watch.html`
**Currently:** Player wrapper, URL input, 5 stat cards, event log,
finish button. JS uses YouTube IFrame API. Sends events to
`/api/event`, `/api/start`, `/api/finish`. Pipeline progress
indicator.

**What could be improved:** Same dead-code issue — not used by
`youtube_app.py`.

**What could be added/changed/updated:**
- Wire to `Jinja2Templates`.
- Add a "current concept" label (from concept_mappings).
- Add SSE-based live feedback (recommendations as the user watches).
- Add a "skip to recommended section" link.
- Add local-storage persistence of progress.

---

### `templates/youtube_results.html`
**Currently:** Engagement ring (conic-gradient), struggle severity
badge, stat grid, video section map, recommendations list, narrative
box. Pure Jinja template.

**What could be improved:** Same dead-code issue.

**What could be added/changed/updated:**
- Wire it up; remove the f-string in `youtube_app.py`.
- Add a "save as PDF" button.
- Add shareable session URL.
- Add a feedback widget ("Was this analysis useful?").

---

## 18. Cross-cutting improvements

These are project-wide changes that touch many files at once.

### 18.1 Observability
- No metrics, no structured logs, no Sentry initialization (the
  `sentry-sdk` dep is unused).
- Add Sentry in `src/api/app.py` lifespan.
- Add `prometheus-fastapi-instrumentator` for `/metrics`.
- Add a `cycle_id` (uuid) per OODA cycle and pass it through state +
  logs + DB.

### 18.2 Persistence of agent state
- The checkpointer is **best-effort** MemorySaver.
- Session state lives in Redis (`SessionCache`).
- No replay capability (`pop_events` is destructive).
- Move raw events to a dedicated Redis Stream (`XADD`/`XREADGROUP`)
  and use it as the system of record.

### 18.3 Multi-tenant
- No tenant ID anywhere.
- Every query is unscoped.
- Add a `tenant_id` column to all `ai_*` tables and enforce row-level
  security in Postgres.

### 18.4 Auth
- The YouTube demo has hard-coded passwords; the OODA API has no
  auth at all.
- Add OAuth2 + JWT middleware in `src/api/dependencies.py`.
- Replace `user_id` path params with the authenticated subject.

### 18.5 Tool wiring
- Six `src/agent/tools/*` modules exist with `@tool` decorations, but
  none of them are `bind_tools`'d to the LLM in `graph.py`.
- Add a `TOOL_REGISTRY` and bind in `compile_ooda_agent`.

### 18.6 Prompt source-of-truth
- `ORIENT_SYSTEM_PROMPT` lives in both `nodes/orient.py` and
  `prompts/orient_prompt.py`.
- `DECIDE_SYSTEM_PROMPT` is duplicated in `nodes/decide.py` and
  `prompts/decide_prompt.py`.
- `CHALLENGE_GENERATION_PROMPT` is duplicated in
  `agent/prompts/generate_prompt.py` and `intervention/generator.py`.
- Pick one home and import.

### 18.7 Configuration
- `Settings()` has cooldown/TTL but they're never read by the
  agents/workers.
- `LLM_CONFIG` in `src/config/llm_config.py` is hard-coded; the
  `Settings()` LLM values exist but are not consulted.

### 18.8 Containerization of the API
- `docker-compose.yml` only runs Postgres + Redis.
- `Dockerfile` doesn't exist; CI/CD is absent.
- Add a `Dockerfile` for the API, a separate one for the worker, and
  compose services for both.

### 18.9 Migration safety
- Initial migration references `ab6_user_data.user_details.id` which
  is not in this repo. Bootstrap will fail.
- Add a separate `0000_user_data.py` migration that creates the user
  schema, or document the external dependency.

### 18.10 Schema quality
- Embedding dim 1536 is hard-coded.
- No HNSW index.
- No CHECK constraints on alpha/beta, difficulty, weight.
- `effectiveness_label` is a free string.

### 18.11 Performance
- `get_with_neighbors` does an N+1 to fetch concept rows.
- `select_intervention` (selector.py) and `decide_node` both do
  Thompson sampling — double work.
- `init_chat_model` called per request in `provider.py` — should be
  cached.

### 18.12 LLM quality
- The LLM's output in `decide_node` is overridden by Thompson
  sampling — the LLM is decorative.
- Use `with_structured_output(Decision)` to get reliable JSON.
- Add a 2nd-pass "explainability" node that surfaces why a
  particular intervention was chosen.

### 18.13 Testing
- 21 unit tests but the integration tests don't talk to real
  Postgres/Redis.
- No load tests.
- Add `testcontainers` for Postgres and Redis.
- Add a Locust profile for the API.

### 18.14 Demos vs. live
- Three demo entry points (`demo.py`, `interactive_demo.py`,
  `web_demo.py`) + the YouTube app + the real API = 5 different
  ways to run the same agent.
- Consolidate: keep one `interactive_demo.py` and one CLI `demo.py`;
  remove `web_demo.py` (or merge).

### 18.15 Dead code / dead files
- `templates/youtube_*.html` are not used.
- `src/agent/prompts/generate_prompt.py` and
  `explain_prompt.py` are not imported.
- `src/agent/tools/*` is not bound to any LLM.
- `src/concept_graph/builder.py` is not called from the API.
- Remove or wire up.

### 18.16 Type hygiene
- `pyproject.toml` enables `mypy strict`, but most modules use
  `Column(...)` and `# type: ignore` is everywhere.
- Models use `Mapped[]` half-typed; migrate to fully
  `mapped_column()`.

### 18.17 Error responses
- The API has no consistent error model.
- Add a `BaseModel` for `ErrorResponse` and a global exception
  handler that maps `AB6AIError` subclasses to status codes.

### 18.18 Rate-limiting
- LLM has a per-process `RateLimiter`; the API has no per-user
  rate limit.
- Add `slowapi` and a Redis-backed limiter.

### 18.19 Background jobs
- ARQ worker is a stub.
- Replace with real workers: `process_observation → enqueue OODA
  cycle for user`, `process_intervention_outcome → update
  effectiveness after delay`.

### 18.20 Frontend / UI
- No first-party frontend; the demos are minimal.
- Build a small Next.js / SvelteKit dashboard for admins
  (intervention log, wisdom store, benchmarks) and learners
  (current struggle, recommended next step).

### 18.21 Eval / regression tests
- No golden scenarios.
- Add a "scenario pack" (JSON of events + expected intervention
  type) and run the cycle deterministically (`seed` the RNG).

### 18.22 Deployment
- No Helm chart, no Terraform, no GitHub Actions.
- Add a `deploy/k8s/` folder with deployment + service +
  configmap + secret templates.
- Add `.github/workflows/ci.yml` running `ruff`, `mypy`, `pytest`.

### 18.23 Documentation drift
- `docs/phase-09-testing-and-demo/01-testing-and-demo.md` claims
  "21 unit tests"; the count can rot.
- Add a docs linter or generate the test count from
  `pytest --collect-only -q`.

### 18.24 Naming consistency
- `src/agent/prompts/explain_prompt.py` (snake_case) vs
  `src/api/middleware/sanitizer.py` (snake_case) — OK, but
  `llm_config.py` mixes concerns (provider names + per-purpose
  config). Split into `providers.py` + `routing.py`.

### 18.25 Security
- CORS `*` in `app.py`.
- `start-live.ps1` is fine for dev, but no separate prod entry.
- No CORS preflight, no CSP headers.
- Add `secure_headers` middleware.

### 18.26 Streaming UX
- Telemetry WS receives data but the agent's WebSocket is
  receive-only (`ping/pong`). Interventions are pushed via a
  different socket.
- Combine into one socket per user with a typed envelope
  (`{type: "telemetry" | "intervention" | "control", ...}`).

### 18.27 Schema introspection
- The recursive CTE in `get_with_neighbors` is a custom
  implementation of "graph neighborhood".
- Add a recursive UDF or use Apache AGE / Memgraph for richer
  graph operations.

### 18.28 Failure modes
- `concept_repo.get_with_neighbors` raises nothing on missing
  concept; returns a dict.
- `generator.generate_challenge` returns a dict with `error` key
  on failure — the calling code must check.
- Replace with a discriminated union / Result type.

### 18.29 Cost
- No token usage tracking per request.
- Add a middleware that wraps `llm_call` and records
  `prompt_tokens`, `completion_tokens`, `model`, `user_id`, and
  stores it in `ai_intervention_log` (new columns) for billing.

### 18.30 Versioning
- No API version negotiation beyond the `/v1/` prefix.
- Add a `X-API-Version` header check.
- Add OpenAPI versioning.

---

*End of audit.*
