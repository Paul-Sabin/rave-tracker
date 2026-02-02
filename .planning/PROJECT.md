# RA Tracker

## What This Is

A multi-user event tracker that monitors ra.co for upcoming events from artists, venues, and promoters you follow. Each user can create tracking rules, configure notification preferences (Telegram and/or Email), and browse events on a mobile-friendly dashboard.

## Core Value

Users never miss events from artists, venues, or promoters they care about — automatic monitoring replaces manual checking of ra.co.

## Current Milestone: v2.1 Security Hardening & Account Lifecycle

**Goal:** Harden authentication, add account management features, and implement audit logging while maintaining mobile-first UI patterns.

**Target features:**
- Rate limiting on sensitive routes (5 attempts / 15 min)
- Global CSRF protection on all forms
- Mandatory email verification (all users, existing verify on next login)
- Token-based password reset via email
- Authenticated password change
- Soft-delete account with 30-day grace period
- Audit logging with forever retention and admin UI

## Current State

**Version:** v2.0 Multi-User Support (shipped 2026-02-01)

**Capabilities:**
- User registration with privacy consent
- Secure login/logout with session management
- Per-user tracking rules for artists, venues, promoters
- Dual-mode filtering: dashboard visibility vs notifications (Global/Local/Off)
- Telegram bot linking with /link, /stop, /start commands
- Email notifications with one-click unsubscribe
- Admin dashboard for user/rule oversight
- Mobile-first responsive design (375px+, 44px touch targets)

**Tech Stack:**
- Python 3.11+ / FastAPI / Jinja2
- SQLite database
- Tailwind CSS v4 (CDN)
- APScheduler for background jobs
- Argon2id password hashing

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

### Active

<!-- v2.1 Security Hardening & Account Lifecycle -->

**Authentication Hardening:**
- [ ] SEC-01: Rate limiting on login (5 attempts / 15 min)
- [ ] SEC-02: Rate limiting on password reset requests
- [ ] SEC-03: Global CSRF protection on all POST forms
- [ ] SEC-04: Mandatory email verification for all users
- [ ] SEC-05: Existing users must verify on next login

**Account Management:**
- [ ] ACCOUNT-01: Password reset via email link (token-based, expiring)
- [ ] ACCOUNT-02: Change password when logged in
- [ ] ACCOUNT-03: Soft-delete account with 30-day grace period
- [ ] ACCOUNT-04: Account recovery during grace period
- [ ] ACCOUNT-05: Hard purge after grace period (cascade delete)

**Audit Logging:**
- [ ] AUDIT-01: Log login attempts (success/fail)
- [ ] AUDIT-02: Log password changes and resets
- [ ] AUDIT-03: Log account creation and deletion
- [ ] AUDIT-04: Log email verification status changes
- [ ] AUDIT-05: Dedicated /admin/audit-log page with filtering
- [ ] AUDIT-06: Forever retention (no auto-purge)

### Out of Scope

- OAuth/social login — email/password sufficient
- Per-user Telegram bot tokens — shared bot simpler
- Per-user event caches — events are public data
- Mobile app — web-first approach
- Real-time WebSocket updates — polling sufficient

## Context

**Codebase:**
- 4,467 lines of Python across 15 modules
- Layered architecture: API client → Services → Web/Scheduler → Database
- Full codebase documentation in `.planning/codebase/`

**Infrastructure:**
- SQLite database (sufficient for expected scale)
- Single-process deployment (web + scheduler in one process)
- Config via YAML file with environment overrides

## Constraints

- **Database:** SQLite — simpler deployment, sufficient scale
- **Stack:** Python/FastAPI — consistency with existing code
- **Auth:** Built-in (no OAuth) — avoid external dependencies
- **Email:** Requires SMTP configuration by admin

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Email/password auth over OAuth | Simpler implementation, no external dependencies | ✓ Good |
| Shared event cache, per-user rules | Events are public data, avoid duplication | ✓ Good |
| Shared Telegram bot, per-user chat ID | Simpler user onboarding, admin manages bot | ✓ Good |
| SQLite over PostgreSQL | Sufficient scale, simpler deployment | ✓ Good |
| Argon2id password hashing | OWASP 2025 recommendation | ✓ Good |
| Tailwind v4 via CDN | No build step, rapid iteration | ✓ Good |
| 44px touch targets | WCAG AAA accessibility | ✓ Good |
| Cycling buttons for rule modes | Clear UX, single toggle per setting | ✓ Good |
| AJAX form submissions | Preserve scroll position | ✓ Good |

---
*Last updated: 2026-02-02 after v2.1 milestone initialization*
