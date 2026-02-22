# Phase 5: Audit Foundation & CSRF Protection - Research

**Researched:** 2026-02-02
**Domain:** Security (CSRF Protection, Audit Logging)
**Confidence:** HIGH

## Summary

This phase establishes two foundational security features: CSRF protection for all POST forms and audit logging infrastructure. The existing codebase uses FastAPI with Jinja2 templates, session-based authentication with httponly cookies, and AJAX form submissions via fetch() to preserve scroll position.

For CSRF protection, the recommended approach is the Double Submit Cookie pattern using `starlette-csrf` or a lightweight custom middleware. The key challenge is supporting both traditional form submissions AND AJAX fetch() calls with the same token mechanism.

For audit logging, a simple SQLite table with flexible JSON details column provides the required functionality while remaining queryable. The schema must capture event_type, user_id, ip_address, timestamp, and flexible details without auto-purge (AUDIT-10 requirement).

**Primary recommendation:** Use a custom CSRF middleware with Double Submit Cookie pattern that accepts tokens from either headers (for AJAX) or form body (for regular forms), plus a dedicated audit_logs table with JSON details column.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python secrets | stdlib | CSRF token generation | Cryptographically secure, no dependencies |
| Python hmac | stdlib | Token signing | Standard for HMAC-based signed tokens |
| Python json | stdlib | Audit details serialization | Built-in, sufficient for SQLite JSON storage |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| starlette-csrf | 3.0+ | CSRF middleware | If wanting pre-built solution with sensitive_cookies support |
| fastapi-csrf-protect | 1.0+ | Alternative CSRF | If needing flexible header/body acceptance |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom middleware | starlette-csrf | Pre-built vs. simpler/fewer deps for this use case |
| JSON details column | Separate columns | Flexibility vs. queryability (JSON sufficient for audit) |
| SQLite audit table | Separate audit DB | Simplicity vs. separation (single DB ok for this scale) |

**Installation:**
```bash
# No additional packages required - using stdlib
# Optional if preferring pre-built:
pip install starlette-csrf
```

## Architecture Patterns

### Recommended Project Structure
```
ra_tracker/
├── web/
│   ├── csrf.py          # CSRF middleware and utilities
│   ├── audit.py         # Audit logging service
│   └── routes.py        # (existing - add CSRF token to templates)
├── database.py          # (add audit_logs table)
└── templates/
    └── base.html        # (add CSRF token global, JS helper)
```

### Pattern 1: Double Submit Cookie for CSRF
**What:** Generate CSRF token, set in cookie AND make available to forms/JS. Validate by comparing cookie value to submitted value (header or body).
**When to use:** Session-based auth with forms and AJAX
**Example:**
```python
# Source: OWASP CSRF Prevention Cheat Sheet + starlette-csrf pattern
import secrets
import hmac
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, secret_key: str, cookie_name: str = "csrftoken",
                 header_name: str = "x-csrftoken", form_field: str = "csrf_token",
                 safe_methods: set = {"GET", "HEAD", "OPTIONS", "TRACE"}):
        super().__init__(app)
        self.secret_key = secret_key
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.form_field = form_field
        self.safe_methods = safe_methods

    async def dispatch(self, request: Request, call_next):
        # Generate or retrieve CSRF token
        csrf_cookie = request.cookies.get(self.cookie_name)
        if not csrf_cookie:
            csrf_token = secrets.token_urlsafe(32)
        else:
            csrf_token = csrf_cookie

        # Store token in request.state for template access
        request.state.csrf_token = csrf_token

        # Validate on unsafe methods
        if request.method not in self.safe_methods:
            # Check header first (AJAX), then form body
            submitted = request.headers.get(self.header_name)
            if not submitted:
                # Try form body - requires reading form data
                # (implementation detail: may need to cache body)
                pass

            if not hmac.compare_digest(csrf_cookie or "", submitted or ""):
                return Response("CSRF validation failed", status_code=403)

        response = await call_next(request)

        # Set cookie on response if new token
        if not csrf_cookie:
            response.set_cookie(
                key=self.cookie_name,
                value=csrf_token,
                httponly=False,  # JS needs to read it for AJAX
                samesite="lax",
                secure=request.url.scheme == "https",
                path="/"
            )

        return response
```

### Pattern 2: Audit Logging Service
**What:** Centralized audit logging function that writes to audit_logs table
**When to use:** Any security-relevant action (login, logout, rule changes, settings changes)
**Example:**
```python
# Source: Enterprise audit logging best practices
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request

def log_audit_event(
    event_type: str,
    user_id: Optional[int],
    request: Request,
    details: Optional[Dict[str, Any]] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
) -> None:
    """Log an audit event to the database.

    Args:
        event_type: Category.action format (e.g., 'auth.login', 'rule.create')
        user_id: User who triggered event (None for anonymous)
        request: FastAPI request for IP extraction
        details: Additional context as JSON-serializable dict
        target_type: Type of resource affected (e.g., 'rule', 'user')
        target_id: ID of affected resource
    """
    ip_address = request.client.host if request.client else None

    db = get_db()
    db.add_audit_log(
        event_type=event_type,
        user_id=user_id,
        ip_address=ip_address,
        details=json.dumps(details) if details else None,
        target_type=target_type,
        target_id=target_id,
    )
```

### Pattern 3: CSRF Token in Jinja2 Templates + AJAX
**What:** Make CSRF token available globally in templates, include in forms and AJAX headers
**When to use:** All forms and AJAX POST/PUT/DELETE requests
**Example:**
```html
<!-- base.html - Add to head -->
<meta name="csrf-token" content="{{ csrf_token }}">

<!-- In forms -->
<form method="post" action="/rules/add">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <!-- other fields -->
</form>

<!-- In JavaScript for AJAX -->
<script>
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').content;
}

// For all fetch() calls:
fetch('/api/rules/add', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken()
    },
    body: JSON.stringify(data)
});

// For form data submissions:
const formData = new FormData();
formData.append('csrf_token', getCSRFToken());
formData.append('mode', mode);
fetch(action, {
    method: 'POST',
    body: formData,
    redirect: 'manual'
});
</script>
```

### Anti-Patterns to Avoid
- **GET requests for state changes:** Never use GET for actions that modify data - CSRF tokens won't protect them
- **Token in URL:** Never put CSRF tokens in URLs - they leak in logs and referrer headers
- **Same token for all users:** Each user session should have unique CSRF token
- **Predictable tokens:** Always use cryptographically secure random generation

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSRF token generation | Simple random | `secrets.token_urlsafe(32)` | Cryptographically secure |
| Token comparison | String equality | `hmac.compare_digest()` | Timing attack resistant |
| IP address extraction | Manual header parsing | `request.client.host` | FastAPI handles proxies |
| JSON serialization | Manual string building | `json.dumps()` | Handles escaping correctly |

**Key insight:** The stdlib provides all the cryptographic primitives needed. External CSRF libraries add value through configuration options (exempt_urls, sensitive_cookies) but aren't strictly necessary for this use case.

## Common Pitfalls

### Pitfall 1: CSRF Cookie Not Readable by JavaScript
**What goes wrong:** Setting httponly=True on CSRF cookie prevents JavaScript from reading it for AJAX headers
**Why it happens:** Confusion with session cookie (which SHOULD be httponly)
**How to avoid:** CSRF cookie must be httponly=False so JS can read and send in header
**Warning signs:** AJAX requests fail with 403 while form submissions work

### Pitfall 2: Form Body Reading Consumes Request
**What goes wrong:** Reading form data in middleware prevents route from reading it
**Why it happens:** Request body is a stream that can only be read once
**How to avoid:** Cache the body after reading, or check header first (AJAX pattern)
**Warning signs:** Empty form data in route handlers

### Pitfall 3: Missing CSRF Token in AJAX FormData
**What goes wrong:** AJAX form submissions work initially then fail after adding CSRF
**Why it happens:** FormData doesn't include the hidden CSRF field automatically
**How to avoid:** Either append csrf_token to FormData or use X-CSRFToken header
**Warning signs:** Regular form submissions pass, AJAX submissions fail

### Pitfall 4: Audit Log Write Failures Blocking Requests
**What goes wrong:** Database errors in audit logging cause user requests to fail
**Why it happens:** Synchronous audit writes in request path
**How to avoid:** Use background tasks for audit writes, or catch and log errors without raising
**Warning signs:** User actions failing with database errors in audit code

### Pitfall 5: Audit Details Column Too Restrictive
**What goes wrong:** Need to add new context to audit logs requires schema migration
**Why it happens:** Using rigid columns instead of flexible JSON details
**How to avoid:** Use JSON column for variable details, keep indexed columns for common queries
**Warning signs:** Frequent migrations to add audit columns

## Code Examples

Verified patterns for this codebase:

### Audit Log Schema (SQLite)
```sql
-- Source: Enterprise audit log best practices + AUDIT-01 requirements
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,           -- 'auth.login', 'auth.logout', 'rule.create', etc.
    user_id INTEGER,                     -- NULL for anonymous/failed auth
    ip_address TEXT,                     -- Client IP
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    details TEXT,                        -- JSON blob for flexible context
    target_type TEXT,                    -- 'rule', 'user', 'settings', etc.
    target_id INTEGER                    -- ID of affected resource
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_logs(target_type, target_id);
```

### Database Methods for Audit Logging
```python
# Source: Existing database.py patterns
def add_audit_log(
    self,
    event_type: str,
    user_id: Optional[int],
    ip_address: Optional[str],
    details: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
) -> int:
    """Add an audit log entry. Returns the log ID."""
    with self.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO audit_logs (event_type, user_id, ip_address, details, target_type, target_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_type, user_id, ip_address, details, target_type, target_id)
        )
        return cursor.lastrowid

def get_audit_logs(
    self,
    event_type: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[dict]:
    """Query audit logs with optional filters."""
    with self.get_connection() as conn:
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
```

### CSRF Middleware Integration with FastAPI
```python
# Source: FastAPI middleware documentation + starlette-csrf patterns
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

# Add to app.py
app.add_middleware(
    CSRFMiddleware,
    secret_key=config.session.secret_key,  # Reuse existing secret
    cookie_name="csrftoken",
    header_name="x-csrftoken",
    form_field="csrf_token",
)

# Template context processor pattern
def get_templates(request: Request):
    """Get templates with CSRF token in context."""
    templates = request.app.state.templates
    # Add csrf_token to all template contexts
    return templates

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_auth)):
    templates = get_templates(request)
    csrf_token = getattr(request.state, 'csrf_token', '')

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "csrf_token": csrf_token,  # Pass to template
            # ... other context
        },
    )
```

### JavaScript CSRF Helper for Existing AJAX Pattern
```javascript
// Source: Adapted from existing rules.html AJAX pattern
// Add to base.html or separate JS file

function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

// Wrap fetch for automatic CSRF token inclusion
const originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
    // Only add CSRF for unsafe methods
    const method = (options.method || 'GET').toUpperCase();
    const unsafeMethods = ['POST', 'PUT', 'PATCH', 'DELETE'];

    if (unsafeMethods.includes(method)) {
        options.headers = options.headers || {};
        // Don't override if already set
        if (!options.headers['X-CSRFToken'] && !options.headers['x-csrftoken']) {
            options.headers['X-CSRFToken'] = getCSRFToken();
        }
    }

    return originalFetch(url, options);
};
```

## Event Types to Audit

Based on requirements (AUDIT-01) and security best practices:

| Category | Event Type | When to Log | Details to Capture |
|----------|------------|-------------|-------------------|
| Authentication | auth.login_success | Successful login | email |
| Authentication | auth.login_failure | Failed login attempt | email, reason |
| Authentication | auth.logout | User logout | - |
| Authentication | auth.register | New user registration | email, display_name |
| Rules | rule.create | Rule added | rule_type, target_id, target_name |
| Rules | rule.update | Rule settings changed | rule_id, field, old_value, new_value |
| Rules | rule.delete | Rule deleted | rule_id, rule_type, target_name |
| Settings | settings.update | User settings changed | field, old_value, new_value |
| Settings | telegram.link | Telegram account linked | - |
| Settings | telegram.unlink | Telegram account unlinked | - |
| Admin | admin.view_users | Admin viewed user list | - |
| Admin | admin.view_rules | Admin viewed all rules | - |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Synchronizer Token Pattern | Double Submit Cookie (signed) | OWASP 2023+ | Stateless, easier scaling |
| Custom CSRF middleware | Library (starlette-csrf) | 2024+ | Less code to maintain |
| Separate log tables | Single table with JSON details | Current | Flexibility without schema changes |

**Deprecated/outdated:**
- **Referer header checking only:** Unreliable, easily spoofed
- **Cookie-only storage:** Vulnerable without double-submit validation

## Open Questions

Things that couldn't be fully resolved:

1. **Form body reading in middleware**
   - What we know: FastAPI's request body can only be read once
   - What's unclear: Best approach for CSRF middleware to read form data without breaking route handlers
   - Recommendation: Prioritize header-based validation (AJAX), fall back to form field only for traditional submissions

2. **CSRF exempt URLs**
   - What we know: Webhook endpoints (like Telegram) shouldn't require CSRF
   - What's unclear: Exact list of exempt URLs needed
   - Recommendation: Exempt `/telegram/webhook` and potentially API endpoints authenticated via other means

## Sources

### Primary (HIGH confidence)
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) - Double Submit Cookie, token validation
- [FastAPI Middleware Documentation](https://fastapi.tiangolo.com/tutorial/middleware/) - BaseHTTPMiddleware pattern
- Existing codebase (database.py, routes.py, auth.py) - Current patterns to extend

### Secondary (MEDIUM confidence)
- [starlette-csrf GitHub](https://github.com/frankie567/starlette-csrf) - sensitive_cookies configuration
- [fastapi-csrf-protect GitHub](https://github.com/aekasitt/fastapi-csrf-protect) - Flexible header/body acceptance
- [Enterprise Ready Audit Log Guide](https://www.enterpriseready.io/features/audit-log/) - Schema design, event types

### Tertiary (LOW confidence)
- Various Medium articles on FastAPI logging middleware - General patterns, verify with official docs

## Metadata

**Confidence breakdown:**
- CSRF approach: HIGH - OWASP guidance is authoritative, existing codebase patterns clear
- Audit schema: HIGH - Requirements are explicit (AUDIT-01, AUDIT-10), standard patterns apply
- Integration patterns: MEDIUM - Codebase-specific, may need adjustment during implementation

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days - stable security patterns)
