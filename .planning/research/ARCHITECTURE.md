# Architecture: Onboarding Wizard Integration

**Project:** Rave Tracker v3.4 — Onboarding & Welcome Wizard
**Researched:** 2026-03-01
**Confidence:** HIGH (based on direct codebase analysis)

---

## What This Document Covers

How a multi-step onboarding wizard plugs into the existing FastAPI/Jinja2/PostgreSQL
architecture. Every claim here is derived from reading the actual source files, not from
inference or convention alone.

---

## Existing Architecture Snapshot (what the wizard must fit into)

**Request cycle:**
```
Browser → FastAPI router (routes.py) → Dependency (require_verified_email)
       → Route handler → db.get_* → Jinja2 template render → HTML response
```

**Auth chain:**
```
require_verified_email → require_auth → get_current_user → session cookie lookup
```
Every protected page goes through `require_verified_email`. The wizard will too.

**Login redirect target (current):**
```python
# routes.py line ~682
response = RedirectResponse(url="/", status_code=303)
```
After a successful, verified login the user lands on `/`. This is the only intercept point
to route first-time users to `/welcome` instead.

**Database mutation pattern** (from `database.py`):
- All writes go through `Database.get_connection()` context manager
- Migrations are appended to the `MIGRATIONS` list — each entry is a raw SQL string
- Current migration count: 13 (last: `queued_for_digest` on notifications table)
- PostgreSQL schema lives in `SCHEMA_PG`; SQLite schema in `SCHEMA`; both must stay in sync

**AJAX / JSON endpoint pattern** (from `routes.py` lines 488-498):
```python
@router.post("/api/user/local-area")
async def set_local_area(request: Request, user: User = Depends(require_verified_email)):
    data = await request.json()
    area_id = data.get("area_id")
    area_name = data.get("area_name", "")
    db.update_user_local_area(user.id, int(area_id), area_name)
    return {"success": True}
```
The wizard's "save and advance" calls will follow this exact JSON-body + JSON-response shape.

**Template structure:**
```
web/templates/
  base.html          ← nav, CSS vars, <head>
  dashboard.html     ← extends base.html
  settings.html      ← extends base.html
  rules.html         ← extends base.html
  welcome.html       ← NEW — extends base.html, but should suppress nav
```

---

## Database Schema Changes

### New Column: `onboarding_completed`

Add one boolean column to the `users` table.

**SQLite migration (appended as Migration 14):**
```sql
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0;
```

**PostgreSQL migration (appended as Migration 14):**
```sql
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE;
```

**Migration entry in `MIGRATIONS` list:**
```python
# Migration 14: Add onboarding_completed flag for welcome wizard
"""
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0;
""",
```
The existing migration runner executes the SQLite variant on SQLite and skips on PostgreSQL
(or vice versa — check which branch `database.py` selects at runtime; both need updating).

**`User` dataclass addition:**
```python
@dataclass
class User:
    ...
    onboarding_completed: bool = False  # Set True after wizard finish step
```

**New `Database` method:**
```python
def set_onboarding_completed(self, user_id: int, completed: bool = True) -> None:
    """Mark onboarding as completed (or reset for revisit testing)."""
    with self.get_connection() as conn:
        conn.execute(
            f"UPDATE users SET onboarding_completed = {self.ph} WHERE id = {self.ph}",
            (completed, user_id)
        )
```

### No New Tables Required

Wizard state is ephemeral (which step the user is on). It lives in the URL path parameter
(`/welcome/step/2`), not the database. The only persistent state is `onboarding_completed`.
Local area and notification preferences already have columns — the wizard reuses them.

---

## New Routes

All new routes go into `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/web/routes.py` — there is
only one route file in this project. Do not create a separate module.

### GET /welcome

```python
@router.get("/welcome", response_class=HTMLResponse)
async def welcome_redirect(request: Request, user: User = Depends(require_verified_email)):
    """Always starts at step 1."""
    return RedirectResponse(url="/welcome/step/1", status_code=303)
```

### GET /welcome/step/{step}

```python
@router.get("/welcome/step/{step}", response_class=HTMLResponse)
async def welcome_step(
    step: int,
    request: Request,
    user: User = Depends(require_verified_email),
):
    """Render the wizard at a given step. Clamps out-of-range steps."""
    templates = get_templates(request)
    db = get_db()
    user = db.get_user_by_id(user.id)  # Refresh — local_area may have changed

    TOTAL_STEPS = 4
    step = max(1, min(step, TOTAL_STEPS))

    return templates.TemplateResponse(
        "welcome.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, "csrf_token", ""),
            "step": step,
            "total_steps": TOTAL_STEPS,
        },
    )
```

### POST /welcome/complete

```python
@router.post("/welcome/complete")
async def complete_welcome(
    request: Request,
    user: User = Depends(require_verified_email),
):
    """Mark onboarding done, redirect to dashboard."""
    db = get_db()
    db.set_onboarding_completed(user.id, True)
    return RedirectResponse(url="/", status_code=303)
```

### No Separate "Save Step" Routes

Each wizard step that needs to persist data calls an **existing endpoint**:

| Wizard step | Existing endpoint called | Method |
|-------------|--------------------------|--------|
| Local area | `POST /api/user/local-area` | JSON body |
| Telegram toggle | `POST /settings/notifications/telegram` | form-encoded |
| Email toggle | `POST /settings/notifications/email` | form-encoded |

The wizard template uses JavaScript `fetch()` to call these endpoints inline, exactly as the
area widget on `/tracking` does today (see `rules.html` lines 698-712).

---

## Modified Routes

### POST /login — add onboarding intercept

**Location:** `routes.py` ~line 681

**Current code:**
```python
response = RedirectResponse(url="/", status_code=303)
```

**Modified code:**
```python
# Refresh user after session create to get onboarding_completed
fresh_user = db.get_user_by_id(user.id)
if not fresh_user.onboarding_completed:
    response = RedirectResponse(url="/welcome/step/1", status_code=303)
else:
    response = RedirectResponse(url="/", status_code=303)
```

This is the only modification needed to trigger the wizard on first login. Subsequent logins
bypass it because `onboarding_completed = True`.

### GET /settings — add "revisit tour" link

**Location:** `templates/settings.html`

Add a link in the Notification Preferences card (or as a standalone card):
```html
<div class="card">
    <div class="card-header">
        <span class="card-title">App Tour</span>
    </div>
    <p class="text-muted mb-2">Revisit the welcome wizard to review your setup.</p>
    <a href="/welcome/step/1" class="btn btn-secondary">Revisit Tour</a>
</div>
```

No route change needed — `/welcome/step/1` renders correctly for users with
`onboarding_completed = True` because the wizard does not check that flag on render.
Only the login intercept checks it.

---

## New Template: `welcome.html`

**Location:** `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/web/templates/welcome.html`

**Extends:** `base.html`

**Key structural decisions:**

1. **Single template, step-driven via Jinja2 `{% if step == N %}`** — not one template per
   step. The server renders the correct panel based on the `step` context variable.
   This keeps the file count low and avoids duplicating the base layout.

2. **Nav suppression** — the base template nav should be hidden during onboarding so users
   cannot navigate away mid-wizard. Use a `{% block nav %}{% endblock %}` override if
   `base.html` exposes a nav block, or add a `no_nav` context flag and `{% if not no_nav %}`
   guard in `base.html`.

3. **Step indicator** — a progress bar or numbered dots rendered from `step` and
   `total_steps`. Pure HTML/CSS; no JS required for the indicator itself.

4. **Mobile-first layout** — single column, full-width cards. Touch targets 44px minimum.
   Matches the existing `.card` / `.btn` / `.form-control` CSS class system from `base.html`.

**Step structure (4 steps):**

| Step | Content | Data action |
|------|---------|-------------|
| 1 | Welcome + Ravemonger character intro | None — navigate only |
| 2 | Local area selection | Calls `POST /api/user/local-area` via `fetch()` |
| 3 | Notification preferences (Telegram + Email toggles) | Calls existing `/settings/notifications/*` endpoints via `fetch()` |
| 4 | Feature tour (tracking, dashboard, settings overview) | None — navigate to `/welcome/complete` |

**Navigation pattern (client-side):**
```javascript
// "Next" button on steps 1-3
async function advanceStep(currentStep) {
    // If step has unsaved state, save first (see data actions above)
    window.location.href = `/welcome/step/${currentStep + 1}`;
}

// "Finish" button on step 4
async function finishWizard() {
    const resp = await fetch('/welcome/complete', {
        method: 'POST',
        headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content },
    });
    window.location.href = '/';
}
```

Step navigation is a full page load (`window.location.href`), not AJAX. This is consistent
with how the rest of the app handles page transitions. AJAX is reserved for inline data saves.

---

## Component Boundaries: New vs Modified

### New (create from scratch)

| Component | File | Size estimate |
|-----------|------|---------------|
| `welcome.html` template | `web/templates/welcome.html` | ~200 lines |
| `GET /welcome` route | `web/routes.py` | 5 lines |
| `GET /welcome/step/{step}` route | `web/routes.py` | 20 lines |
| `POST /welcome/complete` route | `web/routes.py` | 10 lines |
| `Database.set_onboarding_completed()` | `database.py` | 8 lines |
| Migration 14 SQL | `database.py` (MIGRATIONS list) | 3 lines each (SQLite + PG) |
| `User.onboarding_completed` field | `database.py` (dataclass) | 1 line |

### Modified (surgical edits to existing files)

| Component | File | Change |
|-----------|------|--------|
| Login POST handler | `web/routes.py` | 5-line onboarding intercept after session create |
| `User` row readers | `database.py` | Add `onboarding_completed` to every `row["..."]` mapping |
| PostgreSQL schema constant | `database.py` | Add column to `SCHEMA_PG` |
| SQLite schema constant | `database.py` | Add column to `SCHEMA` |
| Settings template | `web/templates/settings.html` | Add "Revisit Tour" card |
| `base.html` | `web/templates/base.html` | Add `{% block nav %}` override support (if not already present) |

**User row readers note:** `database.py` maps database rows to `User` dataclasses in several
places (`get_user_by_id`, `get_user_by_email`, `get_user_by_telegram_chat_id`, and the
admin user list). Each mapping needs `onboarding_completed=row["onboarding_completed"]`
added. Grep for `telegram_chat_id=row["telegram_chat_id"]` to find all sites.

---

## Data Flow per Wizard Step

### Step 1 — Welcome (no data)
```
GET /welcome/step/1
  → render welcome.html (step=1)
  → user clicks "Let's go" → window.location.href = "/welcome/step/2"
```

### Step 2 — Local Area
```
GET /welcome/step/2
  → render welcome.html (step=2, pre-populated with user.local_area_name)

User types city name:
  → JS fetch: GET /api/search/areas?q={query}
  → render dropdown results

User selects area:
  → JS fetch: POST /api/user/local-area {area_id, area_name}
  → {success: true} → enable "Next" button

User clicks "Next":
  → window.location.href = "/welcome/step/3"
```
This reuses `search_areas()` and `set_local_area()` without any modification.

### Step 3 — Notifications
```
GET /welcome/step/3
  → render welcome.html (step=3, user.telegram_chat_id, user.telegram_enabled,
                         user.email_enabled, telegram_configured, email_configured)

User toggles email on/off:
  → JS fetch: POST /settings/notifications/email {enabled: "on"|"off"}
  → receives RedirectResponse 303 (ignore redirect, treat any 2xx/3xx as success)

User clicks Telegram link button:
  → JS fetch: POST /settings/telegram/link
  → receives {link_code: "...", bot_username: "..."}
  → display bot link instructions inline

User clicks "Next":
  → window.location.href = "/welcome/step/4"
```

The existing notification endpoints return `RedirectResponse(url="/settings", ...)` — the
wizard JS must use `redirect: "manual"` and treat opaque responses as success (same pattern
as the tracking page's AJAX cycle buttons in `rules.html`).

### Step 4 — Feature Tour (no data)
```
GET /welcome/step/4
  → render welcome.html (step=4) — static tour content, no data needed

User clicks "Start tracking":
  → JS fetch: POST /welcome/complete (with CSRF token)
  → db.set_onboarding_completed(user.id, True)
  → redirect 303 → /
  → user lands on dashboard
```

---

## "Revisitable" Architecture

Revisiting the tour from settings requires zero new infrastructure:

1. `/settings` links to `/welcome/step/1`
2. `GET /welcome/step/{step}` renders without checking `onboarding_completed`
3. `POST /welcome/complete` sets `onboarding_completed = True` again (idempotent)
4. At the end the user is redirected to `/` — same as first time

The wizard does not distinguish first-run from revisit at render time. The only place
`onboarding_completed` is checked is the login POST handler redirect decision.

---

## Wizard State Management: Server-Side vs Client-Side

**Decision: step state lives in the URL, not server-side session.**

Rationale:
- Session state would require storing step progress in the database or cookie — additional
  complexity with no user-facing benefit (wizard is short, ~2 minutes)
- URL-based step (`/welcome/step/2`) is bookmarkable, shareable for debugging, and
  consistent with how the rest of the app uses URL structure
- If user refreshes, they stay on the same step — better UX than being reset to step 1
- "Back" button works naturally (browser history)

Persistent data (local_area, notification prefs) is saved per-step via existing AJAX
endpoints so there is no risk of losing input if the user refreshes.

---

## Scalability and Multi-Worker Concerns

No scheduler involvement. No background jobs. No shared state beyond the `users` table
column, which PostgreSQL handles correctly under concurrent writes. The wizard is stateless
on the server — every request is a fresh database read.

---

## Mobile-First Rendering

The wizard is accessed primarily on mobile (375px+, based on PROJECT.md constraints).

**Approach:**
- Single-column layout for all wizard steps — no two-column split
- "Next" button is full-width (`width: 100%`) at the bottom of the step card
- Area search results list is full-width with 44px touch targets per item
- Notification toggle switches reuse the `.toggle-switch` CSS class from `settings.html`
- Ravemonger image: fixed size (e.g., 80px × 80px), does not reflow — renders above
  the step content, not beside it

No new CSS component classes are required. The wizard uses `.card`, `.btn`, `.btn-primary`,
`.form-control`, `.toggle-switch`, and `.toggle-slider` — all defined in `base.html`.

---

## Build Order (dependency-aware)

This order minimizes blocked work and allows incremental verification.

### Step 1 — Database migration (prerequisite for everything)

**Why first:** The `onboarding_completed` column must exist before any route reads the
`User` object or the login intercept compares the flag.

- Add `onboarding_completed BOOLEAN DEFAULT 0/FALSE` to both schema constants
- Append Migration 14 to `MIGRATIONS`
- Add `onboarding_completed: bool = False` to `User` dataclass
- Add `onboarding_completed=row["onboarding_completed"]` to all row mappings
- Add `Database.set_onboarding_completed()` method

**Verification:** Restart app locally, register a new user, confirm `onboarding_completed`
column is `False` in the database.

### Step 2 — Wizard routes (no template yet)

**Why second:** Unblocks template work by giving it real URLs to point to.

- `GET /welcome` → redirects to `/welcome/step/1`
- `GET /welcome/step/{step}` → stub that returns `{"step": step}` as JSON temporarily
- `POST /welcome/complete` → sets flag and redirects to `/`

**Verification:** `curl -b session_cookie http://localhost:8080/welcome/step/1` returns 200.

### Step 3 — `welcome.html` template (step by step)

**Why third:** Routes exist, database exists, now build the UI.

Build in step order (1 → 2 → 3 → 4), testing each step in the browser before adding the next.
This catches template syntax errors early without debugging a 200-line file.

- Step 1: Static welcome card with Ravemonger image
- Step 2: Area search widget (copy JS from `rules.html`, adapt for wizard context)
- Step 3: Notification toggles (copy from `settings.html`, adapt for wizard context)
- Step 4: Feature tour static content + Finish button calling `/welcome/complete`

**Nav suppression:** Add `{% block nav %}{% endblock %}` to `base.html` nav block at this
point (only if the nav block does not already exist).

### Step 4 — Login intercept (makes wizard trigger on first login)

**Why fourth:** Template must exist before the intercept redirects real users to it.
Doing this last prevents broken redirects during development.

- Modify `POST /login` to check `fresh_user.onboarding_completed`
- If `False`, redirect to `/welcome/step/1` instead of `/`

**Verification:** Register new user, verify email, login — confirm redirect lands on `/welcome/step/1`.

### Step 5 — Settings "Revisit Tour" link

**Why last:** Purely additive, zero risk of breaking existing functionality.

- Add "Revisit Tour" card to `settings.html`

**Verification:** Log in as existing user with `onboarding_completed = True`, go to
`/settings`, click "Revisit Tour", confirm wizard renders.

### Step 6 — Existing user migration (production concern)

Existing users in production have `onboarding_completed = NULL` (column default) or `False`
after Migration 14 runs. They will be sent to the wizard on next login.

**Decision needed:** Should existing users be auto-opted-out?

Options:
- **A. Show wizard to all** — Migration 14 defaults to `FALSE`; every existing user sees
  the wizard once. Acceptable if wizard content is genuinely useful for existing users.
- **B. Skip for existing users** — Run a one-time `UPDATE users SET onboarding_completed = TRUE`
  as part of the migration for rows that already have a `local_area_id` set (proxy for
  "user has already configured the app"). Safer for production.

Recommendation: **Option B.** Add to Migration 14:
```sql
-- Migration 14b: Mark existing configured users as having completed onboarding
UPDATE users SET onboarding_completed = TRUE WHERE local_area_id IS NOT NULL;
```
Users who registered but never set a local area will see the wizard. Users who have already
engaged with the app will not be interrupted.

---

## Integration Points with Existing Code: Summary

| Existing code | Interaction | Type |
|---------------|-------------|------|
| `POST /login` route | Add 5-line intercept to check `onboarding_completed` | Modify |
| `GET /api/search/areas` | Called by wizard step 2 area search | Reuse (no change) |
| `POST /api/user/local-area` | Called by wizard step 2 area save | Reuse (no change) |
| `POST /settings/notifications/telegram` | Called by wizard step 3 | Reuse (no change) |
| `POST /settings/notifications/email` | Called by wizard step 3 | Reuse (no change) |
| `POST /settings/telegram/link` | Called by wizard step 3 Telegram link flow | Reuse (no change) |
| `User` dataclass | Add `onboarding_completed` field | Modify |
| `Database` class | Add `set_onboarding_completed()` method | Modify |
| `SCHEMA` / `SCHEMA_PG` constants | Add column definition | Modify |
| `MIGRATIONS` list | Append Migration 14 | Modify |
| Row-to-User mappings (4 locations) | Add `onboarding_completed` field read | Modify |
| `settings.html` | Add "Revisit Tour" link | Modify |
| `base.html` | Add nav block override support | Modify (minor) |

---

## Sources

All findings are derived from direct source code analysis (HIGH confidence):

- `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/database.py` — Schema, MIGRATIONS pattern,
  User dataclass, row mapping sites, migration runner
- `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/web/routes.py` — Login flow, redirect chain,
  existing area/notification endpoints, AJAX patterns
- `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/web/templates/rules.html` — Area widget JS
  (fetch, search, save pattern)
- `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/web/templates/settings.html` — Notification
  toggle UI pattern
- `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/web/templates/base.html` — CSS variables,
  component class names, layout conventions
- `/c/CLAUDE/ra-tips/.planning/PROJECT.md` — v3.4 requirements, mobile-first constraints
- `/c/CLAUDE/ra-tips/.planning/codebase/ARCHITECTURE.md` — Layered service architecture,
  authentication chain
- `/c/CLAUDE/ra-tips/.planning/codebase/CONVENTIONS.md` — AJAX pattern, CSRF token source,
  mobile layout conventions

---

*Architecture analysis: 2026-03-01*
*Confidence: HIGH — based on reading actual source files, not inference*
