"""Access log middleware - Record request processing time"""

import time
import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Create a dedicated access logger
access_logger = logging.getLogger("access_logger")

# Set up access logger
if not access_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(fmt="%(asctime)s %(levelname)s: %(message)s", datefmt="%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    access_logger.addHandler(handler)
    access_logger.setLevel(logging.INFO)
    # Avoid propagation to the root logger and prevent duplicate logging
    access_logger.propagate = False


def _extract_client_ip(request: Request) -> str:
    """Extract client IP address"""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Access log middleware - Record request processing time"""

    def __init__(self, app, logger: logging.Logger = None):
        super().__init__(app)
        self.logger = logger or access_logger

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle requests and record access logs"""
        import uuid
        from yuxi.utils.logging_config import set_log_context, reset_log_context

        # Extract request_id from headers or generate a new one
        request_id = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        # Record request start time
        start_time = time.perf_counter()

        # Get client IP
        client_ip = _extract_client_ip(request)

        # Handle request with logging context
        token = set_log_context(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            reset_log_context(token)

        # Calculate processing time
        process_time = time.perf_counter() - start_time
        process_time_ms = int(process_time * 1000)  # Convert to milliseconds

        # Format log messages, add processing time
        log_message = (
            f"{client_ip}:{request.client.port if request.client else 'unknown'} - "
            f'"{request.method} {request.url.path}{"?" + request.url.query if request.url.query else ""} '
            f'HTTP/{request.scope["http_version"]}" '
            f"{response.status_code} - {process_time_ms}ms"
        )

        # logging
        self.logger.info(log_message)

        # Append X-Request-ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
