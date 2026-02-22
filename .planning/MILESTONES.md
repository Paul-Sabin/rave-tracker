# Project Milestones: Rave Tracker

## v3.2 Tracking Page UX (Shipped: 2026-02-22)

**Delivered:** Tracking page overhaul — Berlin default for new signups, persistent area widget replacing the warning card, and /rules renamed to /tracking.

**Phases completed:** Phase 15 (1 plan)

**Key accomplishments:**

- New users get Berlin (area ID 34) as their default local area at registration — dashboard is populated from first login
- Persistent area widget at top of /tracking page: shows current area, "Change" reveals inline search, selecting auto-saves via new `POST /api/user/local-area` endpoint
- Yellow "Set your local region" warning card removed
- /rules → /tracking rename across all routes, nav, form actions, and dashboard link; 301 redirect preserves old bookmarks

**Stats:**

- 1 phase, 1 plan
- 5 files modified
- 1 commit: `ae4d07f`
- Timeline: 2026-02-22 (1 day)

**Git range:** `ae4d07f`

**Archive:** `.planning/milestones/v3.2-ROADMAP.md`

---

## v3.1 Production Deployment, Hosting & Observability (Shipped: 2026-02-20)

**Delivered:** Rave Tracker is live in production on Railway with PostgreSQL, HTTPS, custom domain, scraper resilience, and full observability stack (structured logging, Sentry, Better Stack, Telegram alerts).

**Phases completed:** Phases 10–14 (14 plans, 5 phases)

**Key accomplishments:**

- All secrets externalized to Railway environment variables; config.yaml contains no hardcoded credentials
- Dual-mode PostgreSQL/SQLite database layer with automatic placeholder translation and connection pooling
- Multi-process production server: gunicorn + uvicorn workers with separated APScheduler process
- Deployed to Railway with custom domain (ravetracker.whotrustswho.com), provider-managed PostgreSQL, automated backups, and git-push deployments
- RA.co scraper hardened with exponential backoff, User-Agent rotation, circuit breaker (3-strike open, 30-min recovery)
- Structured JSON logging with X-Request-ID correlation headers shipped to Better Stack
- Sentry error tracking with request_id tag and per-request user context
- Scraper fetch cycle persistence across gunicorn workers; admin dashboard shows success rate, trend, and fetch history
- Telegram admin alerts after 3 consecutive scraper failures with silence-until-recovery logic

**Stats:**

- 5 phases, 14 plans across Phases 10–14
- 73 files changed, +13,000 / −443 lines
- 8,921 lines of Python
- Timeline: 2026-02-12 → 2026-02-20 (8 days)
- 25 requirements shipped (ENV-01–03, DB-01–05, SRV-01–04, HOST-01–05, SCRAPE-01–04, OBS-01–04)

**Git range:** `feat(10-01)` → `feat(14-04)`

**Archive:** `.planning/milestones/v3.1-ROADMAP.md`

---

## v2.2 UX Polish & Branding (Shipped: 2026-02-10)

**Delivered:** Rebranded to "Rave Tracker", improved region selection UX with per-user local area storage, and cleaned up legacy UI elements.

**Phases completed:** Phase 9 (3 plans)

**Key accomplishments:**

- Rebranded all user-facing text from "RA Tracker" to "Rave Tracker" (web UI, emails, Telegram)
- Dashboard toggle labels changed to "Global events" / "Local only"
- Region selection prompt for new users without configured local area
- Per-user local area storage moved from global config to database
- Legacy admin welcome banner removed

**Stats:**

- 3 plans across 1 phase
- 27 files modified
- 5 requirements shipped (BRAND-01, BRAND-02, UX-01, UX-02, UX-03)

**Git range:** `feat(09-01)` → `feat(09-03)`

**What's next:** TBD

---

## v2.1 Security Hardening (Shipped: 2026-02-08)

**Delivered:** Comprehensive security hardening with audit logging, CSRF protection, email verification, password management, and account lifecycle.

**Phases completed:** 5-8 (11 plans total)

**Key accomplishments:**

- Audit logging infrastructure with forever retention
- CSRF protection (Double Submit Cookie pattern)
- Login rate limiting (dual IP/email) and password reset rate limiting
- Mandatory email verification for all users
- Password reset and change flows with NIST SP 800-63B compliance
- Soft-delete account with 30-day recovery period
- Admin audit log UI with filtering and pagination

**Stats:**

- 11 plans across 4 phases
- 25 requirements shipped

**Git range:** `feat(05-01)` → `feat(08-03)`

**What's next:** v2.2 UX Polish & Branding

---

## v2.0 Multi-User Support (Shipped: 2026-02-01)

**Delivered:** Full multi-user support with authentication, per-user data isolation, and configurable Telegram/Email notifications.

**Phases completed:** 1-4 (14 plans total)

**Key accomplishments:**

- Multi-user database schema with Argon2id password hashing
- Registration, login, logout with secure cookie sessions
- Tailwind CSS v4 mobile-first UI with 44px touch targets
- Privacy Policy page with explicit consent checkbox
- Per-user rules and notification isolation with shared event cache
- Telegram bot linking and Email notifications with one-click unsubscribe

**Stats:**

- 14 plans across 4 phases
- 4,467 lines of Python
- 61 commits over 13 days
- 25 requirements shipped

**Git range:** `feat(01-01)` → `feat(04-05)`

**What's next:** v2.1 Security Hardening

---

## v1.0 Core Functionality (Shipped: 2026-01-19)

**Delivered:** Single-user RA event tracker with rule-based monitoring and Telegram notifications.

**Key accomplishments:**

- GraphQL integration with ra.co API
- SQLite database with rules, events, notifications
- FastAPI web dashboard with event listings
- APScheduler background event fetching
- Telegram notifications for new events

**What's next:** v2.0 Multi-User Support


