"""Authentication utilities and FastAPI dependencies for session management."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, Request, HTTPException, status

from ..database import get_db, User, Session
from ..config import get_config


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
    return db.get_user_by_id(session.user_id)


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


def set_session_cookie(response, token: str, expires_at: datetime, secure: bool = True):
    """Set session cookie with security flags."""
    max_age = int((expires_at - datetime.now()).total_seconds())
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
