"""Email verification token generation and validation using itsdangerous."""

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from ..config import get_config


def _get_verification_serializer() -> URLSafeTimedSerializer:
    """Get serializer for email verification tokens.

    Uses a dedicated salt ('email-verify') separate from unsubscribe tokens.
    """
    config = get_config()
    secret = config.app.secret_key
    if not secret:
        raise ValueError("app.secret_key not configured - required for verification tokens")
    return URLSafeTimedSerializer(secret, salt="email-verify")


def generate_verification_token(user_id: int) -> str:
    """Generate a signed verification token for a user.

    Token is URL-safe, contains user_id, and valid for 24 hours.

    Args:
        user_id: The user's database ID

    Returns:
        URL-safe token string
    """
    serializer = _get_verification_serializer()
    return serializer.dumps({"user_id": user_id})


def verify_verification_token(token: str, max_age_hours: int = 24) -> dict:
    """Verify and decode a verification token.

    Args:
        token: The signed token from URL
        max_age_hours: Maximum age in hours (default 24)

    Returns:
        Dict with 'user_id' key if valid

    Raises:
        SignatureExpired: If token has expired (>24 hours old)
        BadSignature: If token is tampered or invalid
    """
    serializer = _get_verification_serializer()
    max_age_seconds = max_age_hours * 60 * 60
    return serializer.loads(token, max_age=max_age_seconds)


def get_user_id_from_expired_token(token: str) -> int:
    """Extract user_id from an expired token (for auto-resend on expired link).

    This is used when a user clicks an expired verification link - we want to
    identify them to auto-send a new verification email.

    Args:
        token: The expired token

    Returns:
        user_id extracted from token

    Raises:
        BadSignature: If token is tampered or completely invalid
    """
    serializer = _get_verification_serializer()
    # Load with very long max_age to get data from expired token
    # We just need the user_id, not to validate it's still within time
    data = serializer.loads(token, max_age=365 * 24 * 60 * 60)  # 1 year
    return data["user_id"]
