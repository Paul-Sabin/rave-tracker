# Rave Tracker

## What This Is

A multi-user event tracker running in production that monitors ra.co for upcoming events from artists, venues, and promoters you follow. Each user can create tracking rules, configure notification preferences (Telegram and/or Email), and browse events on a mobile-friendly dashboard. Deployed on Railway with PostgreSQL, HTTPS, and a custom domain. Branded as "Rave Tracker" (not affiliated with RA).

## Core Value

Users never miss events from artists, venues, or promoters they care about — automatic monitoring replaces manual checking of ra.co.

## Current State

**Version:** v3.3 Settings Split (shipped 2026-02-28)

**Live at:** https://ravetracker.whotrustswho.com

**Capabilities:**
- User registration with privacy consent and email verification
- Secure login/logout with session management and CSRF protection
- Rate limiting on login and password reset
- Per-user tracking rules for artists, venues, promoters
- Dual-mode filtering: dashboard visibility vs notifications (Global/Local/Off)
- Telegram bot linking with /link, /stop, /start commands
- Email notifications with one-click unsubscribe
- Password reset and change flows
- Soft-delete account with 30-day recovery period
- Admin dashboard with audit log viewing, scraper status, health metrics, fetch history
- Split settings: `/settings` (personal — all users) and `/admin/settings` (system config — admin only)
- Dual notification dispatch: "Upon fetch" (immediate) or "Daily digest" (batched per user at configured time)
- Server-side admin guards on all admin-only endpoints
- Mobile-first responsive design (375px+, 44px touch targets)
- Structured JSON logging with request ID correlation (Better Stack)
- Sentry error tracking with user context and request_id tag
- Telegram admin alerts on 3+ consecutive scraper failures

**Tech Stack:**
- Python 3.11+ / FastAPI / Jinja2
- PostgreSQL (production) / SQLite (local dev)
- Tailwind CSS v4 (CDN)
- gunicorn + uvicorn workers (multi-process)
- APScheduler with CronTrigger (separate process)
- Argon2id password hashing
- Sentry, Better Stack (Logtail), asgi-correlation-id
- Railway (hosting + managed PostgreSQL)

## Requirements

### Validated

<!-- Shipped and confirmed valuable -->

**Milestone 1: Core Functionality**
- [x] FETCH-01: System fetches events from ra.co GraphQL API — v1.0
- [x] FETCH-02: Events cached in SQLite with deduplication — v1.0
- [x] FETCH-03: Background scheduler at configurable interval — v1.0
- [x] RULE-01: Add tracking rules for artists/venues/promoters — v1.0
- [x] RULE-02: Search ra.co for entities to track — v1.0
- [x] RULE-03: Delete tracking rules — v1.0
- [x] RULE-04: Set notify mode per rule — v1.0
- [x] UI-01: Dashboard displays events grouped by date — v1.0
- [x] UI-02: Events show venue, artists, link to ra.co — v1.0
- [x] UI-03: Dashboard shows matched rules per event — v1.0
- [x] NOTIF-01: Telegram notifications for new events — v1.0
- [x] NOTIF-02: Notification deduplication — v1.0
- [x] CONFIG-01: YAML configuration for all settings — v1.0

**Milestone 2: Multi-User Support**
- [x] AUTH-01: Register with email and password — v2.0
- [x] AUTH-02: Login with email and password — v2.0
- [x] AUTH-03: Logout — v2.0
- [x] AUTH-04: Session persistence across browser refresh — v2.0
- [x] AUTH-05: Argon2id password hashing — v2.0
- [x] SESSION-01: Secure httponly session cookies — v2.0
- [x] SESSION-02: Configurable session timeout — v2.0
- [x] UI-01: Mobile-first design (375px+, 44px touch targets) — v2.0
- [x] MULTI-01: Multi-user database schema — v2.0
- [x] MULTI-02: Per-user rule scoping — v2.0
- [x] MULTI-03: Per-user notification history — v2.0
- [x] MULTI-04: Shared event cache — v2.0
- [x] TELEGRAM-01: User links Telegram via bot — v2.0
- [x] TELEGRAM-02: Admin configures shared bot token — v2.0
- [x] EMAIL-01: Email to login address — v2.0
- [x] EMAIL-02: Admin configures SMTP — v2.0
- [x] NOTIFY-01: Toggle Telegram on/off — v2.0
- [x] NOTIFY-02: Toggle Email on/off — v2.0
- [x] NOTIFY-03: Channel must be configured — v2.0
- [x] NOTIFY-05: One-click email unsubscribe — v2.0
- [x] NOTIFY-06: Telegram /stop command — v2.0
- [x] PRIVACY-01: Privacy Policy explains data collected — v2.0
- [x] PRIVACY-02: Privacy Policy explains storage — v2.0
- [x] PRIVACY-03: Explicit consent checkbox — v2.0
- [x] PRIVACY-04: Privacy Policy link on registration — v2.0

**Milestone 3: Security Hardening**
- [x] SEC-01: Rate limiting on login (5 attempts / 15 min) — v2.1
- [x] SEC-02: Rate limiting on password reset requests — v2.1
- [x] SEC-03: Global CSRF protection on all POST forms — v2.1
- [x] SEC-04: Mandatory email verification for all users — v2.1
- [x] SEC-05: Existing users must verify on next login — v2.1
- [x] ACCOUNT-01: Password reset via email link (token-based, expiring) — v2.1
- [x] ACCOUNT-02: Change password when logged in — v2.1
- [x] ACCOUNT-03: Soft-delete account with 30-day grace period — v2.1
- [x] ACCOUNT-04: Account recovery during grace period — v2.1
- [x] ACCOUNT-05: Hard purge after grace period (cascade delete) — v2.1
- [x] AUDIT-01: Log login attempts (success/fail) — v2.1
- [x] AUDIT-02: Log password changes and resets — v2.1
- [x] AUDIT-03: Log account creation and deletion — v2.1
- [x] AUDIT-04: Log email verification status changes — v2.1
- [x] AUDIT-05: Dedicated /admin/audit-log page with filtering — v2.1
- [x] AUDIT-06: Forever retention (no auto-purge) — v2.1

**Milestone 4: UX Polish & Branding**
- [x] BRAND-01: Rebrand all user-facing text from "RA Tracker" to "Rave Tracker" — v2.2
- [x] BRAND-02: Email "from" name displays as "Rave Tracker" — v2.2
- [x] UX-01: One-time local region prompt before first rule creation — v2.2
- [x] UX-02: Dashboard toggle labels "Global events" / "Local only" — v2.2
- [x] UX-03: Remove legacy admin welcome banner — v2.2

**Milestone 6: Tracking Page UX**
- [x] UX-04: Berlin (area ID 34) set as default local area for new user signups — v3.2
- [x] UX-05: Persistent area widget on /tracking page; inline search auto-saves without page reload — v3.2
- [x] UX-06: /rules page renamed to /tracking with 301 redirect for old bookmarks — v3.2

**Milestone 7: Settings Split**
- [x] SETT-01: `/settings` shows only Notification Preferences, Account Security, and Delete Account for all users — v3.3
- [x] SETT-02: Local Area section removed from `/settings` entirely — v3.3
- [x] SETT-03: Admin users see a link to `/admin/settings` on `/settings` — v3.3
- [x] SETT-04: `/admin/settings` page created, accessible to admins only — v3.3
- [x] SETT-05: Telegram bot token and admin chat ID editable on `/admin/settings` — v3.3
- [x] SETT-06: Fetch schedule configurable as specific times of day (CronTrigger) — v3.3
- [x] SETT-07: Event horizon (days) editable on `/admin/settings` — v3.3
- [x] SETT-08: Database info displayed (read-only) on `/admin/settings` — v3.3
- [x] SETT-09: Test Admin Telegram button on `/admin/settings` — v3.3
- [x] SETT-10: Notification mode toggle: "Upon fetch completion" vs "Daily digest" — v3.3
- [x] SETT-11: Daily digest time field shown when digest mode is selected — v3.3
- [x] SETT-12: "Upon fetch" mode sends notifications immediately after successful fetch — v3.3
- [x] SETT-13: "Daily digest" mode queues found events rather than sending immediately — v3.3
- [x] SETT-14: Daily digest job sends batched notifications per user at configured time — v3.3
- [x] SETT-15: POST `/settings/save` rejects non-admin requests server-side — v3.3
- [x] SETT-16: POST `/settings/test-telegram` rejects non-admin requests with 403 — v3.3

**Milestone 5: Production Deployment, Hosting & Observability**
- [x] ENV-01: All secrets configured via environment variables — v3.1
- [x] ENV-02: No hardcoded secrets in config.yaml or committed files — v3.1
- [x] ENV-03: .env.example documents all required environment variables — v3.1
- [x] DB-01: Application connects to PostgreSQL via DATABASE_URL — v3.1
- [x] DB-02: DATABASE_URL parsing handles postgres:// and postgresql:// — v3.1
- [x] DB-03: All raw SQL queries work against PostgreSQL — v3.1
- [x] DB-04: Connection pooling configured for production load — v3.1
- [x] DB-05: Database schema migrations run against PostgreSQL — v3.1
- [x] SRV-01: Application runs under gunicorn with uvicorn workers — v3.1
- [x] SRV-02: Scheduler runs as separate process — v3.1
- [x] SRV-03: Health check endpoint returns database connectivity status — v3.1
- [x] SRV-04: Graceful shutdown (in-flight requests complete before exit) — v3.1
- [x] HOST-01: Deployed to Railway hosting provider — v3.1
- [x] HOST-02: Provider-managed PostgreSQL with automated backups — v3.1
- [x] HOST-03: Automated HTTPS/SSL (provider-managed) — v3.1
- [x] HOST-04: Custom domain configured (ravetracker.whotrustswho.com) — v3.1
- [x] HOST-05: Git-push deployment pipeline configured — v3.1
- [x] SCRAPE-01: Exponential backoff on 403/429/5xx responses — v3.1
- [x] SCRAPE-02: User-Agent string rotation — v3.1
- [x] SCRAPE-03: Circuit breaker for extended API outages — v3.1
- [x] SCRAPE-04: Scraper logs response status codes — v3.1
- [x] OBS-01: Structured JSON logs with request IDs and HTTP status codes — v3.1
- [x] OBS-02: Sentry error tracking with stack traces and user context — v3.1
- [x] OBS-03: Scraper health visible (success rate, last fetch, circuit breaker) — v3.1
- [x] OBS-04: Telegram alert on 3+ consecutive scraper failures — v3.1

### Active

<!-- Current milestone: v3.4 Onboarding & Welcome -->

**v3.4 Onboarding & Welcome**

- [ ] Multi-step welcome wizard triggered on first login
- [ ] The Ravemonger character guides the experience (user-provided image asset)
- [ ] Local area selection (keep Berlin default or change)
- [ ] Feature tour (tracking, dashboard, settings orientation)
- [ ] Notification channel preference (Telegram / Email / None)
- [ ] Revisitable from settings
- [ ] Short, snappy, fun tone — not a chore

### Out of Scope

- OAuth/social login — email/password sufficient
- Per-user Telegram bot tokens — shared bot simpler
- Per-user event caches — events are public data
- Mobile app — web-first approach
- Real-time WebSocket updates — polling sufficient
- Docker/Kubernetes — Railway handles orchestration
- Auto-scaling — predictable load, fixed deployment sufficient
- SQLAlchemy ORM — raw SQL works, migration high-effort low-payoff
- Proxy rotation — start conservative, add only if blocked by ra.co

## Context

**Codebase:**
- ~9,300 lines of Python across 20+ modules, ~4,700 lines of HTML templates
- Layered architecture: API client → Services → Web/Scheduler → Database → Observability
- Full codebase documentation in `.planning/codebase/`

**Infrastructure:**
- Railway managed PostgreSQL (production)
- gunicorn + uvicorn workers, APScheduler in separate process
- Sentry (error tracking), Better Stack (log shipping)
- Config via YAML + environment variable overrides

**Known issues:**
- Bot polling error logged on startup: "set_wakeup_fd only works in main thread" — non-fatal, cosmetic log noise from gunicorn worker forking

## Constraints

- **Database:** PostgreSQL (production), SQLite (local dev)
- **Stack:** Python/FastAPI — consistency with existing code
- **Auth:** Built-in (no OAuth) — avoid external dependencies
- **Email:** Requires SMTP configuration by admin
- **Hosting:** Railway — committed to platform for predictability

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Email/password auth over OAuth | Simpler implementation, no external dependencies | ✓ Good |
| Shared event cache, per-user rules | Events are public data, avoid duplication | ✓ Good |
| Shared Telegram bot, per-user chat ID | Simpler user onboarding, admin manages bot | ✓ Good |
| Argon2id password hashing | OWASP 2025 recommendation | ✓ Good |
| Tailwind v4 via CDN | No build step, rapid iteration | ✓ Good |
| 44px touch targets | WCAG AAA accessibility | ✓ Good |
| AJAX form submissions | Preserve scroll position | ✓ Good |
| User-facing rebrand only | Keep ra-tracker/ra_tracker internally, avoid churn | ✓ Good |
| Per-user local area in DB | User preferences in database, not global config | ✓ Good |
| Dual-mode SQLite/PostgreSQL | Local dev convenience, production correctness | ✓ Good |
| Railway over Fly.io/DigitalOcean | Managed PostgreSQL + git-push deploys, lowest ops overhead | ✓ Good |
| gunicorn + uvicorn workers | Multi-process web server, standard for FastAPI in production | ✓ Good |
| APScheduler in separate process | Prevents scheduler duplication across web workers | ✓ Good |
| Circuit breaker for scraper | Prevents infinite retries during extended API outages | ✓ Good |
| Singleton alert_state table | DB-persisted alert state survives worker restarts | ✓ Good |
| SKIPPED status counts as failure | Circuit-open = no data delivered, admin should be alerted | ✓ Good |
| AccessLogMiddleware over uvicorn.access | Structured JSON with request_id, cleaner than plain-text uvicorn logs | ✓ Good |
| Better Stack for logs, not Sentry | Avoid log duplication; Sentry for errors, Better Stack for all logs | ✓ Good |
| Berlin as default local area (ID 34) | Removes silent 90-event exclusion for new users; confirmed via RAClient at implementation | ✓ Good |
| Area widget replaces warning card | Persistent and discoverable without being alarming; inline save avoids settings page detour | ✓ Good |
| /api/rules/add JSON endpoint kept as-is | Only form-based routes renamed; JS fetch calls unchanged | ✓ Good |
| 301 redirect /rules → /tracking | Permanent redirect preserves bookmarks and SEO | ✓ Good |
| Notification mode is system-wide admin policy | Simpler than per-user preference; admin controls digest cadence | ✓ Good |
| Daily digest queues at fetch time, sends at configured time | Decouples event discovery from notification delivery | ✓ Good |
| queue_event_for_digest uses rule_id=0 + UNIQUE(event_id, rule_id) | Consistent dedup pattern with add_event_notification | ✓ Good |
| CronTrigger replaces interval scheduling | fetch_times config is more intuitive than interval-in-minutes | ✓ Good |
| GET /admin/settings redirects non-admins (not 403) | Clean UX — non-admins land on their own settings, not an error page | ✓ Good |
| POST /settings/test-telegram returns JSON 403 (not redirect) | AJAX endpoint — redirect would silently swallow the error in JS callers | ✓ Good |

---
*Last updated: 2026-03-01 after v3.4 milestone started*
