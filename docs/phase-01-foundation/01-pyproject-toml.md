# Task 1.1 — Project Configuration: `pyproject.toml`

## System Design Reference

The Master System Design specified a Python 3.11+ project using `pyproject.toml` as the single source of truth for metadata, dependencies, and tool configuration. This replaces the older `setup.py` + `requirements.txt` + multiple config file pattern.

## Purpose

`pyproject.toml` is the **entry point** for the entire project. It declares:
1. **Package metadata** — name, version, description for `pip install`
2. **Dependencies** — 29 production packages for every phase
3. **Optional dev dependencies** — pytest, mypy, ruff, matplotlib
4. **Tool configuration** — ruff linter rules, mypy type checking, pytest settings

## Line-by-Line Explanation

```toml
[project]
```

The `[project]` table is the modern PEP 621 standard for Python project metadata. Tools like pip, build, and setuptools all read from here.

```toml
name = "ab6-ai-agent"
```

Package name on PyPI. When someone runs `pip install ab6-ai-agent`, this is the name. It's also used as the namespace for the installed package.

```toml
version = "0.1.0"
```

Semantic version: major 0 (pre-release / initial development), minor 1 (first feature iteration), patch 0. In production, this would be bumped with each release.

```toml
description = "AB6 Adaptive Learning AI Agent — OODA Loop Architecture"
```

Short description shown on PyPI and in `pip show`. Mentions the key architectural pattern (OODA) so anyone reading it immediately knows what this is.

```toml
requires-python = ">=3.11"
```

Minimum Python version. We use Python 3.11 features:
- `except*` for exception groups
- `Self` type (from 3.11)
- Better asyncio performance
- `tomllib` (standard library TOML parser)
If someone tries `pip install` with Python 3.10 or lower, they'll get an error.

```toml
dependencies = [
    "fastapi>=0.110.0",
```

**Line by line, here's why each dependency exists:**

| Dependency | Minimum Version | Phase | Why |
|---|---|---|---|
| `fastapi>=0.110.0` | 0.110.0 | 8 | REST API framework — async native, auto-docs, dependency injection |
| `uvicorn[standard]>=0.27.0` | 0.27.0 | 8 | ASGI server to run FastAPI; `[standard]` includes websocket support |
| `langgraph>=0.2.0` | 0.2.0 | 5 | OODA state machine — `StateGraph`, conditional edges, checkpointer |
| `langchain-core>=0.3.0` | 0.3.0 | 5 | LangChain base classes — `BaseChatModel`, `MessagesState`, tool interface |
| `langchain-openai>=0.2.0` | 0.2.0 | 2 | OpenAI LLM provider (GPT-4o-mini, GPT-4o, text-embedding-3-small) |
| `langchain-anthropic>=0.2.0` | 0.2.0 | 2 | Anthropic LLM provider (Claude Sonnet 4 — fallback 1) |
| `langchain-google-genai>=2.0.0` | 2.0.0 | 2 | Google GenAI provider (Gemini 2.5 Flash — fallback 2) |
| `asyncpg>=0.29.0` | 0.29.0 | 1 | Async PostgreSQL driver — essential for non-blocking DB access |
| `sqlalchemy[asyncio]>=2.0.0` | 2.0.0 | 1 | Async ORM — 7 models mapped to PostgreSQL tables; `[asyncio]` enables async engine |
| `alembic>=1.13.0` | 1.13.0 | 1 | Database migrations — auto-generates migration scripts from model changes |
| `redis[hiredis]>=5.0.0` | 5.0.0 | 3 | Redis client for event streaming; `[hiredis]` installs C accelerator for 10x faster parsing |
| `arq>=0.26.0` | 0.26.0 | 3 | Async Redis queue worker — background processing of event streams |
| `pgvector>=0.3.0` | 0.3.0 | 4 | PostgreSQL vector extension support — enables `<=>` cosine distance operator in SQLAlchemy |
| `numpy>=1.26.0` | 1.26.0 | 4/7 | Numerical computing — cosine similarity, Beta distribution sampling, statistics |
| `pydantic>=2.5.0` | 2.5.0 | all | Data validation — every data class uses Pydantic v2 for validation and serialization |
| `pydantic-settings>=2.1.0` | 2.1.0 | 1 | `.env` file loading — `BaseSettings` auto-reads env vars from `.env` |
| `python-dotenv>=1.0.0` | 1.0.0 | 1 | Lower-level env file loader (used by pydantic-settings under the hood) |
| `websockets>=12.0` | 12.0 | 7 | WebSocket protocol — real-time intervention delivery to browser clients |
| `sse-starlette>=2.0.0` | 2.0.0 | 7 | Server-Sent Events — alternative real-time channel using HTTP streaming |
| `sentry-sdk>=2.0.0` | 2.0.0 | 8 | Error monitoring — reports exceptions to Sentry dashboard in production |
| `httpx>=0.27.0` | 0.27.0 | 2 | Async HTTP client — used internally by LangChain for API calls |
| `tenacity>=8.2.0` | 8.2.0 | 2 | Retry library — configurable retries with backoff for LLM calls |

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "mypy>=1.8.0",
    "ruff>=0.3.0",
    "matplotlib>=3.8.0",
]
```

Optional `[dev]` extras, installed with `pip install -e ".[dev]"`:

| Package | Purpose |
|---|---|
| `pytest` | Test runner — auto-discovery of `test_*.py` files |
| `pytest-asyncio` | Async test support — marks tests with `@pytest.mark.asyncio` or uses `asyncio_mode = "auto"` |
| `pytest-cov` | Code coverage — `pytest --cov=src` reports which lines are tested |
| `mypy` | Static type checking — enforces type annotations match actual usage |
| `ruff` | Ultra-fast linter/formatter — replaces flake8 + isort + black |
| `matplotlib` | Plotting library — for generating benchmark charts and demo visualizations |

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "W"]
```

Ruff configuration:
- `target-version = "py311"` — Allows Python 3.11 syntax (e.g., `X | None` types)
- `line-length = 100` — Wider than default 88; matches the project's preferred wrapping
- `select = ["E", "F", "I", "W"]` — E (pycodestyle errors), F (pyflakes), I (isort), W (pycodestyle warnings)

```toml
[tool.mypy]
strict = true
python_version = "3.11"
ignore_missing_imports = true
```

MyPy configuration:
- `strict = true` — Enables all strict checks (no implicit Any, no untyped defs, etc.)
- `ignore_missing_imports = true` — Doesn't error on third-party packages without type stubs

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Pytest configuration:
- `asyncio_mode = "auto"` — Every `async def test_*` is automatically treated as an async test (no `@pytest.mark.asyncio` decorator needed)
- `testpaths = ["tests"]` — Only look for tests in the `tests/` directory

## How It Connects

Every other file in the project is governed by `pyproject.toml`:
- **`pip install -e .`** reads `dependencies` and makes all packages available
- **`pip install -e ".[dev]"`** adds dev tooling
- **Ruff** and **MyPy** read their settings from `[tool.ruff]` and `[tool.mypy]`
- **Pytest** reads `[tool.pytest.ini_options]` to configure async mode

## PoC Presentation Idea

Show the `pyproject.toml` as a **dependency wheel diagram**:

```
                    FastAPI (REST API)
                   /        |          \
          LangGraph       Redis        PostgreSQL
         (OODA Loop)   (Streaming)    (Persistence)
              |             |              |
        LangChain     redis[hiredis]    asyncpg
         /  |  \                        SQLAlchemy
     OpenAI  Anthropic  Google          Alembic
              GenAI
```

Highlight that each dependency maps to exactly one architectural component — nothing extraneous.
