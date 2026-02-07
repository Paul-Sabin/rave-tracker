"""Password reset token generation and validation using itsdangerous."""

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from ..config import get_config


def _get_reset_serializer() -> URLSafeTimedSerializer:
    """Get serializer for password reset tokens.

    Uses a dedicated salt ('password-reset') separate from verification tokens.
    """
    config = get_config()
    secret = config.app.secret_key
    if not secret:
        raise ValueError("app.secret_key not configured - required for reset tokens")
    return URLSafeTimedSerializer(secret, salt="password-reset")


def generate_reset_token(user_id: int) -> str:
    """Generate a signed password reset token for a user.

    Token is URL-safe, contains user_id, and valid for 24 hours.

    Args:
        user_id: The user's database ID

    Returns:
        URL-safe token string
    """
    serializer = _get_reset_serializer()
    return serializer.dumps({"user_id": user_id})


def verify_reset_token(token: str, max_age_hours: int = 24) -> dict:
    """Verify and decode a password reset token.

    Args:
        token: The signed token from URL
        max_age_hours: Maximum age in hours (default 24)

    Returns:
        Dict with 'user_id' key if valid

    Raises:
        SignatureExpired: If token has expired (>24 hours old)
        BadSignature: If token is tampered or invalid
    """
    serializer = _get_reset_serializer()
    max_age_seconds = max_age_hours * 60 * 60
    return serializer.loads(token, max_age=max_age_seconds)
