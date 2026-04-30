"""Middleware that logs every API request."""

import time
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.request_logger import RequestLogEntry, request_logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Capture and store every API request/response for monitoring."""

    SKIP_PATHS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.time()

        # Capture request body
        request_body = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    request_body = json.loads(body_bytes)
            except Exception:
                pass

        response = await call_next(request)

        # Capture response body
        response_body = None
        duration_ms = (time.time() - start) * 1000

        try:
            body_parts = []
            async for chunk in response.body_iterator:
                body_parts.append(chunk)
            full_body = b"".join(body_parts)
            response._body = full_body  # Reattach for client

            if full_body:
                response_body = json.loads(full_body)
        except Exception:
            pass

        # Only log API endpoints
        if request.url.path.startswith("/v1/"):
            entry = RequestLogEntry(
                method=request.method,
                path=request.url.path,
                query=str(request.query_params),
                status_code=response.status_code,
                duration_ms=duration_ms,
                request_body=request_body,
                response_body=response_body,
                ip=request.client.host if request.client else "",
                user_agent=request.headers.get("user-agent", ""),
            )
            request_logger.log(entry)

        return response
