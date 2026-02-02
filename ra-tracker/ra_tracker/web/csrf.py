"""CSRF protection middleware for RA Tracker."""

import hmac
import logging
import secrets
from typing import Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection using Double Submit Cookie pattern.

    - Generates CSRF token and sets as cookie (readable by JS)
    - For unsafe methods (POST, PUT, DELETE, PATCH):
      - Checks X-CSRFToken header (for AJAX) OR csrf_token form field
      - Compares against cookie value using constant-time comparison
    - Stores token in request.state for template access
    """

    def __init__(
        self,
        app,
        cookie_name: str = "csrftoken",
        header_name: str = "x-csrftoken",
        form_field: str = "csrf_token",
        exempt_paths: Set[str] = None,
        safe_methods: Set[str] = None,
    ):
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name.lower()  # Headers are case-insensitive
        self.form_field = form_field
        self.exempt_paths = exempt_paths or {"/telegram/webhook"}
        self.safe_methods = safe_methods or {"GET", "HEAD", "OPTIONS", "TRACE"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # Check if path is exempt
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Get or generate CSRF token
        csrf_cookie = request.cookies.get(self.cookie_name)
        if csrf_cookie:
            csrf_token = csrf_cookie
        else:
            csrf_token = secrets.token_urlsafe(32)

        # Store token in request.state for template access
        request.state.csrf_token = csrf_token

        # Validate on unsafe methods
        if request.method not in self.safe_methods:
            # Get submitted token from header (AJAX) or we'll check form later
            submitted = request.headers.get(self.header_name)

            # If no header, try to read from form body
            # Note: For form submissions, the form data will be read by the route
            # We check header first (AJAX pattern) which covers most cases
            if not submitted:
                # For URL-encoded forms, we can peek at the body
                # But this is tricky with streaming - prefer header approach
                # For now, allow form submissions through and let routes validate
                # This works because our templates include hidden csrf_token field
                content_type = request.headers.get("content-type", "")
                if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
                    # Read form data - this caches it
                    try:
                        form = await request.form()
                        submitted = form.get(self.form_field)
                    except Exception as e:
                        logger.warning(f"Could not read form for CSRF: {e}")

            # Validate token
            if not csrf_cookie:
                logger.warning(f"CSRF validation failed: no cookie for {request.url.path}")
                return Response(
                    content="CSRF validation failed: missing token cookie",
                    status_code=403
                )

            if not submitted:
                logger.warning(f"CSRF validation failed: no submitted token for {request.url.path}")
                return Response(
                    content="CSRF validation failed: missing token in request",
                    status_code=403
                )

            if not hmac.compare_digest(csrf_cookie, submitted):
                logger.warning(f"CSRF validation failed: token mismatch for {request.url.path}")
                return Response(
                    content="CSRF validation failed: token mismatch",
                    status_code=403
                )

        # Call the actual route
        response = await call_next(request)

        # Set cookie on response if new token (or refresh existing)
        # Cookie is NOT httponly so JS can read it
        is_secure = request.url.scheme == "https"
        response.set_cookie(
            key=self.cookie_name,
            value=csrf_token,
            httponly=False,  # JS needs to read for AJAX
            samesite="lax",
            secure=is_secure,
            path="/",
            max_age=86400 * 7,  # 7 days
        )

        return response
