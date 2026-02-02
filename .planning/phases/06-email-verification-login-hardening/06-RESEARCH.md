# Phase 6: Email Verification & Login Hardening - Research

**Researched:** 2026-02-02
**Domain:** Security (Email Verification, Rate Limiting, Login Protection)
**Confidence:** HIGH

## Summary

This phase implements email verification for user accounts and brute-force protection on login. The existing codebase already uses `itsdangerous` with `URLSafeTimedSerializer` for unsubscribe tokens, `fastapi-mail` for email sending, and has comprehensive audit logging infrastructure in place. This provides a solid foundation to extend.

For email verification tokens, we extend the existing `itsdangerous` pattern with a dedicated salt (`email-verify`) and 24-hour expiration. The token contains user_id and can be validated atomically. For rate limiting, SlowAPI provides a decorator-based approach that integrates cleanly with FastAPI and supports in-memory storage (suitable for single-instance deployment) with composite key functions for tracking by both IP AND email.

The key UX decisions are already locked in CONTEXT.md: hard-block after signup until verified, 24-hour token validity, auto-resend on expired link, 3 resends per hour limit, and 5 failed login attempts per 15 minutes triggers block (tracked by both IP and email).

**Primary recommendation:** Extend the existing `itsdangerous` serializer pattern for verification tokens, add SlowAPI for login rate limiting with dual key tracking (IP + email), and create a simple "verify email" holding page that blocks dashboard access for unverified users.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| itsdangerous | 2.0+ | Secure token generation/validation | Already in use for unsubscribe tokens, cryptographically secure |
| slowapi | 0.1.9+ | Rate limiting | FastAPI-native, decorator-based, supports custom key functions |
| fastapi-mail | 1.4+ | Email sending | Already in use for notifications, template support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| limits | 3.0+ | Rate limit storage backends | If scaling to multi-instance (Redis backend) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SlowAPI | Custom middleware | SlowAPI is battle-tested, custom adds maintenance |
| In-memory rate limit | Redis | Single instance is fine; Redis needed for multi-pod |
| itsdangerous | JWT | itsdangerous already in codebase, simpler for this use case |

**Installation:**
```bash
pip install slowapi
```

## Architecture Patterns

### Recommended Project Structure
```
ra_tracker/
├── web/
│   ├── rate_limit.py        # Rate limiting setup and custom key functions
│   ├── verification.py      # Email verification token generation/validation
│   ├── routes.py            # (extend with verification routes)
│   └── templates/
│       ├── verify_email.html      # "Check your email" holding page
│       └── email/
│           └── verification.txt   # Plain text verification email template
├── services/
│   └── email_sender.py      # (extend with verification email function)
└── database.py              # (add verification-related columns/methods)
```

### Pattern 1: Email Verification Token Generation
**What:** Generate secure, time-limited tokens containing user_id using itsdangerous
**When to use:** New user registration, resend verification, existing user login when unverified
**Example:**
```python
# Source: itsdangerous documentation + existing unsubscribe pattern
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from ..config import get_config

def _get_verification_serializer() -> URLSafeTimedSerializer:
    """Get serializer for email verification tokens."""
    config = get_config()
    secret = config.app.secret_key
    if not secret:
        raise ValueError("app.secret_key not configured")
    return URLSafeTimedSerializer(secret, salt="email-verify")

def generate_verification_token(user_id: int) -> str:
    """Generate a signed verification token for a user.

    Token is URL-safe and contains user_id. Valid for 24 hours.
    """
    serializer = _get_verification_serializer()
    return serializer.dumps({"user_id": user_id})

def verify_verification_token(token: str, max_age_hours: int = 24) -> dict:
    """Verify and decode a verification token.

    Args:
        token: The signed token from URL
        max_age_hours: Maximum age in hours (default 24)

    Returns:
        Dict with user_id if valid

    Raises:
        SignatureExpired: If token has expired
        BadSignature: If token is tampered
    """
    serializer = _get_verification_serializer()
    max_age_seconds = max_age_hours * 60 * 60
    return serializer.loads(token, max_age=max_age_seconds)
```

### Pattern 2: Composite Key Rate Limiting (IP + Email)
**What:** Rate limit by both IP address AND email address to prevent distributed attacks and single-target attacks
**When to use:** Login endpoint to block brute-force attempts
**Example:**
```python
# Source: SlowAPI documentation + OWASP authentication guidance
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

def get_login_key(request: Request) -> str:
    """Composite key: IP + email for login rate limiting.

    Returns separate keys for IP-only and email-only limiting.
    Both must pass for login attempt to proceed.
    """
    ip = get_remote_address(request) or "unknown"
    # Email comes from form data - extracted in route
    # For limiter key_func, we track by IP
    # Email tracking done separately in route logic
    return f"login:{ip}"

limiter = Limiter(key_func=get_login_key)

# In app.py:
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# On login route:
@router.post("/login")
@limiter.limit("5/15minutes")  # 5 attempts per 15 minutes per IP
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    # Additional email-based rate limiting handled in route
    pass
```

### Pattern 3: Verification Flow Middleware/Dependency
**What:** Check if authenticated user has verified email, redirect to verification page if not
**When to use:** All protected routes (dashboard, rules, settings)
**Example:**
```python
# Source: Existing require_auth pattern
from fastapi import Depends, HTTPException, status
from ..database import User

async def require_verified_email(user: User = Depends(require_auth)) -> User:
    """Require email verification, redirect to verify page if not verified."""
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/verify-email"}
        )
    return user

# Usage: Replace require_auth with require_verified_email for protected routes
@router.get("/")
async def dashboard(request: Request, user: User = Depends(require_verified_email)):
    # Only verified users reach here
    pass
```

### Pattern 4: Expired Token Auto-Resend
**What:** When user clicks expired verification link, automatically send new email and show friendly message
**When to use:** Verification endpoint when token is expired
**Example:**
```python
# Source: UX best practices for email verification
@router.get("/verify/{token}")
async def verify_email(request: Request, token: str):
    try:
        data = verify_verification_token(token)
        user_id = data["user_id"]
        db.set_email_verified(user_id, True)
        log_audit_event("auth.email_verified", request, user_id=user_id)
        return RedirectResponse("/login?verified=1", status_code=303)

    except SignatureExpired:
        # Auto-resend new verification email
        data = verify_verification_token(token, max_age_hours=999999)  # Get user_id from expired token
        user_id = data["user_id"]
        user = db.get_user_by_id(user_id)
        if user and not user.email_verified:
            await send_verification_email(user.email, user_id)
            log_audit_event("auth.verification_resent_auto", request, user_id=user_id,
                          details={"reason": "expired_link"})
        return templates.TemplateResponse("verify_expired.html", {
            "request": request,
            "message": "Link expired. We've sent a new one to your inbox."
        })

    except BadSignature:
        return templates.TemplateResponse("verify_error.html", {
            "request": request,
            "error": "Invalid verification link."
        })
```

### Anti-Patterns to Avoid
- **Storing verification tokens in database:** Use signed tokens instead - no DB lookup needed for validation
- **Generic rate limit key:** Must track both IP AND email to catch distributed and targeted attacks
- **Blocking verified users from re-verification:** Should be harmless no-op, not error
- **Complex email HTML:** Plain text is more reliable for transactional emails

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Secure token generation | Random string | `itsdangerous.URLSafeTimedSerializer` | Cryptographically signed, time-limited |
| Token expiration check | Manual timestamp comparison | `serializer.loads(max_age=...)` | Handles edge cases, timing attacks |
| Rate limit counting | Dict with timestamps | SlowAPI with in-memory backend | Handles cleanup, thread-safe |
| IP address extraction | Manual header parsing | `slowapi.util.get_remote_address` | Handles X-Forwarded-For |
| Email template rendering | String concatenation | fastapi-mail templates | Proper escaping, consistent |

**Key insight:** The existing codebase already has itsdangerous and fastapi-mail. Extending these patterns is lower risk than introducing new libraries.

## Common Pitfalls

### Pitfall 1: Rate Limiting Bypass via Email Variation
**What goes wrong:** Attacker uses email+tag@domain.com variations to bypass per-email limits
**Why it happens:** Email addresses allow + tags that route to same inbox
**How to avoid:** Normalize email before rate limiting (strip +suffix, lowercase)
**Warning signs:** Many failed attempts with slight email variations

### Pitfall 2: Token Reuse After Verification
**What goes wrong:** Same verification link can be used multiple times
**Why it happens:** No invalidation after successful verification
**How to avoid:** Check if already verified before processing token
**Warning signs:** Audit logs show multiple verifications for same user

### Pitfall 3: Information Leakage in Error Messages
**What goes wrong:** "No user with that email" reveals whether email is registered
**Why it happens:** Different error messages for different failure modes
**How to avoid:** Generic "Invalid email or password" for all login failures
**Warning signs:** Security audit flags user enumeration vulnerability

### Pitfall 4: Rate Limit Reset on Successful Login
**What goes wrong:** Forgetting to clear failed attempt counter after successful login
**Why it happens:** Only tracking failures, not clearing on success
**How to avoid:** Explicitly clear/reset counters for IP+email on successful auth
**Warning signs:** Legitimate users blocked after recovering from typos

### Pitfall 5: Missing Rate Limit on Resend
**What goes wrong:** Attacker triggers thousands of verification emails
**Why it happens:** Rate limiting only on login, not on resend endpoint
**How to avoid:** 3 resends per hour per email (per CONTEXT.md decision)
**Warning signs:** Email sending costs spike, potential spam complaints

### Pitfall 6: Admin Lockout During Migration
**What goes wrong:** Admin users forced to verify, but can't access site to trigger email
**Why it happens:** Verification requirement applied uniformly
**How to avoid:** Auto-mark admin users (is_admin=true) as verified in migration (per CONTEXT.md)
**Warning signs:** Admin can't access admin panel after deployment

## Code Examples

Verified patterns for this codebase:

### Database Schema Changes
```sql
-- No new tables needed, users table already has email_verified column
-- Add columns for rate limiting tracking (alternative to in-memory)

-- Optional: Track failed login attempts for persistent rate limiting
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address TEXT NOT NULL,
    email TEXT,  -- NULL for IP-only tracking
    attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address, attempted_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_email ON login_attempts(email, attempted_at);

-- Migration to mark existing admins as verified
UPDATE users SET email_verified = 1 WHERE is_admin = 1;
```

### Database Methods for Verification
```python
# Source: Existing database.py patterns
def set_email_verified(self, user_id: int, verified: bool) -> None:
    """Set a user's email verification status."""
    with self.get_connection() as conn:
        conn.execute(
            "UPDATE users SET email_verified = ? WHERE id = ?",
            (verified, user_id)
        )

def get_unverified_user_by_email(self, email: str) -> Optional[User]:
    """Get user only if email is not verified. For verification flow."""
    with self.get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM users WHERE email = ? AND email_verified = 0",
            (email,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_user(row)
```

### Rate Limiting Setup
```python
# Source: SlowAPI documentation
# ra_tracker/web/rate_limit.py

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

# In-memory storage (default) - suitable for single instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/day", "50/hour"],  # Global defaults
    storage_uri="memory://",
)

def get_ip_key(request):
    """Get IP address for rate limiting."""
    return get_remote_address(request) or "unknown"

# Custom rate limit strings
LOGIN_RATE_LIMIT = "5/15minutes"  # 5 attempts per 15 minutes
RESEND_RATE_LIMIT = "3/hour"      # 3 resends per hour
```

### Verification Email (Plain Text)
```text
# Source: CONTEXT.md decisions
# ra_tracker/web/templates/email/verification.txt

Hi {{ display_name }},

Welcome to RA Tracker! Please verify your email address by clicking the link below:

{{ verification_url }}

This link will expire in 24 hours.

If you didn't create an account, you can safely ignore this email.

--
RA Tracker
```

### Email Sending Function
```python
# Source: Existing email_sender.py pattern
async def send_verification_email(
    user_email: str,
    user_id: int,
    display_name: str,
) -> bool:
    """Send verification email with secure token link.

    Args:
        user_email: Recipient email address
        user_id: User ID for token generation
        display_name: User's display name for personalization

    Returns:
        True if sent successfully, False otherwise
    """
    conf = _get_email_config()
    if not conf:
        logger.warning("Email not configured, skipping verification send")
        return False

    config = get_config()
    token = generate_verification_token(user_id)
    verification_url = f"{config.app.base_url}/verify/{token}"

    message = MessageSchema(
        subject="Welcome to RA Tracker - verify your email",
        recipients=[user_email],
        template_body={
            "display_name": display_name,
            "verification_url": verification_url,
        },
        subtype=MessageType.plain,  # Plain text per CONTEXT.md
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message, template_name="verification.txt")
        logger.info(f"Sent verification email to {user_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification to {user_email}: {e}")
        return False
```

### Login Route with Rate Limiting and Audit
```python
# Source: Existing routes.py + SlowAPI + OWASP guidance
from .rate_limit import limiter, LOGIN_RATE_LIMIT
from .audit import log_audit_event

@router.post("/login")
@limiter.limit(LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Process login form with rate limiting."""
    templates = get_templates(request)
    db = get_db()

    # Normalize email for consistent rate limiting
    email = email.lower().strip()

    user = db.get_user_by_email(email)
    if not user:
        log_audit_event("auth.login_failure", request, details={"email": email, "reason": "unknown_email"})
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Invalid email or password",
            "email": email,
        })

    valid, new_hash = db.verify_password(user.password_hash, password)
    if not valid:
        log_audit_event("auth.login_failure", request, user_id=user.id,
                       details={"reason": "invalid_password"})
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Invalid email or password",
            "email": email,
        })

    # Rehash if needed
    if new_hash:
        db.update_user_password_hash(user.id, new_hash)

    # Create session
    token, expires_at = create_user_session(user.id)

    log_audit_event("auth.login_success", request, user_id=user.id)

    # Check if email verified
    if not user.email_verified:
        # Auto-send verification email for unverified existing users
        await send_verification_email(user.email, user.id, user.display_name)
        log_audit_event("auth.verification_sent", request, user_id=user.id,
                       details={"trigger": "unverified_login"})
        response = RedirectResponse(url="/verify-email", status_code=303)
    else:
        response = RedirectResponse(url="/", status_code=303)

    set_session_cookie(response, token, expires_at, request=request)
    return response
```

### Rate Limit Exceeded Handler
```python
# Source: CONTEXT.md (Claude's discretion on error message)
from slowapi.errors import RateLimitExceeded

async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded.

    Balance security (don't reveal exact limits) with UX (clear message).
    """
    templates = request.app.state.templates

    # For login page, return user-friendly error
    if "/login" in str(request.url):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Too many login attempts. Please try again in a few minutes.",
            "email": "",
        }, status_code=429)

    # For API/other endpoints, standard response
    return Response(
        content="Too many requests. Please try again later.",
        status_code=429,
        headers={"Retry-After": "900"}  # 15 minutes
    )
```

## Audit Event Types for This Phase

| Category | Event Type | When to Log | Details to Capture |
|----------|------------|-------------|-------------------|
| Auth | auth.login_success | Successful login | - |
| Auth | auth.login_failure | Failed login (wrong password or unknown email) | email, reason |
| Auth | auth.register | New user registration | email, display_name |
| Auth | auth.email_verified | User verified their email | - |
| Auth | auth.verification_sent | Verification email sent | trigger (registration/login/resend) |
| Auth | auth.verification_resent_auto | Auto-resent due to expired link | reason |
| Auth | auth.rate_limited | Rate limit triggered | endpoint, ip |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Email verification optional | Mandatory verification | Industry trend 2023+ | Reduces spam accounts, improves deliverability |
| IP-only rate limiting | IP + identifier composite | OWASP 2024 | Catches both distributed and targeted attacks |
| Database-stored verification tokens | Signed stateless tokens | Current best practice | No DB lookup for validation, no cleanup needed |
| Fixed lockout duration | Exponential backoff | OWASP recommendation | Better UX for typos while still blocking attacks |

**Deprecated/outdated:**
- **Verification tokens stored in database:** Use cryptographically signed tokens instead
- **IP-only brute force protection:** Must include user identifier for targeted attack protection
- **Permanent account lockout:** Prefer time-based lockout with exponential backoff

## Open Questions

Things that couldn't be fully resolved:

1. **Email template format**
   - What we know: CONTEXT.md specifies plain text, mentions "RA Tracker" in text
   - What's unclear: Exact wording/structure preferred
   - Recommendation: Keep minimal - greeting, link, expiry note, that's it

2. **Rate limit persistence across restarts**
   - What we know: In-memory storage resets on app restart
   - What's unclear: Is this acceptable for the use case?
   - Recommendation: Accept reset on restart for simplicity; attackers would need to wait anyway

3. **Multi-pod deployment**
   - What we know: In-memory rate limiting doesn't share state across pods
   - What's unclear: Current/planned deployment architecture
   - Recommendation: Start with in-memory; add Redis backend later if needed

## Sources

### Primary (HIGH confidence)
- [itsdangerous Documentation](https://itsdangerous.palletsprojects.com/en/stable/) - URLSafeTimedSerializer, max_age, SignatureExpired handling
- [SlowAPI GitHub](https://github.com/laurentS/slowapi) - FastAPI rate limiting, custom key functions
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) - Brute force protection, exponential lockout
- Existing codebase (email_sender.py, auth.py, database.py) - Patterns to extend

### Secondary (MEDIUM confidence)
- [SlowAPI Documentation](https://slowapi.readthedocs.io/) - Configuration options, storage backends
- [Authgear Login/Signup UX Guide](https://www.authgear.com/post/login-signup-ux-guide) - Rate limiting error message UX
- [SuperTokens Email Verification Flow](https://supertokens.com/blog/implementing-the-right-email-verification-flow) - UX best practices for expired links

### Tertiary (LOW confidence)
- Various Medium articles on FastAPI rate limiting - General patterns, verify with official docs
- [Email List Validation Blog](https://emaillistvalidation.com/blog/email-verification-link-expiration-ensuring-security-and-user-experience-2/) - Expiration timeframes

## Metadata

**Confidence breakdown:**
- Email verification tokens: HIGH - Extending existing itsdangerous pattern
- Rate limiting approach: HIGH - SlowAPI is well-documented, FastAPI-native
- Flow/UX decisions: HIGH - Locked in CONTEXT.md from user discussion
- Audit integration: HIGH - Existing audit infrastructure ready to extend

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days - stable security patterns)
