# Phase 7: Password Management - Research

**Researched:** 2026-02-07
**Domain:** Security (Password Strength, Reset Flow, Change Password, Session Invalidation)
**Confidence:** HIGH

## Summary

This phase implements password reset via email, authenticated password change, password strength validation, and rate limiting on reset requests. The existing codebase provides strong foundations: `itsdangerous` for signed tokens (already used for email verification), `fastapi-mail` for HTML email templates (used in Phase 6), Argon2id for password hashing, and session management in the database (`delete_user_sessions()`).

Password strength validation follows NIST SP 800-63B guidelines: minimum 8 characters, no complexity requirements, block common passwords. For the visual strength meter, use zxcvbn.js on the frontend (CDN-loaded, score 0-4 with feedback). For the server-side common password check, use a static list of 1000 common passwords from SecLists.

The key security requirement is session invalidation on password reset: call `db.delete_user_sessions(user_id)` after password update to terminate all sessions, forcing re-authentication everywhere. This prevents "ghost sessions" where an attacker maintains access after the legitimate user resets their password.

**Primary recommendation:** Extend the existing `itsdangerous` verification token pattern with `salt="password-reset"`, add a simple rate limiter class mirroring `LoginRateLimiter` (3/hour per email), use zxcvbn.js CDN for frontend strength meter, and bundle a static `common_passwords.txt` file for server-side blocking.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| itsdangerous | 2.0+ | Password reset token generation/validation | Already in use for email verification tokens |
| argon2-cffi | 23.1+ | Password hashing | Already in use (OWASP 2025 recommended) |
| zxcvbn.js | 4.4.2 | Frontend password strength meter | Dropbox-maintained, score 0-4, pattern detection |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| fastapi-mail | 1.4+ | Password reset email sending | Already in use for verification emails |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| zxcvbn.js CDN | Python zxcvbn on server | CDN avoids ~400KB bundling; server validation still checks length + common passwords |
| Static password list | API (HaveIBeenPwned) | Static list is simpler, no external dependency, covers top 1000 |
| zxcvbn Python | Custom regex scoring | zxcvbn is battle-tested, provides user feedback |

**No new dependencies required.** All libraries already in `requirements.txt`.

**Frontend addition (CDN):**
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/zxcvbn/4.4.2/zxcvbn.js"></script>
```

## Architecture Patterns

### Recommended Project Structure
```
ra_tracker/
├── web/
│   ├── password_reset.py       # Reset token generation/validation (new file)
│   ├── password_validation.py  # Strength checking, common password blocking (new file)
│   ├── rate_limit.py           # (extend with ResetRateLimiter)
│   ├── routes.py               # (extend with reset/change routes)
│   └── templates/
│       ├── password_reset_request.html  # "Enter email" form
│       ├── password_reset_form.html     # "Enter new password" form
│       ├── password_change.html         # Authenticated change form
│       └── email/
│           └── password_reset.html      # Reset email (HTML, like verification)
├── data/
│   └── common_passwords.txt    # Top 1000 common passwords (new file)
└── services/
    └── email_sender.py         # (extend with send_password_reset_email)
```

### Pattern 1: Password Reset Token (Extends Verification Pattern)
**What:** Generate secure, time-limited tokens containing user_id using itsdangerous with dedicated salt
**When to use:** Password reset requests
**Example:**
```python
# Source: Existing verification.py pattern
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from ..config import get_config

def _get_reset_serializer() -> URLSafeTimedSerializer:
    """Get serializer for password reset tokens.

    Uses dedicated salt ('password-reset') separate from verification tokens.
    """
    config = get_config()
    secret = config.app.secret_key
    if not secret:
        raise ValueError("app.secret_key not configured - required for reset tokens")
    return URLSafeTimedSerializer(secret, salt="password-reset")

def generate_reset_token(user_id: int) -> str:
    """Generate a signed password reset token for a user.

    Token is URL-safe, contains user_id, valid for 24 hours (per requirements).
    """
    serializer = _get_reset_serializer()
    return serializer.dumps({"user_id": user_id})

def verify_reset_token(token: str, max_age_hours: int = 24) -> dict:
    """Verify and decode a password reset token.

    Returns:
        Dict with 'user_id' key if valid

    Raises:
        SignatureExpired: If token has expired (>24 hours old)
        BadSignature: If token is tampered or invalid
    """
    serializer = _get_reset_serializer()
    max_age_seconds = max_age_hours * 60 * 60
    return serializer.loads(token, max_age=max_age_seconds)
```

### Pattern 2: Password Strength Validation (NIST SP 800-63B)
**What:** Server-side validation: 8 char minimum, block top 1000 common passwords
**When to use:** Registration, password change, password reset completion
**Example:**
```python
# Source: NIST SP 800-63B guidelines + CONTEXT.md decisions
from pathlib import Path
from typing import Tuple

# Load common passwords once at module import
_COMMON_PASSWORDS: set = set()

def _load_common_passwords():
    """Load common passwords list from data file."""
    global _COMMON_PASSWORDS
    password_file = Path(__file__).parent.parent / "data" / "common_passwords.txt"
    if password_file.exists():
        with open(password_file, "r", encoding="utf-8") as f:
            _COMMON_PASSWORDS = {line.strip().lower() for line in f if line.strip()}

_load_common_passwords()

def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password against NIST guidelines.

    Args:
        password: The password to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message is empty string
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    if password.lower() in _COMMON_PASSWORDS:
        return False, "This password is too common. Please choose a different one."

    return True, ""
```

### Pattern 3: Frontend Password Strength Meter (zxcvbn.js)
**What:** Visual strength indicator that updates as user types
**When to use:** Password input fields on reset and change forms
**Example:**
```html
<!-- Source: zxcvbn GitHub documentation -->
<div class="password-input-container">
    <input type="password" id="new-password" name="new_password"
           class="w-full p-3 border rounded" required minlength="8">
    <button type="button" onclick="togglePasswordVisibility()"
            class="password-toggle" aria-label="Show password">
        <svg><!-- eye icon --></svg>
    </button>
</div>

<!-- Strength meter bar -->
<div class="h-2 w-full bg-gray-200 rounded mt-2">
    <div id="strength-bar" class="h-full rounded transition-all duration-200"
         style="width: 0%;"></div>
</div>
<p id="strength-text" class="text-sm mt-1"></p>

<script src="https://cdnjs.cloudflare.com/ajax/libs/zxcvbn/4.4.2/zxcvbn.js"></script>
<script>
document.getElementById('new-password').addEventListener('input', function(e) {
    const password = e.target.value;
    const result = zxcvbn(password);

    const strengthBar = document.getElementById('strength-bar');
    const strengthText = document.getElementById('strength-text');

    // Colors: red (0-1), yellow (2), green (3-4)
    const colors = ['#ef4444', '#f59e0b', '#f59e0b', '#22c55e', '#22c55e'];
    const labels = ['Very weak', 'Weak', 'Fair', 'Strong', 'Very strong'];
    const widths = ['20%', '40%', '60%', '80%', '100%'];

    strengthBar.style.width = widths[result.score];
    strengthBar.style.backgroundColor = colors[result.score];
    strengthText.textContent = labels[result.score];
    strengthText.style.color = colors[result.score];

    // Show zxcvbn feedback if score is low
    if (result.score <= 2 && result.feedback.warning) {
        strengthText.textContent += ': ' + result.feedback.warning;
    }
});
</script>
```

### Pattern 4: Session Invalidation on Password Reset
**What:** Delete all user sessions after password reset/change
**When to use:** After successful password update
**Example:**
```python
# Source: OWASP Session Management Cheat Sheet + existing database.py
from ..database import get_db

def reset_password_and_invalidate_sessions(user_id: int, new_password: str) -> None:
    """Reset password and invalidate all existing sessions.

    Critical security: Ensures attacker loses access after password reset.
    User must re-login after password change.
    """
    db = get_db()

    # Hash new password with Argon2id
    from argon2 import PasswordHasher
    hasher = PasswordHasher()
    new_hash = hasher.hash(new_password)

    # Update password
    db.update_user_password_hash(user_id, new_hash)

    # Invalidate ALL sessions for this user
    # Existing method in database.py: delete_user_sessions(user_id)
    db.delete_user_sessions(user_id)
```

### Pattern 5: Reset Rate Limiter (Mirrors LoginRateLimiter)
**What:** Track reset requests per email, limit to 3/hour
**When to use:** Password reset request endpoint
**Example:**
```python
# Source: Existing rate_limit.py LoginRateLimiter pattern
import time
import hashlib
from typing import Optional

class ResetRateLimiter:
    """Rate limiter for password reset requests - tracks by email only.

    3 requests per hour per email (per SEC-02).
    Uses email hash for privacy (same pattern as LoginRateLimiter).
    """

    def __init__(self, max_requests: int = 3, window_minutes: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_minutes * 60
        self._attempts: dict[str, list[float]] = {}

    def _hash_email(self, email: str) -> str:
        normalized = email.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _clean_old_attempts(self, key: str, current_time: float) -> None:
        if key in self._attempts:
            cutoff = current_time - self.window_seconds
            self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]
            if not self._attempts[key]:
                del self._attempts[key]

    def check_rate_limit(self, email: str) -> tuple[bool, Optional[str]]:
        """Check if reset request is allowed.

        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
        """
        current_time = time.time()
        key = f"reset:email:{self._hash_email(email)}"

        self._clean_old_attempts(key, current_time)
        count = len(self._attempts.get(key, []))

        if count >= self.max_requests:
            return False, "email"
        return True, None

    def record_request(self, email: str) -> None:
        """Record a reset request."""
        current_time = time.time()
        key = f"reset:email:{self._hash_email(email)}"

        if key not in self._attempts:
            self._attempts[key] = []
        self._attempts[key].append(current_time)

# Global instance
reset_limiter = ResetRateLimiter()
```

### Anti-Patterns to Avoid
- **Revealing email existence on reset request:** Always show "If account exists, email sent" regardless of whether email is registered
- **Not invalidating sessions on reset:** Attacker maintains access via stolen session even after password change
- **Complexity requirements:** NIST explicitly recommends AGAINST requiring uppercase/numbers/symbols
- **Storing reset tokens in database:** Use signed tokens - no DB storage, no cleanup needed
- **Confirm password field:** Single field + show/hide toggle is modern UX (per CONTEXT.md)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password strength estimation | Regex rules (1 upper, 1 number, etc) | zxcvbn.js | Detects patterns, dictionary words, keyboard sequences |
| Reset token signing | Manual base64 + timestamp | itsdangerous URLSafeTimedSerializer | Cryptographic signature, timing-attack resistant |
| Password hashing | bcrypt, SHA256, custom | Argon2id (already in use) | OWASP 2025 recommended, memory-hard |
| Common password list | Download at runtime | Static bundled file | No external dependency, fast startup |
| Rate limiting | Manual dict with cleanup | Extend existing LoginRateLimiter | Consistent pattern, already tested |

**Key insight:** The existing codebase has 90% of what's needed. Token generation is identical to verification. Session invalidation already exists. Just wire up new routes.

## Common Pitfalls

### Pitfall 1: Ghost Sessions After Password Reset
**What goes wrong:** Attacker who stole session cookie maintains access after user resets password
**Why it happens:** Password updated but sessions not invalidated
**How to avoid:** Call `db.delete_user_sessions(user_id)` immediately after password update
**Warning signs:** User reports suspicious activity after password reset

### Pitfall 2: Email Enumeration via Reset Form
**What goes wrong:** Different error messages reveal whether email is registered
**Why it happens:** "Email not found" vs "Reset email sent" are distinguishable
**How to avoid:** Always show "If an account exists with that email, we've sent a reset link"
**Warning signs:** Security audit flags user enumeration vulnerability

### Pitfall 3: Reusing Reset Token
**What goes wrong:** Same reset link can be used multiple times
**Why it happens:** Token not invalidated after successful reset
**How to avoid:** Check that token's user_id matches a user who hasn't changed password since token was issued
**Warning signs:** Audit log shows multiple password resets from same token

### Pitfall 4: Complexity Requirements Counter to NIST
**What goes wrong:** Users create predictable passwords like "Password1!"
**Why it happens:** Forced complexity leads to predictable patterns
**How to avoid:** Enforce length (8+ chars) and block common passwords only - no complexity requirements
**Warning signs:** User complaints, predictable password patterns in breaches

### Pitfall 5: Rate Limit Bypass via Email Normalization
**What goes wrong:** "user@example.com" and "USER@EXAMPLE.COM" treated as different for rate limiting
**Why it happens:** Case-sensitive comparison
**How to avoid:** Normalize email (lowercase, strip whitespace) before hashing for rate limit key
**Warning signs:** Rate limit bypassed with case variations

### Pitfall 6: Missing CSRF on Password Change Form
**What goes wrong:** Attacker can change victim's password via CSRF
**Why it happens:** Password change form missing CSRF token
**How to avoid:** Include CSRF token field (existing csrf_field() template helper)
**Warning signs:** Security scan flags missing CSRF protection

## Code Examples

Verified patterns from official sources and existing codebase:

### Password Reset Email Template (HTML)
```html
<!-- Source: Matching verification.html pattern from Phase 6 -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset Your Password</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background: #f8f9fa; border-radius: 8px; padding: 30px; margin-bottom: 20px;">
    <h1 style="color: #1a1a1a; margin: 0 0 20px 0; font-size: 24px;">Reset your password</h1>

    <p style="margin: 0 0 20px 0;">Hi,</p>

    <p style="margin: 0 0 20px 0;">Click the button below to reset your password:</p>

    <div style="text-align: center; margin: 30px 0;">
      <a href="{{ reset_url }}"
         style="background: #2563eb; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 500;">
        Reset Password
      </a>
    </div>

    <p style="margin: 0 0 10px 0; font-size: 14px; color: #666;">
      Or copy and paste this link into your browser:
    </p>
    <p style="margin: 0 0 20px 0; font-size: 14px; word-break: break-all;">
      <a href="{{ reset_url }}" style="color: #2563eb;">{{ reset_url }}</a>
    </p>

    <p style="margin: 0; font-size: 14px; color: #666;">
      This link will expire in 24 hours.
    </p>
  </div>

  <p style="font-size: 12px; color: #999; margin: 0;">
    If you didn't request this, you can safely ignore this email. Your password won't change.
  </p>

  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">

  <p style="font-size: 12px; color: #999; margin: 0;">
    RA Tracker
  </p>
</body>
</html>
```

### Send Password Reset Email Function
```python
# Source: Existing send_verification_email pattern
async def send_password_reset_email(
    user_email: str,
    user_id: int,
) -> bool:
    """Send password reset email with secure token link.

    Args:
        user_email: Recipient email address
        user_id: User ID for token generation

    Returns:
        True if sent successfully, False otherwise
    """
    conf = _get_email_config()
    if not conf:
        logger.warning("Email not configured, skipping reset email send")
        return False

    # Import here to avoid circular imports
    from ..web.password_reset import generate_reset_token

    config = get_config()
    token = generate_reset_token(user_id)
    reset_url = f"{config.app.base_url}/reset-password/{token}"

    message = MessageSchema(
        subject="Reset your password",  # Simple, not branded (per CONTEXT.md)
        recipients=[user_email],
        template_body={
            "reset_url": reset_url,
        },
        subtype=MessageType.html,
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message, template_name="password_reset.html")
        logger.info(f"Sent password reset email to {user_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email to {user_email}: {e}")
        return False
```

### Password Change Route (Authenticated)
```python
# Source: OWASP guidelines + existing route patterns
@router.post("/settings/change-password")
async def change_password(
    request: Request,
    user: User = Depends(require_verified_email),
    current_password: str = Form(...),
    new_password: str = Form(...),
):
    """Change password for authenticated user."""
    templates = get_templates(request)
    db = get_db()

    # Verify current password
    valid, _ = db.verify_password(user.password_hash, current_password)
    if not valid:
        log_audit_event("password.change_failure", request, user_id=user.id,
                       details={"reason": "invalid_current_password"})
        return templates.TemplateResponse("password_change.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Current password is incorrect",
        })

    # Validate new password
    is_valid, error_msg = validate_password(new_password)
    if not is_valid:
        return templates.TemplateResponse("password_change.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": error_msg,
        })

    # Update password and invalidate other sessions
    from argon2 import PasswordHasher
    hasher = PasswordHasher()
    new_hash = hasher.hash(new_password)
    db.update_user_password_hash(user.id, new_hash)

    # DON'T invalidate current session on change - only on reset
    # User just proved they know their password

    log_audit_event("password.change_success", request, user_id=user.id)

    # Flash success message (redirect to same page)
    return templates.TemplateResponse("password_change.html", {
        "request": request,
        "csrf_token": getattr(request.state, 'csrf_token', ''),
        "success": "Password updated successfully",
    })
```

### Password Reset Request Route
```python
# Source: OWASP + existing patterns
from .rate_limit import reset_limiter

@router.post("/forgot-password")
async def request_password_reset(
    request: Request,
    email: str = Form(...),
):
    """Request password reset email."""
    templates = get_templates(request)
    db = get_db()

    # Normalize email
    email = email.lower().strip()

    # Check rate limit BEFORE looking up user (timing attack prevention)
    allowed, reason = reset_limiter.check_rate_limit(email)
    if not allowed:
        log_audit_event("password.reset_rate_limited", request,
                       details={"email_hash": hashlib.sha256(email.encode()).hexdigest()[:16]})
        return templates.TemplateResponse("password_reset_request.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Too many requests. Try again later.",  # Vague per CONTEXT.md
        })

    # Record request (for rate limiting) regardless of user existence
    reset_limiter.record_request(email)

    # Look up user
    user = db.get_user_by_email(email)

    # Always show success message (don't reveal if email exists)
    if user:
        await send_password_reset_email(user.email, user.id)
        log_audit_event("password.reset_requested", request, user_id=user.id)
    else:
        # Log attempt but don't reveal to user
        log_audit_event("password.reset_unknown_email", request,
                       details={"email_hash": hashlib.sha256(email.encode()).hexdigest()[:16]})

    return templates.TemplateResponse("password_reset_request.html", {
        "request": request,
        "csrf_token": getattr(request.state, 'csrf_token', ''),
        "success": "If an account exists with that email, we've sent a reset link.",
    })
```

### Password Reset Completion Route
```python
# Source: OWASP + existing patterns
@router.post("/reset-password/{token}")
async def complete_password_reset(
    request: Request,
    token: str,
    new_password: str = Form(...),
):
    """Complete password reset with new password."""
    templates = get_templates(request)
    db = get_db()

    # Validate token
    try:
        data = verify_reset_token(token)
        user_id = data["user_id"]
    except SignatureExpired:
        return templates.TemplateResponse("password_reset_form.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "This reset link has expired.",
            "show_request_new": True,
        })
    except BadSignature:
        return templates.TemplateResponse("password_reset_form.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Invalid reset link.",
        })

    # Validate new password
    is_valid, error_msg = validate_password(new_password)
    if not is_valid:
        return templates.TemplateResponse("password_reset_form.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "token": token,  # Preserve token for retry
            "error": error_msg,
        })

    # Get user
    user = db.get_user_by_id(user_id)
    if not user:
        return templates.TemplateResponse("password_reset_form.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "User not found.",
        })

    # Update password
    from argon2 import PasswordHasher
    hasher = PasswordHasher()
    new_hash = hasher.hash(new_password)
    db.update_user_password_hash(user_id, new_hash)

    # CRITICAL: Invalidate ALL sessions (security - assume password was compromised)
    db.delete_user_sessions(user_id)

    log_audit_event("password.reset_completed", request, user_id=user_id)

    # Redirect to login with success message
    return RedirectResponse(
        url="/login?message=Password updated. Please log in.",
        status_code=303
    )
```

## Audit Event Types for This Phase

| Category | Event Type | When to Log | Details to Capture |
|----------|------------|-------------|-------------------|
| Password | password.reset_requested | Reset request received (user exists) | - |
| Password | password.reset_unknown_email | Reset request for non-existent email | email_hash |
| Password | password.reset_completed | Password successfully reset | - |
| Password | password.reset_rate_limited | Rate limit exceeded | email_hash |
| Password | password.change_success | Password changed via settings | - |
| Password | password.change_failure | Password change failed | reason |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Complexity requirements | Length + blocklist only | NIST 800-63B (2024 superseded by 800-63-4, Aug 2025) | Better passwords, less user friction |
| DB-stored reset tokens | Signed stateless tokens | Current best practice | No cleanup, no DB lookup |
| IP-only rate limiting | Email-based for reset | Current best practice | Prevents targeted attacks |
| Leave sessions after reset | Invalidate all sessions | OWASP recommendation | Cuts off attacker access |

**Deprecated/outdated:**
- **Complexity requirements (uppercase, numbers, symbols):** Leads to predictable patterns
- **Password confirmation field:** Single field + show/hide toggle preferred
- **Knowledge-based recovery questions:** Easily socially engineered

## Open Questions

Things that couldn't be fully resolved:

1. **Common password list size**
   - What we know: CONTEXT.md says "top 1000", SecLists has 10k-most-common.txt
   - What's unclear: Exact file to use (1000 vs 10000)
   - Recommendation: Start with 1000 (faster validation, covers most common), can expand later

2. **Password change session behavior**
   - What we know: Reset invalidates all sessions; change requires current password
   - What's unclear: Should change also invalidate other sessions?
   - Recommendation: Only invalidate on reset (user proved identity via current password on change)

## Sources

### Primary (HIGH confidence)
- [NIST SP 800-63B](https://pages.nist.gov/800-63-3/sp800-63b.html) - Password guidelines (superseded by 800-63-4 Aug 2025)
- [zxcvbn PyPI](https://pypi.org/project/zxcvbn/) - Python package v4.5.0 (Feb 2025)
- [zxcvbn GitHub](https://github.com/dropbox/zxcvbn) - JavaScript library, CDN usage
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) - Session invalidation requirements
- Existing codebase: verification.py, rate_limit.py, auth.py, database.py

### Secondary (MEDIUM confidence)
- [SecLists Common Credentials](https://github.com/danielmiessler/SecLists/tree/master/Passwords/Common-Credentials) - Password blocklists
- [HIPAA Journal NIST Update](https://www.hipaajournal.com/nist-password-guidelines-update-2024/) - NIST changes summary
- [Authgear Password Reset Best Practices](https://www.authgear.com/post/authentication-security-password-reset-best-practices-and-more) - Flow patterns

### Tertiary (LOW confidence)
- Medium articles on ghost sessions and password reset flows - General patterns, verify with official docs

## Metadata

**Confidence breakdown:**
- Password reset tokens: HIGH - Identical to existing verification token pattern
- Password strength (NIST): HIGH - Official NIST guidelines, widely documented
- Session invalidation: HIGH - OWASP explicit recommendation, existing method in database.py
- Rate limiting: HIGH - Extends existing LoginRateLimiter pattern
- zxcvbn frontend: HIGH - Official Dropbox documentation, CDN available

**Research date:** 2026-02-07
**Valid until:** 2026-03-07 (30 days - stable security patterns)
