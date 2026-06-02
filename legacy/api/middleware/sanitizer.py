"""PII sanitization middleware.

The previous version logged PII redactions but never actually rewrote
the request body, so downstream handlers and persistence layers still
saw the original (PII-bearing) JSON.  This implementation:
  - reads the request body
  - decodes, runs `sanitize_pii` on the JSON tree
  - replaces `request._body` so any later `await request.json()` or
    `await request.body()` returns the sanitized payload
  - extends the response headers with a `X-PII-Sanitized: true` flag
    when redactions occurred, so observability can confirm it ran
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.llm.sanitizer import sanitize_pii, strip_pii

logger = logging.getLogger(__name__)

PII_SCAN_PREFIXES = (
    "/api/v1/ai/",
    "/mentor/",
)


def _contains_pii(text: str) -> bool:
    return any(token in text for token in ("[EMAIL]", "[PHONE]", "[CARD]", "[NAME]"))


class PIISanitizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        path = request.url.path
        if not any(path.startswith(p) for p in PII_SCAN_PREFIXES):
            return await call_next(request)

        body = await request.body()
        if not body:
            return await call_next(request)

        original_text = body.decode("utf-8", errors="replace")

        try:
            parsed: Any = json.loads(original_text)
            sanitized_obj = sanitize_pii(parsed)
            sanitized_text = json.dumps(
                sanitized_obj, separators=(",", ":"), default=str
            )
        except json.JSONDecodeError:
            sanitized_text = strip_pii(original_text)
            sanitized_obj = None

        if sanitized_text != original_text:
            logger.info("PII sanitized in request: %s", path)
            request._body = sanitized_text.encode("utf-8")
            request._sanitized_json = sanitized_obj

        response: Response = await call_next(request)
        if _contains_pii(sanitized_text):
            response.headers["X-PII-Sanitized"] = "true"
        return response
