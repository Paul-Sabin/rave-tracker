"""CSRF protection middleware for RA Tracker."""

import hmac
import logging
import secrets
from typing import Set
from urllib.parse import parse_qs

from fastapi import Request, Response
from starlette.types import ASGIApp, Receive, Scope, Send, Message

logger = logging.getLogger(__name__)


class CSRFMiddleware:
    """CSRF protection using Double Submit Cookie pattern.

    Implemented as pure ASGI middleware to avoid body consumption issues
    with BaseHTTPMiddleware.

    - Generates CSRF token and sets as cookie (readable by JS)
    - For unsafe methods (POST, PUT, DELETE, PATCH):
      - Checks X-CSRFToken header (for AJAX) OR csrf_token form field
      - Compares against cookie value using constant-time comparison
    - Stores token in request.state for template access
    """

    def __init__(
        self,
        app: ASGIApp,
        cookie_name: str = "csrftoken",
        header_name: str = "x-csrftoken",
        form_field: str = "csrf_token",
        exempt_paths: Set[str] = None,
        safe_methods: Set[str] = None,
    ):
        self.app = app
        self.cookie_name = cookie_name
        self.header_name = header_name.lower()
        self.form_field = form_field
        self.exempt_paths = exempt_paths or {"/telegram/webhook"}
        self.safe_methods = safe_methods or {"GET", "HEAD", "OPTIONS", "TRACE"}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = scope.get("path", "")

        # Check if path is exempt
        if path in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        # Get or generate CSRF token
        csrf_cookie = request.cookies.get(self.cookie_name)
        if csrf_cookie:
            csrf_token = csrf_cookie
        else:
            csrf_token = secrets.token_urlsafe(32)

        # Store token in request.state for template access
        # Starlette's request.state wraps scope["state"] dict with State class
        # which provides attribute access. Just ensure it's a dict.
        if "state" not in scope or not isinstance(scope["state"], dict):
            scope["state"] = {}
        scope["state"]["csrf_token"] = csrf_token

        method = scope.get("method", "GET")

        # Validate on unsafe methods
        if method not in self.safe_methods:
            # Get submitted token from header (AJAX)
            headers = dict(scope.get("headers", []))
            submitted = headers.get(self.header_name.encode(), b"").decode()

            # If no header, try to read from form body
            if not submitted:
                content_type = headers.get(b"content-type", b"").decode()
                if "application/x-www-form-urlencoded" in content_type:
                    # Read and cache body for form parsing
                    body_parts = []

                    async def caching_receive() -> Message:
                        message = await receive()
                        if message["type"] == "http.request":
                            body_parts.append(message.get("body", b""))
                        return message

                    # Read body
                    while True:
                        message = await caching_receive()
                        if message["type"] == "http.request":
                            if not message.get("more_body", False):
                                break
                        else:
                            break

                    body = b"".join(body_parts)

                    # Parse form data to get CSRF token
                    try:
                        form_data = parse_qs(body.decode("utf-8"))
                        submitted = form_data.get(self.form_field, [""])[0]
                    except Exception as e:
                        logger.warning(f"Could not parse form for CSRF: {e}")

                    # Create a new receive that returns cached body
                    body_sent = False

                    async def cached_receive() -> Message:
                        nonlocal body_sent
                        if not body_sent:
                            body_sent = True
                            return {"type": "http.request", "body": body, "more_body": False}
                        return {"type": "http.request", "body": b"", "more_body": False}

                    receive = cached_receive

            # Validate token
            if not csrf_cookie:
                logger.warning(f"CSRF validation failed: no cookie for {path}")
                response = Response(
                    content="CSRF validation failed: missing token cookie",
                    status_code=403
                )
                await response(scope, receive, send)
                return

            if not submitted:
                logger.warning(f"CSRF validation failed: no submitted token for {path}")
                response = Response(
                    content="CSRF validation failed: missing token in request",
                    status_code=403
                )
                await response(scope, receive, send)
                return

            if not hmac.compare_digest(csrf_cookie, submitted):
                logger.warning(f"CSRF validation failed: token mismatch for {path}")
                response = Response(
                    content="CSRF validation failed: token mismatch",
                    status_code=403
                )
                await response(scope, receive, send)
                return

        # Wrap send to add CSRF cookie to response
        is_secure = scope.get("scheme", "http") == "https"
        cookie_value = (
            f"{self.cookie_name}={csrf_token}; "
            f"Path=/; "
            f"SameSite=Lax; "
            f"Max-Age={86400 * 7}"
        )
        if is_secure:
            cookie_value += "; Secure"

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", cookie_value.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cookie)
