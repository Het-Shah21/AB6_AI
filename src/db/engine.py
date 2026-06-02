"""Database engine and session factory.

Dispatches on ``MENTOR_BACKEND``:

  - ``postgres`` (default) — asyncpg against the real Postgres + pgvector
  - ``sqlite``            — aiosqlite against a single local file
  - ``memory``            — pure in-process dicts (for demos / no-Docker)

All three return an object with the same ``execute(text(...))`` /
``commit()`` / ``close()`` / ``refresh()`` surface, so the rest of the
codebase doesn't have to branch.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.config.settings import get_settings


class Base(DeclarativeBase):
    pass


_pg_engine: AsyncEngine | None = None
_pg_session_factory: async_sessionmaker[AsyncSession] | None = None


async def get_engine() -> AsyncEngine:
    global _pg_engine
    if _pg_engine is None:
        settings = get_settings()
        _pg_engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    return _pg_engine


async def get_pg_session_factory() -> async_sessionmaker[AsyncSession]:
    global _pg_session_factory
    if _pg_session_factory is None:
        engine = await get_engine()
        _pg_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _pg_session_factory


def backend_name() -> str:
    return get_settings().mentor_backend


def get_session():
    """Return an async-session-like object for the active backend.

    Always returns a coroutine, so callers can uniformly write
    ``sess = await get_session()`` regardless of backend.
    """
    backend = backend_name()
    if backend == "sqlite":
        return _memory_session_factory("sqlite")
    if backend == "memory":
        return _memory_session_factory("memory")
    return _pg_session_coro()


async def _memory_session_factory(kind: str):
    if kind == "sqlite":
        from src.db.sqlite_backend import SQLiteSession
        return SQLiteSession()
    from src.db.in_memory import MemorySession
    return MemorySession()


async def _pg_session_coro() -> AsyncSession:
    factory = await get_pg_session_factory()
    return factory()


async def close_engine() -> None:
    global _pg_engine
    if _pg_engine is not None:
        await _pg_engine.dispose()
        _pg_engine = None


__all__ = [
    "Base",
    "get_engine",
    "get_pg_session_factory",
    "get_session",
    "backend_name",
    "close_engine",
]
