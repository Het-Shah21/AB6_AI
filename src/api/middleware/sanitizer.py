import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.llm.sanitizer import strip_pii

logger = logging.getLogger(__name__)


class PIISanitizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        if "/api/v1/ai/" in request.url.path:
            body = await request.body()
            if body:
                sanitized = strip_pii(body.decode("utf-8", errors="replace"))
                if sanitized != body.decode("utf-8", errors="replace"):
                    logger.info(
                        "PII sanitized in request: %s", request.url.path
                    )
        return await call_next(request)
