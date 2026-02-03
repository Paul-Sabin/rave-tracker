"""Rate limiting for RA Tracker using SlowAPI.

Implements dual rate limiting per SEC-01:
- IP-based: Prevents distributed attacks from single IP
- Email-based: Prevents targeted attacks against specific accounts

Email is hashed to avoid storing plaintext emails in rate limit keys,
which could be a privacy/enumeration concern.
"""

import hashlib
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

# In-memory storage (suitable for single-instance deployment)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/day", "50/hour"],
    storage_uri="memory://",
)

# Rate limit constants
LOGIN_RATE_LIMIT = "5/15minutes"
RESEND_RATE_LIMIT = "3/hour"


def get_login_key(request: Request) -> str:
    """Get key for IP-based login rate limiting.

    Args:
        request: FastAPI request object

    Returns:
        Rate limit key based on IP address
    """
    ip = get_remote_address(request) or "unknown"
    return f"login:ip:{ip}"


def _hash_email(email: str) -> str:
    """Hash email for rate limit key to avoid storing plaintext.

    Uses SHA256 truncated to 16 chars - sufficient for rate limit
    bucketing while not storing reversible email data.

    Args:
        email: Email address to hash

    Returns:
        Truncated SHA256 hash of lowercased email
    """
    normalized = email.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


class LoginRateLimiter:
    """Dual rate limiter for login attempts - tracks both IP and email.

    This class manages separate rate limit counters for:
    1. IP address - prevents one IP from hammering multiple accounts
    2. Email hash - prevents distributed attacks against one account

    Both limits must pass for a login attempt to proceed.
    """

    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        """Initialize the login rate limiter.

        Args:
            max_attempts: Maximum attempts before rate limiting (default 5)
            window_minutes: Time window in minutes (default 15)
        """
        self.max_attempts = max_attempts
        self.window_seconds = window_minutes * 60
        # In-memory storage: key -> list of timestamps
        self._attempts: dict[str, list[float]] = {}

    def _clean_old_attempts(self, key: str, current_time: float) -> None:
        """Remove attempts outside the time window."""
        if key in self._attempts:
            cutoff = current_time - self.window_seconds
            self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]
            if not self._attempts[key]:
                del self._attempts[key]

    def _get_attempt_count(self, key: str, current_time: float) -> int:
        """Get number of attempts in current window."""
        self._clean_old_attempts(key, current_time)
        return len(self._attempts.get(key, []))

    def _record_attempt(self, key: str, current_time: float) -> None:
        """Record an attempt timestamp."""
        if key not in self._attempts:
            self._attempts[key] = []
        self._attempts[key].append(current_time)

    def check_rate_limit(self, request: Request, email: str) -> tuple[bool, Optional[str]]:
        """Check if login attempt is allowed under both IP and email limits.

        Args:
            request: FastAPI request for IP extraction
            email: Email being used for login attempt

        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
            If not allowed, reason indicates which limit was hit
        """
        import time
        current_time = time.time()

        ip = get_remote_address(request) or "unknown"
        ip_key = f"login:ip:{ip}"
        email_key = f"login:email:{_hash_email(email)}"

        # Check IP limit
        ip_count = self._get_attempt_count(ip_key, current_time)
        if ip_count >= self.max_attempts:
            return False, "ip"

        # Check email limit
        email_count = self._get_attempt_count(email_key, current_time)
        if email_count >= self.max_attempts:
            return False, "email"

        return True, None

    def record_failed_attempt(self, request: Request, email: str) -> None:
        """Record a failed login attempt for both IP and email.

        Args:
            request: FastAPI request for IP extraction
            email: Email used in failed attempt
        """
        import time
        current_time = time.time()

        ip = get_remote_address(request) or "unknown"
        ip_key = f"login:ip:{ip}"
        email_key = f"login:email:{_hash_email(email)}"

        self._record_attempt(ip_key, current_time)
        self._record_attempt(email_key, current_time)

    def clear_on_success(self, request: Request, email: str) -> None:
        """Clear rate limit counters on successful login.

        This prevents a user who finally got their password right from
        being locked out due to previous failed attempts.

        Args:
            request: FastAPI request for IP extraction
            email: Email of successful login
        """
        ip = get_remote_address(request) or "unknown"
        ip_key = f"login:ip:{ip}"
        email_key = f"login:email:{_hash_email(email)}"

        self._attempts.pop(ip_key, None)
        self._attempts.pop(email_key, None)


# Global instance for login rate limiting
login_limiter = LoginRateLimiter()
