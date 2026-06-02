"""Structured logging + cycle correlation + Sentry init."""

from __future__ import annotations

import logging
import os
import sys
import uuid
from contextvars import ContextVar
from typing import Any

try:
    import sentry_sdk
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    _SENTRY_AVAILABLE = True
except Exception:  # pragma: no cover
    _SENTRY_AVAILABLE = False

from src.config.settings import get_settings


_cycle_id: ContextVar[str | None] = ContextVar("cycle_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)


class _CycleFilter(logging.Filter):
    """Inject cycle_id and user_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.cycle_id = _cycle_id.get() or "-"
        record.user_id = _user_id.get() or "-"
        return True


def configure_logging() -> None:
    """Idempotent root-logger setup. Honours LOG_LEVEL from .env."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    if getattr(root, "_mentor_configured", False):
        return

    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s [%(levelname)s] [cycle=%(cycle_id)s user=%(user_id)s] %(name)s :: %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(_CycleFilter())
    root.handlers[:] = [handler]
    root.setLevel(level)
    root._mentor_configured = True  # type: ignore[attr-defined]

    # Quiet noisy libs
    for name in ("httpx", "httpcore", "urllib3", "langchain", "openai"):
        logging.getLogger(name).setLevel(max(level, logging.WARNING))


def init_sentry() -> None:
    """Initialise Sentry if a DSN is configured."""
    if not _SENTRY_AVAILABLE:
        return
    dsn = os.environ.get("SENTRY_DSN") or get_settings().sentry_dsn
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FastApiIntegration(),
            AsyncioIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        environment=os.environ.get("ENV", "dev"),
    )


def set_cycle(cycle_id: str | uuid.UUID | None = None, user_id: str | None = None) -> tuple[str, str]:
    cid = str(cycle_id or uuid.uuid4())
    uid = str(user_id) if user_id else ""
    _cycle_id.set(cid)
    _user_id.set(uid)
    return cid, uid


def get_logger(name: str) -> logging.LoggerAdapter:
    base = logging.getLogger(name)
    return logging.LoggerAdapter(base, extra={})


def log_event(logger: logging.LoggerAdapter, event_type: str, **fields: Any) -> None:
    """Emit a structured event line. JSON-ish in production, human in dev."""
    payload = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.info("event=%s %s", event_type, payload)
