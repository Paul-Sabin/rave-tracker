"""HTTP access logging middleware that emits structured JSON log lines per request."""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Inherits from ra_tracker logger: JSON formatter, CorrelationIdFilter, Better Stack handler
logger = logging.getLogger("ra_tracker.access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that logs structured HTTP access info via the ra_tracker logger.

    Emits one INFO log line per request with method, path, status_code, and duration_ms
    as discrete extra fields — picked up as top-level JSON keys by python-json-logger.
    The request_id field is added automatically by CorrelationIdFilter.

    Skips /health (load balancer noise) and /static/* (asset noise).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip noisy paths that don't need per-request logging
        if path == "/health" or path.startswith("/static"):
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        method = request.method
        status_code = response.status_code

        extra: dict = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }

        query = str(request.query_params)
        if query:
            extra["query"] = query

        logger.info(
            f"{method} {path} {status_code} {duration_ms}ms",
            extra=extra,
        )

        return response
