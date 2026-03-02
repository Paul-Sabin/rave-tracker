# Phase 20: Wizard Routes - Research

**Researched:** 2026-03-02
**Domain:** FastAPI route definitions, Jinja2 templates, step-routing with integer path params
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Phase boundary**
- Routing infrastructure only — actual wizard content (forms, validation, data persistence) is Phase 21+

**Stub page content**
- Minimal: each step page shows only "Step N of 4" with no content hints or form placeholders
- Pure routing verification — Phase 21 fills in real content

**Completion behavior**
- POST /welcome/complete calls set_onboarding_completed(user_id) and redirects to /dashboard (303)
- No success message, no query parameter — clean redirect

**Re-visit policy**
- Allow re-entry: users who already completed onboarding can revisit /welcome and step through again
- Do NOT redirect already-onboarded users away from the wizard

**Step navigation**
- Each step has a "Next" link/button navigating to the next step
- Step 4 has a "Complete" button that POSTs to /welcome/complete
- No Back button in stubs — Phase 21 adds richer navigation
- No progress indicator in stubs

### Claude's Discretion

- Template structure (single template with step variable vs separate templates per step)
- Exact HTML/CSS for stub pages
- Error handling for invalid step numbers (clamping behavior)
- CSRF token handling on POST /welcome/complete

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WIZ-01 | New user sees a 4-step welcome wizard on first login after email verification | Route definitions for /welcome (redirect) and /welcome/step/{1-4}, auth gated via require_verified_email, step clamping to 1-4, POST /welcome/complete with DB call |
</phase_requirements>

---

## Summary

Phase 20 is a pure routing phase in a FastAPI + Jinja2 codebase. The work is narrow: define four GET routes and one POST route for the /welcome wizard, create a single stub template, and wire auth via the existing `require_verified_email` dependency. No new dependencies, no database migrations, no JavaScript beyond what base.html already provides.

The codebase has fully established patterns for every sub-problem: route definition, redirect responses, path parameter handling, template rendering with CSRF token, and the `require_verified_email` decorator. All patterns can be copied verbatim from existing routes. The only design decision left to research is whether to use a single parameterized template or separate per-step templates — a single template with a `step` variable is the clear recommendation for stub phase.

WIZ-01 says "new user sees a 4-step welcome wizard." Phase 20 satisfies the routing half of WIZ-01: the URL structure resolves correctly, auth gates are in place, and step navigation (Next / Complete) functions. Phase 21 fills in real content to complete the requirement.

**Primary recommendation:** Implement all routes in routes.py following the existing dashboard/tracking pattern; use a single `welcome.html` template that branches on `step` variable; clamp step with `max(1, min(step, 4))`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI (already installed) | current project version | Route definitions, path params, Depends | Already the web framework |
| Jinja2 (already installed) | current project version | Template rendering | Already the template engine |
| Starlette RedirectResponse (already installed) | — | 303 redirect for /welcome → /welcome/step/1 and POST /welcome/complete | Already used in every POST handler |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| None | — | No new dependencies needed | This phase adds no new libs |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Single welcome.html with step variable | 4 separate step templates | Single template is correct for stubs with identical minimal content; separate templates suit Phase 21 when each step has distinct forms |

**Installation:**
No installation needed — all required libraries are already present.

---

## Architecture Patterns

### Recommended Project Structure

```
ra-tracker/ra_tracker/web/
├── routes.py                     # Add wizard routes here (existing file)
└── templates/
    └── welcome.html              # New single stub template (step 1-4)
```

### Pattern 1: Redirect Route (GET /welcome → GET /welcome/step/1)

**What:** A GET route that immediately returns a 301 or 303 redirect to the first step.
**When to use:** Canonical URL shortcut — /welcome is the entry point, /welcome/step/1 is the actual page.

```python
# Source: existing pattern in routes.py line 99-100
@router.get("/welcome")
async def welcome_redirect(user: User = Depends(require_verified_email)):
    return RedirectResponse(url="/welcome/step/1", status_code=302)
```

Note: Use 302 (temporary) not 301 (permanent) here — the redirect target may change in future phases. The success criteria says "GET /welcome redirects to /welcome/step/1" without specifying status code; 302 is safe.

### Pattern 2: Parameterized Step Route with Clamping

**What:** A single GET route with an integer path parameter; clamps to valid range rather than returning 404/500 for out-of-range values.
**When to use:** Whenever a resource has a bounded integer index and graceful degradation is preferred over errors.

```python
# Source: FastAPI path params pattern, verified against existing codebase patterns
@router.get("/welcome/step/{step}", response_class=HTMLResponse)
async def welcome_step(
    request: Request,
    step: int,
    user: User = Depends(require_verified_email),
):
    templates = get_templates(request)
    step = max(1, min(step, 4))  # Clamp: 0 → 1, 99 → 4
    return templates.TemplateResponse(
        "welcome.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "step": step,
        },
    )
```

### Pattern 3: POST Route with DB Call + Clean Redirect

**What:** POST handler that calls a DB method and returns a 303 redirect. Follows every existing POST handler in routes.py.
**When to use:** Any action that mutates state and then navigates away.

```python
# Source: pattern from routes.py /tracking/add, /settings/save etc.
@router.post("/welcome/complete")
async def welcome_complete(
    request: Request,
    user: User = Depends(require_verified_email),
):
    db = request.app.state.db if hasattr(request.app.state, 'db') else get_db()
    db.set_onboarding_completed(user.id)
    return RedirectResponse(url="/", status_code=303)
```

Note: Existing routes use `get_db()` (module-level singleton). Confirmed `get_db` is imported in routes.py line 24. Use `get_db()` directly, consistent with all other routes.

### Pattern 4: Auth Gating via require_verified_email

**What:** The `require_verified_email` dependency is already defined in auth.py. It chains `require_auth` (redirect to /login if not authenticated) → checks `user.email_verified` (redirect to /verify-email if unverified).
**When to use:** All wizard routes — satisfies both success criteria 4 (unauthenticated → login) and 5 (unverified → verify-email).

```python
# Source: auth.py lines 99-112 — already handles both conditions
async def require_verified_email(
    request: Request,
    user: User = Depends(require_auth)
) -> User:
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/verify-email"}
        )
    return user
```

No modification needed. Simply `Depends(require_verified_email)` on all four routes handles success criteria 4 and 5 together.

### Pattern 5: CSRF on POST Form

**What:** The CSRF middleware (csrf.py) reads the token from either the `X-CSRFToken` header (AJAX) or the `csrf_token` form field. The POST /welcome/complete form must include `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`.
**When to use:** All POST form submissions.

```html
<!-- Source: base.html pattern used in every form in the codebase -->
<form action="/welcome/complete" method="POST">
  <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
  <button type="submit" class="btn btn-primary">Complete</button>
</form>
```

### Pattern 6: Single Stub Template (recommended approach for Claude's Discretion)

**What:** One `welcome.html` that receives a `step` integer and branches minimally. Avoids creating 4 near-identical files.
**Reasoning:** Phase 21 will replace this template with real content; duplicating four identical stubs wastes merge effort.

```html
{% extends "base.html" %}

{% block title %}Welcome - Rave Tracker{% endblock %}

{% block content %}
<div class="max-w-md mx-auto py-8">
  <div class="card text-center">
    <p class="text-text-muted mb-6">Step {{ step }} of 4</p>
    {% if step < 4 %}
      <a href="/welcome/step/{{ step + 1 }}" class="btn btn-primary">Next</a>
    {% else %}
      <form action="/welcome/complete" method="POST">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <button type="submit" class="btn btn-primary">Complete</button>
      </form>
    {% endif %}
  </div>
</div>
{% endblock %}
```

### Anti-Patterns to Avoid

- **Using 404 for out-of-range step:** Success criterion 3 explicitly requires clamping — GET /welcome/step/99 must return 200 with step 4 rendered.
- **Using 301 permanent redirect for /welcome:** Use 302; the canonical step URL may evolve.
- **Adding `onboarding_completed` check as an extra guard:** The re-visit policy decision explicitly says DO NOT redirect already-onboarded users away. `require_verified_email` is the only gate needed.
- **Calling `request.app.state.db` directly:** Existing routes all use `get_db()` from `from ..database import get_db`. Follow the same pattern.
- **Putting wizard routes in a new file:** All web routes live in routes.py via the single `router = APIRouter()`. No new router file is warranted for 3 GET + 1 POST routes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Auth gating (unauthed + unverified) | Custom auth check in each route | `Depends(require_verified_email)` | Already handles both conditions with correct redirects |
| CSRF protection on POST | Manual token generation/validation | CSRFMiddleware already active + hidden `csrf_token` field in form | Double-submit cookie pattern already wired globally |
| Integer path param validation | Manual `try/except int()` | FastAPI's `step: int` path param | FastAPI returns 422 automatically for non-integer; then clamp handles range |

**Key insight:** This phase has zero custom problem-solving. Every sub-problem is already solved in the codebase. The entire implementation is assembly of proven patterns.

---

## Common Pitfalls

### Pitfall 1: FastAPI 422 vs Step Clamping

**What goes wrong:** Accessing `/welcome/step/abc` returns FastAPI's default 422 JSON response instead of an HTML page, which looks broken.
**Why it happens:** FastAPI validates `step: int` path param type. Non-integer values like "abc" fail before the route function runs.
**How to avoid:** This is acceptable behavior — the success criteria only specifies clamping for numeric out-of-range values (e.g., step/99). Non-integer paths are appropriately rejected with 422. No special handling needed.
**Warning signs:** Only a problem if tests try `/welcome/step/abc` and expect a 200.

### Pitfall 2: CSRF Failure on POST /welcome/complete

**What goes wrong:** POST /welcome/complete returns 403 "CSRF validation failed."
**Why it happens:** The form is missing the `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">` field, OR the template context doesn't include `csrf_token`.
**How to avoid:** Always pass `"csrf_token": getattr(request.state, 'csrf_token', '')` in TemplateResponse context (same as every other route). Always include the hidden field in the form.
**Warning signs:** 403 response on POST, "CSRF validation failed" in logs.

### Pitfall 3: base.html Nav Highlighting

**What goes wrong:** The nav bar highlights "Dashboard" or "Settings" when on a /welcome URL because base.html checks `request.url.path == '/'` etc.
**Why it happens:** base.html nav uses exact path matching for active state. /welcome doesn't match any existing nav item.
**How to avoid:** Nothing to do — no nav item for /welcome exists yet. The nav simply shows no active item while on wizard pages, which is correct for a full-screen wizard.
**Warning signs:** None — expected behavior for stub phase.

### Pitfall 4: Redirect Loop on /welcome

**What goes wrong:** GET /welcome → 302 → GET /welcome/step/1 → 302 → GET /welcome/step/1 (loop).
**Why it happens:** Would only occur if the step route also redirected. It doesn't — the step route renders HTML.
**How to avoid:** Ensure `/welcome/step/{step}` returns `TemplateResponse` (200), not another redirect.
**Warning signs:** Browser shows redirect loop error.

### Pitfall 5: step + 1 Jinja2 Arithmetic

**What goes wrong:** `{{ step + 1 }}` in a Jinja2 template where `step` is passed as a Python `int` works correctly, but if passed as a string it concatenates instead of adds.
**Why it happens:** Python type mismatch.
**How to avoid:** Ensure `step = max(1, min(step, 4))` in the route function (which guarantees it is a Python int) before passing to template. `step: int` path param + clamping = guaranteed int.
**Warning signs:** URL becomes `/welcome/step/31` instead of `/welcome/step/4` (string "3" + "1").

---

## Code Examples

Verified patterns from existing codebase:

### Complete wizard routes block (ready to add to routes.py)

```python
# Source: patterns verified in routes.py and auth.py

@router.get("/welcome")
async def welcome_redirect(user: User = Depends(require_verified_email)):
    """Redirect /welcome to first wizard step."""
    return RedirectResponse(url="/welcome/step/1", status_code=302)


@router.get("/welcome/step/{step}", response_class=HTMLResponse)
async def welcome_step(
    request: Request,
    step: int,
    user: User = Depends(require_verified_email),
):
    """Render wizard step page. Step is clamped to [1, 4]."""
    templates = get_templates(request)
    step = max(1, min(step, 4))
    return templates.TemplateResponse(
        "welcome.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "step": step,
        },
    )


@router.post("/welcome/complete")
async def welcome_complete(
    request: Request,
    user: User = Depends(require_verified_email),
):
    """Mark onboarding complete and redirect to dashboard."""
    db = get_db()
    db.set_onboarding_completed(user.id)
    return RedirectResponse(url="/", status_code=303)
```

### welcome.html stub template

```html
{% extends "base.html" %}

{% block title %}Welcome - Rave Tracker{% endblock %}

{% block content %}
<div class="max-w-md mx-auto py-8">
  <div class="card text-center">
    <p class="text-text-muted mb-6">Step {{ step }} of 4</p>
    {% if step < 4 %}
      <a href="/welcome/step/{{ step + 1 }}" class="btn btn-primary">Next</a>
    {% else %}
      <form action="/welcome/complete" method="POST">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <button type="submit" class="btn btn-primary">Complete</button>
      </form>
    {% endif %}
  </div>
</div>
{% endblock %}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| N/A — this is new functionality | FastAPI path params + Jinja2 single template | Phase 20 (new) | No migration needed |

**Deprecated/outdated:**
- None applicable — no existing wizard routes exist to replace.

---

## Open Questions

1. **Redirect status code for GET /welcome**
   - What we know: Success criterion says "GET /welcome redirects to /welcome/step/1" — no status code specified
   - What's unclear: 301 vs 302 vs 303
   - Recommendation: Use 302 (Found). Avoids browser caching the redirect permanently, which matters because the entry behavior may change in Phase 22 (login intercept). 303 is for POST→GET, not appropriate here. 301 is permanent and cached by browsers.

2. **Template location: welcome.html vs wizard/welcome.html**
   - What we know: All existing templates are flat in `templates/` (no subdirectory for auth, settings, etc.)
   - What's unclear: Should wizard templates live in a subdirectory?
   - Recommendation: Keep flat (`templates/welcome.html`) for Phase 20 consistency with existing structure. Phase 21 can reorganize if subdirectory makes sense.

---

## Sources

### Primary (HIGH confidence)

- Codebase: `ra-tracker/ra_tracker/web/routes.py` — all route, redirect, template render, and get_db() patterns verified directly
- Codebase: `ra-tracker/ra_tracker/web/auth.py` — `require_verified_email` implementation verified; chains require_auth (login redirect) + email_verified check (verify-email redirect)
- Codebase: `ra-tracker/ra_tracker/web/csrf.py` — CSRF middleware confirmed to accept form field `csrf_token` for application/x-www-form-urlencoded POST bodies
- Codebase: `ra-tracker/ra_tracker/database.py` — `set_onboarding_completed(user_id, completed=True)` method confirmed present; `User.onboarding_completed` field confirmed
- Codebase: `ra-tracker/ra_tracker/web/templates/base.html` — `.btn`, `.btn-primary`, `.card` CSS classes confirmed; `{% block content %}` structure confirmed; `csrf_token` meta tag confirmed
- Phase 20 CONTEXT.md — locked decisions and Claude's discretion areas

### Secondary (MEDIUM confidence)

- None needed — all findings are from direct codebase inspection.

### Tertiary (LOW confidence)

- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all libs are existing project installs
- Architecture: HIGH — every pattern verified directly in codebase source
- Pitfalls: HIGH — derived from reading actual CSRF middleware, auth chain, and Jinja2 template patterns in this exact codebase

**Research date:** 2026-03-02
**Valid until:** 2026-04-01 (stable patterns in a mature codebase)
