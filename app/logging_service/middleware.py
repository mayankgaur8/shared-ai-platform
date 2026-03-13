import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("saib.request")

SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        trace_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.trace_id = trace_id
        start = time.monotonic()

        try:
            response = await call_next(request)
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "%s %s → %s (%dms) trace=%s",
                request.method,
                request.url.path,
                response.status_code,
                latency_ms,
                trace_id,
            )
            response.headers["X-Trace-Id"] = trace_id
            response.headers["X-Latency-Ms"] = str(latency_ms)
            return response
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error("request_error path=%s error=%s (%dms)", request.url.path, exc, latency_ms)
            raise
