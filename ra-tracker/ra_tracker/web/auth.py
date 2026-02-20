"""Authentication utilities and FastAPI dependencies for session management."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, Request, HTTPException, status

from ..database import get_db, User, Session
from ..config import get_config
from ..observability.sentry_config import set_sentry_user


def create_session_token() -> str:
    """Generate cryptographically secure session token."""
    return secrets.token_urlsafe(32)


def create_user_session(user_id: int) -> tuple[str, datetime]:
    """Create a new session for user. Returns (token, expires_at)."""
    config = get_config()
    token = create_session_token()
    expires_at = datetime.now() + timedelta(days=config.session.timeout_days)
    db = get_db()
    db.create_session(user_id, token, expires_at)
    return token, expires_at


async def get_session_token(request: Request) -> Optional[str]:
    """Extract session token from cookie."""
    return request.cookies.get("session_token")


async def get_current_user(
    token: Optional[str] = Depends(get_session_token)
) -> Optional[User]:
    """Get current user from session, or None if not logged in."""
    if not token:
        return None
    db = get_db()
    session = db.get_valid_session(token)
    if not session:
        return None
    user = db.get_user_by_id(session.user_id)
    if user:
        try:
            set_sentry_user(user.id, user.email)
        except Exception:
            pass  # Don't break auth if Sentry is unavailable
    return user


async def require_auth(
    request: Request,
    user: Optional[User] = Depends(get_current_user)
) -> User:
    """Require authentication, redirect to login if not authenticated."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return user


def set_session_cookie(response, token: str, expires_at: datetime, request: Optional[Request] = None, secure: Optional[bool] = None):
    """Set session cookie with security flags.

    Auto-detects secure flag from request scheme if not explicitly set.
    Uses secure=True for HTTPS, secure=False for HTTP.
    """
    max_age = int((expires_at - datetime.now()).total_seconds())

    # Auto-detect secure flag from request if not explicitly provided
    if secure is None:
        if request is not None:
            # Check if request came over HTTPS
            secure = request.url.scheme == "https"
        else:
            # Default to True if we can't detect
            secure = True

    response.set_cookie(
        key="session_token",
        value=token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/"
    )


def clear_session_cookie(response):
    """Clear session cookie on logout."""
    response.delete_cookie(key="session_token", path="/")


async def require_verified_email(
    request: Request,
    user: User = Depends(require_auth)
) -> User:
    """Require email verification, redirect to verify page if not verified.

    Use this instead of require_auth for protected routes that need verification.
    """
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/verify-email"}
        )
    return user


async def require_admin(user: User = Depends(require_auth)) -> User:
    """Require admin privileges. Returns 403 Forbidden for non-admins."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user
