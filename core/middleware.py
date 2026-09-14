"""
MedScript Request Middleware & Security Filters
"""

import time
import uuid
from flask import g, request


def register_middleware(app):
    """Attach security headers, request ID generation, and latency tracking to app."""

    @app.before_request
    def handle_before_request():
        g.request_start_time = time.time()
        # Extract client request ID or generate unique ID
        g.request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"

    @app.after_request
    def handle_after_request(response):
        # Attach request ID to response header
        if hasattr(g, "request_id"):
            response.headers["X-Request-ID"] = g.request_id

        # Attach standard security headers
        headers = app.config.get("SECURITY_HEADERS", {})
        for header, value in headers.items():
            response.headers[header] = value

        # Attach process time in development
        if hasattr(g, "request_start_time"):
            duration = round((time.time() - g.request_start_time) * 1000, 2)
            response.headers["X-Response-Time"] = f"{duration}ms"

        return response
