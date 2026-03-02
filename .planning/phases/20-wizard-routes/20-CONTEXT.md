# Phase 20: Wizard Routes - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

The /welcome URL resolves and returns a rendered page; step routing (/welcome/step/1 through /welcome/step/4) is confirmed working; the wizard is accessible by direct URL to a verified, logged-in user. This phase builds routing infrastructure only — actual wizard content (forms, validation, data persistence) belongs in Phase 21+.

</domain>

<decisions>
## Implementation Decisions

### Stub page content
- Minimal: each step page shows only "Step N of 4" with no content hints or form placeholders
- Pure routing verification — Phase 21 fills in real content

### Completion behavior
- POST /welcome/complete calls set_onboarding_completed(user_id) and redirects to /dashboard (303)
- No success message, no query parameter — clean redirect

### Re-visit policy
- Allow re-entry: users who already completed onboarding can revisit /welcome and step through again
- Do NOT redirect already-onboarded users away from the wizard

### Step navigation
- Each step has a "Next" link/button navigating to the next step
- Step 4 has a "Complete" button that POSTs to /welcome/complete
- No Back button in stubs — Phase 21 adds richer navigation
- No progress indicator in stubs

### Claude's Discretion
- Template structure (single template with step variable vs separate templates per step)
- Exact HTML/CSS for stub pages
- Error handling for invalid step numbers (clamping behavior)
- CSRF token handling on POST /welcome/complete

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `require_verified_email` decorator: Ensures login + email verified before wizard access
- `set_onboarding_completed(user_id)` method: Already exists in Database class from Phase 19
- `base.html` template: Jinja2 base with title/content/scripts blocks, nav bar, Tailwind v4
- CSRF auto-wrapping: fetch() middleware handles CSRF for POST requests
- Form CSS classes: `.form-group`, `.btn`, `.btn-primary` already styled

### Established Patterns
- Route definition: `@router.get("/path", response_class=HTMLResponse)` with `Depends(require_verified_email)`
- Template rendering: `templates.TemplateResponse("file.html", {"request": request, "user": user, "csrf_token": ...})`
- Redirects: `RedirectResponse(url="/path", status_code=303)`
- Email verification flow: proven 2-step redirect-based pattern

### Integration Points
- Routes added to `/ra_tracker/web/routes.py` via existing `router = APIRouter()`
- New template(s) in `/ra_tracker/web/templates/`
- Auth via `require_verified_email` from `/ra_tracker/web/auth.py`
- Database via `request.app.state.db.set_onboarding_completed()`

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches matching existing codebase patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 20-wizard-routes*
*Context gathered: 2026-03-02*
