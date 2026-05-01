"""Middleware that logs every API request."""

import time
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.request_logger import RequestLogEntry, request_logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Capture and store every API request/response for monitoring."""

    SKIP_PATHS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.time()

        # Capture request body (only read, don't consume)
        request_body = None
        if request.method in ("POST", "PUT", "PATCH") and request.url.path.startswith("/v1/"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    request_body = json.loads(body_bytes)
                    # Restore body for downstream handlers
                    async def receive():
                        return {"type": "http.request", "body": body_bytes, "more_body": False}
                    request._receive = receive
            except Exception:
                pass

        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000

        # Only log API endpoints
        if request.url.path.startswith("/v1/"):
            entry = RequestLogEntry(
                method=request.method,
                path=request.url.path,
                query=str(request.query_params),
                status_code=response.status_code,
                duration_ms=duration_ms,
                request_body=request_body,
                response_body=None,
                ip=request.client.host if request.client else "",
                user_agent=request.headers.get("user-agent", ""),
            )
            request_logger.log(entry)

        return response
