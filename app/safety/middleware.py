import json
import logging
import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("saib.safety")

CHECKED_PATHS = ("/v1/generate", "/v1/chat")

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+|previous\s+)?instructions", re.I),
    re.compile(r"you\s+are\s+now\s+(a\s+|an\s+)?(different|evil|unrestricted|jailbroken)", re.I),
    re.compile(r"\bDAN\s+mode\b|\bjailbreak\b", re.I),
    re.compile(r"bypass\s+(safety|filter|restriction|moderation)", re.I),
    re.compile(r"forget\s+(everything|all|your)\s+(above|previous|training)", re.I),
]


def _detect_injection(text: str) -> tuple[bool, str]:
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return True, pattern.pattern
    return False, ""


class SafetyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not any(request.url.path.startswith(p) for p in CHECKED_PATHS):
            return await call_next(request)

        body_bytes = await request.body()
        try:
            body = json.loads(body_bytes) if body_bytes else {}
        except json.JSONDecodeError:
            body = {}

        user_text = (
            body.get("message")
            or str((body.get("inputs") or {}).get("topic", ""))
            or ""
        )

        if user_text:
            flagged, reason = _detect_injection(user_text)
            if flagged:
                logger.warning("injection_blocked path=%s", request.url.path)
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Request blocked by safety filter.", "reason": "potential_injection"},
                )

        # Re-attach body so downstream handlers can read it
        async def receive():
            return {"type": "http.request", "body": body_bytes}

        request._receive = receive
        return await call_next(request)
