# Legacy Code Map

The unified 8-stage mentor (`src.mentor/`, `mentor_app.py`) is the
canonical entry point.  Everything in `legacy/` is kept only for
historical reference and for running the existing OODA / YouTube
test suite.  New work should target `src.mentor/`.

## What moved

| Old import path                  | New import path                | Status         |
|----------------------------------|--------------------------------|----------------|
| `src.agent.*`                    | `legacy.agent.*`               | OODA agent     |
| `src.youtube_agent.*`            | `legacy.youtube_agent.*`       | YouTube agent  |
| `src.api.*`                      | `legacy.api.*`                 | OODA API       |
| `src.concept_graph.*`            | `legacy.concept_graph.*`       | Knowledge graph|
| `src.memory.*`                   | `legacy.memory.*`              | Legacy memory  |
| `src.intervention.*`             | `legacy.intervention.*`        | Thompson/etc.  |
| `src.ingestion.*`                | `legacy.ingestion.*`           | Redis Streams  |
| `src.api.app:app` (uvicorn)      | `mentor_app:app` (uvicorn)     | API entrypoint |
| `src.ingestion.worker.WorkerSettings` (arq) | `legacy.ingestion.worker.WorkerSettings` | ARQ worker |
| `youtube_app.py` (root)          | `legacy/youtube_app.py`        | YouTube demo   |
| `templates/youtube_*.html`       | _deleted_                      | Dead code      |
| `web_demo.py`                    | _deleted_                      | Duplicate demo |

## What stayed (shared with mentor)

`src/llm/`, `src/db/`, `src/shared/`, `src/config/` are still
imported by `src.mentor` and are not deprecated.

## Running the mentor

```bash
# Live stack (Postgres + Redis + uvicorn + ARQ worker)
.\start-live.ps1

# Or, manual:
uvicorn mentor_app:app --host 0.0.0.0 --port 8000
```

## Running the legacy OODA agent (for reference)

```bash
uvicorn legacy.api.app:app --host 0.0.0.0 --port 8002
python legacy/youtube_app.py
```

## What is not deprecated

- All `src.mentor.*` modules.
- `mentor_app.py` (root).
- `src/llm`, `src/db`, `src/shared`, `src/config` (shared).
- `docs/`, `scripts/`, `tests/`, `alembic/`.

## When the legacy code can be deleted

Once:

1. The mentor cycles are running in production for ≥ 1 cohort.
2. All consumers (`tests/integration/*`, `tests/unit/test_*.py`
   except `test_sanitizer.py`, `test_policies.py`, `test_stages.py`)
   are rewritten to target `src.mentor` or removed.
3. The PowerShell `start-live.ps1` only references the mentor.

At that point, `git rm -rf legacy/` is the single deletion commit.
