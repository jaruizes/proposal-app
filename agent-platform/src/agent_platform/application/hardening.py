from __future__ import annotations

import hmac
import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agent_platform.config import Settings


class HardeningMiddleware(BaseHTTPMiddleware):
    """Small, dependency-free security boundary for the HTTP surface."""

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

        if self._body_too_large(request):
            return self._response(413, "REQUEST_TOO_LARGE", "Request body exceeds configured limit", request_id)

        if self._requires_api_key(request) and not self._valid_api_key(request):
            return self._response(401, "UNAUTHORIZED", "Valid X-API-Key header required", request_id)

        if self.settings.rate_limit_enabled and self._rate_limited(request):
            return self._response(429, "RATE_LIMITED", "Too many requests", request_id, {"Retry-After": "60"})

        try:
            response = await call_next(request)
        except Exception:
            return self._response(500, "INTERNAL_ERROR", "Unexpected server error", request_id)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    def _body_too_large(self, request: Request) -> bool:
        value = request.headers.get("content-length")
        if not value:
            return False
        try:
            return int(value) > self.settings.max_request_body_bytes
        except ValueError:
            return True

    def _requires_api_key(self, request: Request) -> bool:
        if not self.settings.api_key_enabled:
            return False
        path = request.url.path
        if path in {"/health", "/health/live", "/health/ready"}:
            return False
        if path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/admin"):
            return False
        if path.startswith("/metrics") and not self.settings.protect_metrics:
            return False
        return path.startswith("/v1") or path.startswith("/metrics")

    def _valid_api_key(self, request: Request) -> bool:
        configured = self.settings.api_key or ""
        provided = request.headers.get("X-API-Key") or ""
        return bool(configured) and hmac.compare_digest(configured, provided)

    def _rate_limited(self, request: Request) -> bool:
        path = request.url.path
        if path.startswith("/health") or path.startswith("/admin"):
            return False
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{path.split('/')[1] if '/' in path else path}"
        now = time.monotonic()
        window = self._requests[key]
        while window and now - window[0] >= 60.0:
            window.popleft()
        if len(window) >= self.settings.rate_limit_requests_per_minute:
            return True
        window.append(now)
        return False

    @staticmethod
    def _response(status: int, code: str, message: str, request_id: str, headers: dict[str, str] | None = None):
        response = JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "request_id": request_id}})
        response.headers["X-Request-ID"] = request_id
        for key, value in (headers or {}).items():
            response.headers[key] = value
        return response
