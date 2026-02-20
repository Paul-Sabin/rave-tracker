"""Sentry initialization with FastAPI auto-integration, before_send hook, and user context helpers."""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def init_sentry(dsn: str, environment: str = "production") -> None:
    """Initialize Sentry SDK for error tracking.

    Must be called BEFORE the FastAPI app is created so that Sentry's
    auto-integration can instrument the ASGI middleware properly.

    If dsn is empty or falsy, Sentry is not initialized (safe for dev environments).

    Args:
        dsn: Sentry DSN string from the Sentry project settings.
        environment: Deployment environment tag (e.g. "production", "staging").
    """
    if not dsn:
        return

    import sentry_sdk
    from asgi_correlation_id.context import correlation_id

    def before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrich Sentry events with the current request ID and strip sensitive headers."""
        # Inject correlation / request ID as a searchable tag
        request_id = correlation_id.get()
        if request_id:
            event.setdefault("tags", {})["request_id"] = request_id

        # Strip sensitive headers to avoid leaking credentials in Sentry
        try:
            request_data = event.get("request", {})
            headers = request_data.get("headers", {})
            if isinstance(headers, dict):
                headers.pop("Cookie", None)
                headers.pop("cookie", None)
                headers.pop("Authorization", None)
                headers.pop("authorization", None)
        except Exception:
            pass  # Never let before_send crash — just return the event as-is

        return event

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=0.1,  # 10% of requests traced for performance monitoring
        send_default_pii=True,   # Required for user context (id, email) to be included
        enable_logs=False,       # Logs go to Better Stack, not Sentry
        before_send=before_send,
    )

    logger.info(f"Sentry initialized for environment: {environment}")


def set_sentry_user(user_id: int, email: str) -> None:
    """Bind the authenticated user to the current Sentry scope.

    Call this after successful authentication so that Sentry errors
    include which user triggered the issue.

    Args:
        user_id: Database user ID.
        email: User's email address.
    """
    try:
        import sentry_sdk
        sentry_sdk.set_user({"id": str(user_id), "email": email})
    except Exception:
        pass  # Don't break auth if Sentry is unavailable


def clear_sentry_user() -> None:
    """Clear the user context from the current Sentry scope.

    Call this at the end of each request to prevent user context from
    bleeding into the next request handled by the same worker thread.
    """
    try:
        import sentry_sdk
        sentry_sdk.set_user(None)
    except Exception:
        pass  # Don't crash if Sentry is unavailable
