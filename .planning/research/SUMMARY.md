# Project Research Summary

**Project:** Rave Tracker v3.4 — Onboarding Welcome Wizard
**Domain:** Multi-step onboarding wizard integrated into existing FastAPI/Jinja2 web app
**Researched:** 2026-03-01
**Confidence:** HIGH

## Executive Summary

This milestone adds a 4-step onboarding wizard to an existing, production FastAPI/Jinja2 application. Research across stack, features, architecture, and pitfalls converges on a clear recommendation: build with zero new dependencies, integrate deeply with existing endpoints, and keep the wizard lean (4 steps maximum). The existing stack — Tailwind v4 CDN, vanilla JS, Jinja2 server rendering, PostgreSQL — handles everything the wizard requires. The work is technique selection and careful integration, not new technology adoption.

The recommended approach is server-side step rendering via a single `welcome.html` template driven by a `step` URL parameter, with client-side AJAX calls reusing existing endpoints for data persistence (area selection, notification toggles). Wizard state lives in the URL path, not in JavaScript or server session — this survives refresh naturally and is consistent with how the rest of the app works. The only new persistent state is a single `onboarding_completed` boolean column on the `users` table.

The dominant risk is the existing-user migration: adding `onboarding_completed DEFAULT FALSE` without a backfill will force every existing configured user through the wizard on their next login. A one-line backfill (`UPDATE users SET onboarding_completed = TRUE WHERE local_area_id IS NOT NULL`) eliminates this entirely. Secondary risks are GDPR compliance on the notification step (pre-checked toggles are illegal), and accessibility gaps (focus management on step transitions). Both are well-understood and have specific, low-effort fixes documented in PITFALLS.md.

## Key Findings

### Recommended Stack

No new libraries or frameworks are needed. The entire wizard is achievable with CSS `@keyframes` animations declared in a `<style type="text/tailwindcss">` block, vanilla JS state management using a plain object + `sessionStorage`, and Jinja2 template conditionals for step rendering. Tailwind v4 CDN supports `@theme` custom animation tokens natively, making direction-aware slide transitions a zero-dependency CSS exercise.

**Core technologies:**
- `@keyframes` + Tailwind v4 `@theme` tokens: Step transition animations — no library, works in CDN mode
- Vanilla JS `WizardState` object + `sessionStorage`: Client-side step direction tracking — 80 lines, no Alpine.js needed
- `display: none` / Tailwind `hidden` + `aria-hidden`: Step visibility toggling — avoids tab-stop leakage into hidden steps
- HTML `<ol>` with Tailwind data-attribute variants: Progress indicator dots — fully accessible, zero custom CSS
- `<picture>` with WebP + PNG fallback: Ravemonger mascot — correct format for a raster character asset
- `aria-live="polite"` region + `requestAnimationFrame` flush: Screen reader step announcements — WCAG 2.2 SC 4.1.3 compliance

**Hard constraint:** The Tailwind CDN prohibits `@apply`. All styling must be utility classes in HTML or `@keyframes`/`@theme` in the `<style type="text/tailwindcss">` block.

### Expected Features

The 4-step structure identified in FEATURES.md is optimal — it sits exactly at the 3-5 step ceiling where completion rates hold above 60%. Any step added beyond this point statistically doubles abandonment probability.

**Must have (table stakes):**
- Visible skip / dismiss on every step — forced tours are the #1 cited anti-pattern; always-skippable flows have 25% higher completion rates
- Step progress indicator (dot row) — users abandon when they cannot gauge remaining length
- 3-5 step limit — the proposed 4-step flow (welcome, area, feature tour, notifications) hits this exactly
- Mobile-first layout with 44px touch targets — app is mobile-primary; a wizard that breaks at 375px undermines trust
- Persistent state surviving refresh — step in URL path, data saved per-step via existing AJAX endpoints
- Revisitable from Settings — "Revisit Tour" link; wizard renders identically for first-run and revisit
- Functional CTA per step — area selection and notification toggles must actually save data
- Works without JS for navigation — use standard form POST for step transitions; layer JS on top

**Should have (differentiators):**
- Ravemonger mascot with step-aware dialogue — character-guided onboarding reduces cognitive load; static image + changing speech bubble copy (no animation required)
- Short punchy copy per step (under 30 words) — treat each step like a tweet; wall-of-text is the #1 dismissal trigger
- Partial completion handling — store current step in URL; user refreshes and resumes on the same step
- Completion micro-celebration — single CSS confetti or Ravemonger "thumbs up" variant on final step only
- Inline area search on step 2 — reuse existing AJAX area widget without redirecting away
- Notification opt-in with value context — one sentence of "why" before the toggle primes consent
- "You can change this any time" reassurance — reduces choice anxiety on area and notification steps

**Defer (outside wizard scope):**
- Interactive tooltip overlays on live app pages — high cost, low signal at current user scale
- Per-step DB progress persistence (use URL path for step state; only `onboarding_completed` flag needs the DB)
- Advanced notification configuration (digest timing, etc.) — belongs in `/settings`
- Gamification points, badges — Rave Tracker has no gamification system; dangling feature

### Architecture Approach

The wizard is a pure integration exercise into the existing architecture. One new template (`welcome.html`), three new routes, one new DB column, one DB method, and a 5-line modification to the login POST handler. Every data-saving action in the wizard calls an existing endpoint — the wizard adds no new API surface for data. The login intercept (`if not fresh_user.onboarding_completed` redirect to `/welcome/step/1`) is the only structural change to the authentication flow.

**Major components:**
1. Migration 14 (`onboarding_completed` column + backfill) — prerequisite for all other work; must land first
2. `/welcome` and `/welcome/step/{step}` routes — server-renders `welcome.html` at correct step; step clamped to 1-4
3. `welcome.html` template — single file, step-conditional via `{% if step == N %}`; suppresses nav via block override
4. Login POST intercept — 5-line addition checking `onboarding_completed` after successful auth
5. Settings "Revisit Tour" link — purely additive; links to `/welcome/step/1`
6. `POST /welcome/complete` route — sets flag, redirects to dashboard

**Reused without modification:** `GET /api/search/areas`, `POST /api/user/local-area`, `POST /settings/notifications/telegram`, `POST /settings/notifications/email`, `POST /settings/telegram/link`.

### Critical Pitfalls

1. **Retroactive wizard trigger on existing users** — Add `UPDATE users SET onboarding_completed = TRUE WHERE local_area_id IS NOT NULL OR telegram_chat_id IS NOT NULL` as part of Migration 14. Must be in the migration itself, not as a separate manual step. Address before any wizard UI is built.

2. **GDPR non-compliance on notification step** — `email_enabled` defaults to `TRUE` in the DB. The wizard notification step must render toggles as unchecked regardless of DB default for new users. Affirmative action required; skip writes nothing. Pre-checked consent is a GDPR Article 7 violation.

3. **Duplicate preference paths creating divergent state** — Wizard fields must be seeded from current DB values on each render (not hardcoded defaults). "Skip" must write nothing. Both conditions are enforced by routing through existing endpoints rather than creating new save logic.

4. **Inaccessible step transitions** — On each step advance, move focus to the step heading. Add `aria-live="polite"` announcement region. Apply `role="dialog"` + `aria-modal="true"` to wizard container. Trap focus inside. Missing any of these fails WCAG 2.2 SC 4.1.3.

5. **Wizard shown before email verification** — Gate the wizard trigger on both conditions: `email_verified AND NOT onboarding_completed`. The `require_verified_email` dependency already handles this for the wizard routes themselves; the login intercept must also check it.

## Implications for Roadmap

Based on combined research, the build order follows a strict dependency chain. Each phase unblocks the next; they cannot be reordered without creating broken states in the development environment.

### Phase 1: Database Foundation
**Rationale:** The `onboarding_completed` column must exist before any route, template, or login intercept references it. This is also where the highest-risk decision (existing user backfill) must be locked in before deployment — fixing a bad migration post-production requires a second migration and a deployment window.
**Delivers:** Migration 14 with `onboarding_completed` column + backfill for configured users; `User` dataclass field; all four row-to-User mappings updated; `Database.set_onboarding_completed()` method; both schema constants (SQLite and PostgreSQL) updated.
**Addresses:** Table stakes "persistent state"; pitfall P1 (retroactive trigger); pitfall P12 (wizard before verification).
**Avoids:** Any scenario where existing users see the wizard on first post-deployment login.

### Phase 2: Wizard Routes and Stub Template
**Rationale:** Routes must exist before template work begins so navigation links resolve and route smoke-testing happens independently of UI work. The login intercept is NOT added in this phase — that comes after a working template exists in Phase 4.
**Delivers:** `GET /welcome`, `GET /welcome/step/{step}`, `POST /welcome/complete` routes; stub `welcome.html` that renders the step number confirming routing works.
**Uses:** Existing `get_templates()`, `require_verified_email` dependency, `RedirectResponse` pattern.
**Implements:** Architecture component 2 (wizard routes) and skeleton of component 3 (template).

### Phase 3: Welcome Template — Step by Step
**Rationale:** Build each step individually and verify in browser before adding the next. This catches template syntax errors in a 200-line file early. Step 1 first (simplest — static content), then each subsequent step adds a data interaction layer. The notification step must be verified for opaque redirect handling before finalizing.
**Delivers:** Complete `welcome.html` with all 4 steps: (1) Ravemonger welcome + nav suppression, (2) inline area search reusing existing widget JS, (3) notification toggles reusing existing endpoint pattern with `redirect: "manual"` fetch, (4) feature tour static content + finish button calling `POST /welcome/complete`. Skip button on every step. Completion micro-celebration on step 4.
**Uses:** CSS `@keyframes` + Tailwind `@theme` tokens for slide transitions; `WizardState` vanilla JS object; `<picture>` WebP/PNG for mascot; `aria-live` region for screen reader announcements; `<ol>` dot progress indicator with Tailwind data-attribute variants.
**Avoids:** P3 (duplicate preference paths — seed from DB), P4 (mascot fatigue — wizard-only), P6 (GDPR — toggles unchecked for new users), P7 (inaccessibility — focus management and live regions), P9 (mobile CTA off-screen — sticky/full-width CTA), P11 (CSRF missing — csrf_token in every POST).

### Phase 4: Login Intercept and First-Run Trigger
**Rationale:** The intercept is added last because `welcome.html` must fully exist before real users are redirected to it. Adding the intercept before the template is complete would produce broken redirects for all new user registrations during development.
**Delivers:** Modified `POST /login` handler with 5-line `onboarding_completed` check; verified end-to-end flow: register new user, verify email, login, land on `/welcome/step/1`, complete wizard, land on dashboard, subsequent login goes directly to dashboard.
**Implements:** Architecture component 4 (login intercept).
**Avoids:** P12 (wizard before verification — gate is `email_verified AND NOT onboarding_completed`).

### Phase 5: Settings Revisit Link
**Rationale:** Purely additive, zero risk of breaking existing functionality. Placed last so all other verification is complete before introducing this entry point. Revisit path renders without checking `onboarding_completed` so no additional route logic is needed.
**Delivers:** "Revisit Tour" card in `settings.html`; verified: logged-in user with `onboarding_completed = TRUE` can access `/welcome/step/1` and re-complete with wizard seeding current DB values.
**Addresses:** Table stakes "revisitable from settings".
**Avoids:** P8 (stale state on revisit — wizard always seeds from live DB on each step render, not from hardcoded defaults).

### Phase Ordering Rationale

- DB migration must precede routes because the `User` dataclass reads `onboarding_completed` on every authenticated request — missing column causes runtime errors
- Routes must precede the full template to enable URL resolution during template development
- Template must precede the login intercept to prevent broken redirects in the development environment for any new registrations during the build
- Settings link is last because it has no blockers other than a working wizard end-to-end

### Research Flags

Phases with well-documented patterns (skip research-phase):
- **Phase 1:** Standard FastAPI/PostgreSQL migration pattern; documented directly from codebase analysis; no ambiguity
- **Phase 2:** Standard route registration; identical to existing route patterns in `routes.py`
- **Phase 4:** 5-line conditional in login handler; pattern is clear from architecture research
- **Phase 5:** Single HTML addition to `settings.html`; no ambiguity

Phases that may benefit from targeted spot-checks during implementation:
- **Phase 3:** The notification toggle endpoints return `RedirectResponse 303` rather than JSON. The wizard JS must handle opaque redirect responses (`redirect: "manual"`) without triggering a full navigation. This pattern exists in `rules.html` but verify it works identically in the wizard context before finalizing the notification step. One test fetch call is sufficient to confirm.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All techniques are browser-native or Tailwind v4 CDN-confirmed. No new dependencies — minimal risk surface. `@starting-style` explicitly deferred due to confirmed Firefox browser gap documented in MDN. |
| Features | HIGH (structure), MEDIUM (statistics) | 4-step structure is well-validated from multiple sources. Completion rate statistics (25%, 40%, 67% figures) come from MEDIUM-confidence industry sources, not peer-reviewed research — treat as directional, not precise. |
| Architecture | HIGH | Based on direct source code analysis of `routes.py`, `database.py`, and all relevant templates. Integration points verified against actual file contents, not convention. |
| Pitfalls | HIGH | P1 (existing users) and P6 (GDPR) are confirmed against actual DB schema defaults. P2 (refresh state corruption) is architecturally eliminated by the URL-based step decision. P12 (auth gate) confirmed from login route reading. |

**Overall confidence:** HIGH

### Gaps to Address

- **Ravemonger image asset:** The mascot image (WebP + PNG) is pending from the user. The template can be built with a placeholder `<img>` before the asset arrives, but the final visual for steps 1 and 4 is blocked on delivery. Flag this dependency at the start of Phase 3.
- **Nav suppression mechanism in `base.html`:** The template may or may not already have a `{% block nav %}` override point. Check at the start of Phase 3 — if not present, a minor edit to `base.html` is required before the wizard can suppress nav correctly. Low risk, but must be confirmed before step 1 template work.
- **Email default display for new users on notification step:** `email_enabled` defaults to `TRUE` at the DB level. For new users, the notification step must render the toggle as unchecked (requiring affirmative action, per GDPR). For revisit users, show current DB state. The wizard step must distinguish first-run from revisit for this toggle's initial render state. This is a small conditional but must be explicitly handled.
- **Notification opaque redirect pattern:** Confirmed to exist in `rules.html` — verify the `redirect: "manual"` fetch approach works when called from inside the wizard step 3 before finalizing that step's JS.

## Sources

### Primary (HIGH confidence)
- `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/database.py` — Schema, MIGRATIONS pattern, User dataclass, migration runner, row mapping sites
- `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/web/routes.py` — Login flow, existing endpoints, AJAX patterns, redirect chain
- `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/web/templates/rules.html` — Area widget JS, opaque redirect fetch pattern (`redirect: "manual"`)
- `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/web/templates/settings.html` — Notification toggle UI pattern
- `/c/CLAUDE/ra-tips/ra-tracker/ra_tracker/web/templates/base.html` — CSS variables, component class names, layout conventions
- Tailwind CSS v4 CDN docs: tailwindcss.com/docs/installation/play-cdn
- ARIA live region MDN: developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live
- WCAG 2.2 SC 4.1.3 (Status Messages)
- W3C ARIA Authoring Practices Guide: w3.org/WAI/ARIA/apg/

### Secondary (MEDIUM confidence)
- Chameleon: Product Tour Completion Rate Data (550M data points) — completion rate benchmarks by step count
- NNGroup: Bottom Sheets UX Guidelines — mobile layout and touch target patterns
- Appcues: Duolingo User Onboarding Breakdown — mascot and copy tone reference
- Appcues: Mobile Permission Priming — notification opt-in value context pattern
- UserGuiding: Onboarding Statistics 2026 — step count abandonment data
- Tailwind v4 GitHub discussions #16041, #16482 — CDN `@theme` and `@keyframes` confirmation

### Tertiary (directional only)
- Raw Studio: How Mascots Improve UX — 25% drop-off reduction figure (single source, treat as directional)
- SpeedVitals: WebP vs AVIF 2025 — browser support percentages for image format decision
- DesignerUp: I Studied 200 Onboarding Flows — general UX pattern validation

---
*Research completed: 2026-03-01*
*Ready for roadmap: yes*
