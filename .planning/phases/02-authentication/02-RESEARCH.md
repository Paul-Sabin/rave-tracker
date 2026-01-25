# Phase 2: Authentication - Research

**Researched:** 2026-01-25
**Domain:** FastAPI Authentication, Session Management, Tailwind CSS Mobile UI
**Confidence:** HIGH

## Summary

This phase implements user authentication (registration, login, logout with secure sessions) and migrates the existing UI to Tailwind CSS with mobile-first responsive design. The app is built on FastAPI with Jinja2 templates (not Flask as initially assumed), which provides clean patterns for dependency injection-based route protection.

Key findings:
- FastAPI provides native support for cookie-based session authentication via Starlette's response cookies with `httponly`, `secure`, and `samesite` flags
- Session storage should be database-backed (SQLite sessions table) for persistence across server restarts
- Tailwind CSS v4 via CDN supports custom theme colors using the `@theme` directive
- Password hashing with argon2-cffi (already implemented in Phase 1) is OWASP-recommended
- Touch targets must be minimum 44x44px for mobile accessibility (WCAG AAA)

**Primary recommendation:** Implement custom database-backed session storage with secure cookie tokens (using `secrets.token_urlsafe(32)`), FastAPI dependency injection for route protection, and Tailwind CSS v4 CDN for mobile-first UI migration.

## Standard Stack

The established libraries/tools for this domain:

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | current | Web framework | Already in use, excellent dependency injection |
| argon2-cffi | 25.1.0 | Password hashing | OWASP 2025 recommended, already implemented in Phase 1 |
| Jinja2 | current | Template engine | Already in use with FastAPI |

### Supporting (To Add)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Tailwind CSS v4 | 4.x | Utility-first CSS | CDN for development, all templates |
| secrets (stdlib) | Python 3.8+ | Secure token generation | Session token creation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom session store | starsessions | Adds dependency, but we already have SQLite and simple needs |
| Tailwind CDN | Build pipeline | CDN is fine for this app size, production builds add complexity |
| Database sessions | Redis | Overkill for personal tracker with few users |

**No additional packages required.** FastAPI/Starlette response cookies and Python stdlib `secrets` provide everything needed.

## Architecture Patterns

### Recommended Project Structure
```
ra_tracker/
├── web/
│   ├── app.py              # Add session middleware configuration
│   ├── routes.py           # Add auth routes, protection dependencies
│   ├── auth.py             # NEW: Authentication logic (session CRUD, dependencies)
│   └── templates/
│       ├── base.html       # Migrate to Tailwind, add hamburger nav
│       ├── login.html      # NEW: Login form
│       ├── register.html   # NEW: Registration with consent
│       ├── privacy.html    # NEW: Privacy policy page
│       ├── dashboard.html  # Migrate to Tailwind, add mobile support
│       ├── rules.html      # Migrate to Tailwind, add mobile support
│       └── settings.html   # Migrate to Tailwind, add mobile support
├── database.py             # Add sessions table, session CRUD
└── config.py               # Add session timeout config
```

### Pattern 1: Database-Backed Session Store
**What:** Store session tokens in SQLite, use secure cookies to reference them
**When to use:** Always for web app authentication with persistence requirements

Sessions table schema:
```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,        -- session token (secrets.token_urlsafe(32))
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
```

### Pattern 2: FastAPI Dependency Injection for Route Protection
**What:** Create `get_current_user` dependency that validates session and returns user
**When to use:** All protected routes

```python
# Source: FastAPI official patterns
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

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
        # For browser requests, redirect to login
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return user
```

### Pattern 3: Secure Cookie Configuration
**What:** Set session cookies with security flags
**When to use:** Login response, session refresh

```python
# Source: Starlette official documentation
response.set_cookie(
    key="session_token",
    value=token,
    max_age=session_timeout_seconds,  # From config
    httponly=True,      # Prevents JavaScript access (XSS protection)
    secure=True,        # Only send over HTTPS (set False for local dev)
    samesite="lax",     # CSRF protection, allows top-level navigation
    path="/"            # Available to all routes
)
```

### Pattern 4: Tailwind CSS v4 CDN Setup
**What:** Add Tailwind via CDN with custom theme colors
**When to use:** base.html template

```html
<!-- Source: Tailwind CSS v4 official docs -->
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
<style type="text/tailwindcss">
  @theme {
    --color-bg-dark: #1a1a2e;
    --color-bg-card: #16213e;
    --color-accent: #e94560;
    --color-accent-hover: #ff6b6b;
    --color-text: #eeeeee;
    --color-text-muted: #aaaaaa;
    --color-success: #4ecca3;
    --color-border: #2a2a4e;
  }
</style>
```

### Pattern 5: Mobile Hamburger Navigation
**What:** Responsive nav with hamburger menu on mobile
**When to use:** base.html navigation

```html
<!-- Desktop nav visible md:flex, hidden on mobile -->
<nav class="hidden md:flex gap-4">...</nav>

<!-- Hamburger button visible on mobile, hidden md:hidden -->
<button class="md:hidden" onclick="toggleMobileNav()">
  <svg class="w-6 h-6"><!-- hamburger icon --></svg>
</button>

<!-- Mobile nav panel (slide-in or dropdown) -->
<div id="mobile-nav" class="hidden md:hidden">...</div>
```

### Anti-Patterns to Avoid
- **Storing passwords in cookies:** Never. Only store session tokens that reference server-side data.
- **Using Starlette SessionMiddleware for auth:** It stores session data in encrypted cookies, not suitable for session revocation or audit trails.
- **JWT for browser-based auth:** Cookies with httponly are more secure against XSS than localStorage JWTs.
- **Pre-ticked consent checkboxes:** Violates GDPR, must be explicit opt-in.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom hash function | argon2-cffi PasswordHasher | Timing attacks, algorithm weaknesses |
| Secure tokens | uuid.uuid4() | secrets.token_urlsafe(32) | uuid4 is predictable, not cryptographically secure |
| Cookie security | Manual flag setting | response.set_cookie() params | Easy to miss flags, consistent API |
| Session expiration | Cron job cleanup | Query with expires_at filter | Simple, reliable, no extra process |
| Responsive breakpoints | Custom media queries | Tailwind responsive prefixes | Consistent, well-tested breakpoints |

**Key insight:** Session management looks simple but has many security edge cases (timing attacks on comparison, token predictability, cookie flags). Use stdlib `secrets` and framework-provided cookie methods.

## Common Pitfalls

### Pitfall 1: Session Fixation
**What goes wrong:** Attacker obtains session token before user logs in, then hijacks session after login
**Why it happens:** Same session token used before and after authentication
**How to avoid:** Generate NEW session token on login, delete any existing pre-auth session
**Warning signs:** Session token same before and after login form submission

### Pitfall 2: Insecure Cookie Defaults
**What goes wrong:** Session cookies accessible to JavaScript (XSS) or sent over HTTP
**Why it happens:** Forgetting httponly, secure, samesite flags
**How to avoid:** Always set all three flags; secure=False only for localhost development
**Warning signs:** Can read cookie in browser DevTools console

### Pitfall 3: Timing Attacks on Token Comparison
**What goes wrong:** Attacker deduces valid tokens by measuring response times
**Why it happens:** String comparison short-circuits on first mismatch
**How to avoid:** Use `secrets.compare_digest()` for token comparison
**Warning signs:** Using `==` to compare session tokens

### Pitfall 4: Session Cleanup on Logout
**What goes wrong:** Deleted session still works for a period
**Why it happens:** Only clearing cookie, not server-side session record
**How to avoid:** Delete session from database AND clear cookie on logout
**Warning signs:** Can continue using session token after logout

### Pitfall 5: Mobile Tap Target Too Small
**What goes wrong:** Users can't tap buttons accurately on mobile
**Why it happens:** Using desktop-sized padding on touch interfaces
**How to avoid:** Minimum 44x44px tap targets (WCAG AAA), use Tailwind `min-h-11 min-w-11`
**Warning signs:** Filter buttons, notification toggles, small form elements

### Pitfall 6: Consent Checkbox Pre-Ticked
**What goes wrong:** GDPR non-compliance
**Why it happens:** Developer convenience or oversight
**How to avoid:** Checkbox starts unchecked, form validation requires it ticked
**Warning signs:** Checkbox has `checked` attribute in HTML

## Code Examples

Verified patterns from official sources:

### Secure Session Token Generation
```python
# Source: Python secrets module documentation
import secrets

def create_session_token() -> str:
    """Generate cryptographically secure session token.

    32 bytes = 256 bits of randomness, exceeds OWASP minimum.
    Base64 encoding results in ~43 character URL-safe string.
    """
    return secrets.token_urlsafe(32)
```

### Password Verification with Rehash Support
```python
# Source: argon2-cffi documentation
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

def verify_password(stored_hash: str, password: str) -> tuple[bool, Optional[str]]:
    """Verify password, return (success, new_hash_if_rehash_needed)."""
    try:
        ph.verify(stored_hash, password)
        # Check if parameters changed and rehash needed
        if ph.check_needs_rehash(stored_hash):
            return True, ph.hash(password)
        return True, None
    except VerifyMismatchError:
        return False, None
```

### FastAPI Login Route with Secure Cookie
```python
# Source: FastAPI + Starlette documentation
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

router = APIRouter()

@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    db = get_db()
    user = db.get_user_by_email(email)

    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid email or password"
        })

    valid, new_hash = db.verify_password(user.password_hash, password)
    if not valid:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid email or password"
        })

    # Rehash if needed (algorithm upgrade)
    if new_hash:
        db.update_user_password_hash(user.id, new_hash)

    # Create new session (prevents session fixation)
    token = create_session_token()
    db.create_session(user.id, token, expires_in_days=30)  # From config

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=30 * 24 * 60 * 60,  # 30 days in seconds
        httponly=True,
        secure=request.url.scheme == "https",  # True for HTTPS
        samesite="lax",
        path="/"
    )
    return response
```

### Registration Form with Consent Validation (Jinja2 + JavaScript)
```html
<!-- Source: GDPR compliance best practices -->
<form method="post" action="/register" id="register-form">
    <div class="mb-4">
        <label for="email">Email</label>
        <input type="email" id="email" name="email" required
               class="w-full p-3 min-h-11 rounded border border-border bg-bg-dark text-text">
    </div>

    <div class="mb-4">
        <label for="password">Password</label>
        <div class="relative">
            <input type="password" id="password" name="password" required minlength="8"
                   class="w-full p-3 min-h-11 rounded border border-border bg-bg-dark text-text">
            <button type="button" onclick="togglePassword()"
                    class="absolute right-3 top-1/2 -translate-y-1/2">
                Show
            </button>
        </div>
        <p class="text-sm text-text-muted mt-1">Minimum 8 characters</p>
    </div>

    <div class="mb-4">
        <label for="display_name">Display Name</label>
        <input type="text" id="display_name" name="display_name" required
               class="w-full p-3 min-h-11 rounded border border-border bg-bg-dark text-text">
    </div>

    <!-- CONSENT CHECKBOX - MUST NOT BE PRE-TICKED -->
    <div class="mb-4 flex items-start gap-3">
        <input type="checkbox" id="consent" name="consent" required
               class="mt-1 w-5 h-5 min-w-5 min-h-5">
        <label for="consent" class="text-sm">
            I have read and agree to the
            <a href="/privacy" target="_blank" class="text-accent underline">Privacy Policy</a>
        </label>
    </div>

    <button type="submit" id="submit-btn"
            class="w-full p-3 min-h-11 bg-accent text-white rounded font-semibold
                   hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed">
        Create Account
    </button>
</form>

<script>
// Disable submit until consent is checked
const consent = document.getElementById('consent');
const submitBtn = document.getElementById('submit-btn');

consent.addEventListener('change', () => {
    submitBtn.disabled = !consent.checked;
});
submitBtn.disabled = !consent.checked;  // Initial state

function togglePassword() {
    const pwd = document.getElementById('password');
    pwd.type = pwd.type === 'password' ? 'text' : 'password';
}
</script>
```

### Tailwind Mobile-First Navigation
```html
<!-- Source: Tailwind responsive patterns -->
<nav class="bg-bg-card border-b border-border">
    <div class="max-w-7xl mx-auto px-4">
        <div class="flex justify-between items-center h-16">
            <!-- Logo -->
            <a href="/" class="text-xl font-bold text-accent">RA Tracker</a>

            <!-- Desktop nav (hidden on mobile) -->
            <div class="hidden md:flex items-center gap-4">
                <a href="/" class="px-4 py-2 rounded hover:bg-accent">Dashboard</a>
                <a href="/rules" class="px-4 py-2 rounded hover:bg-accent">Rules</a>
                <a href="/settings" class="px-4 py-2 rounded hover:bg-accent">Settings</a>
                {% if user %}
                <span class="text-text-muted">{{ user.display_name }}</span>
                <form action="/logout" method="post" class="inline">
                    <button type="submit" class="px-4 py-2 rounded hover:bg-accent">Logout</button>
                </form>
                {% endif %}
            </div>

            <!-- Hamburger (visible on mobile) -->
            <button id="hamburger" class="md:hidden p-2 min-w-11 min-h-11 flex items-center justify-center"
                    onclick="document.getElementById('mobile-nav').classList.toggle('hidden')">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
            </button>
        </div>

        <!-- Mobile nav panel -->
        <div id="mobile-nav" class="hidden md:hidden pb-4 space-y-2">
            <a href="/" class="block px-4 py-3 min-h-11 rounded hover:bg-accent">Dashboard</a>
            <a href="/rules" class="block px-4 py-3 min-h-11 rounded hover:bg-accent">Rules</a>
            <a href="/settings" class="block px-4 py-3 min-h-11 rounded hover:bg-accent">Settings</a>
            {% if user %}
            <div class="border-t border-border pt-2 mt-2">
                <span class="block px-4 py-2 text-text-muted">{{ user.display_name }}</span>
                <form action="/logout" method="post">
                    <button type="submit" class="block w-full text-left px-4 py-3 min-h-11 rounded hover:bg-accent">
                        Logout
                    </button>
                </form>
            </div>
            {% endif %}
        </div>
    </div>
</nav>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JWT in localStorage | httponly cookies | 2023+ | Better XSS protection |
| MD5/SHA password hash | Argon2id | 2015+ (now standard) | Resistant to GPU attacks |
| tailwind.config.js | @theme CSS directive | Tailwind v4 (2024) | No build step needed for CDN |
| SameSite default "none" | SameSite default "lax" | Chrome 80 (2020) | CSRF protection by default |
| 24px min tap target | 44px recommended | WCAG 2.2 (2023) | Better mobile accessibility |

**Deprecated/outdated:**
- `bcrypt`: Still works but Argon2id is OWASP 2025 recommended
- `tailwind.config.js` for CDN: Use `@theme` directive in v4
- `secrets.token_hex()`: Prefer `token_urlsafe()` for shorter tokens

## Open Questions

Things that couldn't be fully resolved:

1. **Session table cleanup strategy**
   - What we know: Need to delete expired sessions periodically
   - What's unclear: Run as part of login check or separate scheduled task?
   - Recommendation: Check on session validation, delete expired sessions lazily (no separate task needed for small user base)

2. **Sliding session expiration implementation**
   - What we know: Session timeout should reset on activity
   - What's unclear: Update database on every request or batch?
   - Recommendation: Update expires_at on significant actions (page loads), not API calls to avoid excessive writes

## Sources

### Primary (HIGH confidence)
- [FastAPI Response Cookies](https://fastapi.tiangolo.com/advanced/response-cookies/) - Cookie setting API
- [Starlette set_cookie()](https://www.starlette.io/responses/) - All cookie parameters documented
- [Tailwind CSS v4 Play CDN](https://tailwindcss.com/docs/installation/play-cdn) - CDN setup and @theme directive
- [Python secrets module](https://docs.python.org/3/library/secrets.html) - Token generation (32 bytes standard)
- [argon2-cffi documentation](https://argon2-cffi.readthedocs.io/) - Password hashing API

### Secondary (MEDIUM confidence)
- [WCAG 2.5.8 Target Size](https://www.w3.org/WAI/WCAG21/Understanding/target-size.html) - 44px mobile tap targets
- [FastAPI dependency injection patterns](https://fastapi.tiangolo.com/tutorial/dependencies/) - get_current_user pattern
- [GDPR consent requirements](https://termly.io/resources/articles/gdpr-consent-examples/) - Checkbox must not be pre-ticked

### Tertiary (LOW confidence)
- Various blog posts on mobile hamburger menu implementations (patterns validated against Tailwind docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Uses existing FastAPI/argon2-cffi, stdlib secrets, official Tailwind CDN
- Architecture: HIGH - Based on FastAPI official patterns and Starlette documentation
- Pitfalls: HIGH - Well-documented security concerns (OWASP, WCAG, GDPR)
- UI migration: MEDIUM - Tailwind v4 CDN is newer, but official docs are clear

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (30 days - stable technologies, Tailwind v4 is released)
