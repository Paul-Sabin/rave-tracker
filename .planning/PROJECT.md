# RA Tracker

## What This Is

A personal event tracker that monitors ra.co for upcoming events from artists, venues, and promoters you follow. It fetches events via the RA GraphQL API, caches them locally, provides a web dashboard for browsing, and sends Telegram notifications for new events.

Currently single-user; evolving toward multi-user support.

## Core Value

Users never miss events from artists, venues, or promoters they care about — automatic monitoring replaces manual checking of ra.co.

## Requirements

### Validated

<!-- Shipped and confirmed valuable (Milestone 1). -->

- [x] **FETCH-01**: System fetches events from ra.co GraphQL API for tracked entities — existing
- [x] **FETCH-02**: Events are cached in SQLite database with deduplication — existing
- [x] **FETCH-03**: Background scheduler fetches events at configurable interval — existing
- [x] **RULE-01**: User can add tracking rules for artists, venues, or promoters — existing
- [x] **RULE-02**: User can search ra.co for entities to track — existing
- [x] **RULE-03**: User can delete tracking rules — existing
- [x] **RULE-04**: User can set notify mode per rule (always/new/never) — existing
- [x] **UI-01**: Web dashboard displays upcoming events grouped by date — existing
- [x] **UI-02**: Events show venue, artists, and link to ra.co — existing
- [x] **UI-03**: Dashboard shows which rules matched each event — existing
- [x] **NOTIF-01**: Telegram notifications sent for new events matching rules — existing
- [x] **NOTIF-02**: Notifications deduplicated to prevent repeats — existing
- [x] **CONFIG-01**: YAML configuration for Telegram, scheduler, web server — existing

### Active

<!-- Milestone 2: Multi-User Support -->

- [ ] **AUTH-01**: User can register with email and password
- [ ] **AUTH-02**: User can log in with email and password
- [ ] **AUTH-03**: User can log out
- [ ] **AUTH-04**: User session persists across browser refresh (session cookies)
- [ ] **AUTH-05**: Passwords are securely hashed (bcrypt or argon2)
- [ ] **MULTI-01**: Database schema supports multiple users
- [ ] **MULTI-02**: Rules are scoped to the user who created them
- [ ] **MULTI-03**: Notification history is scoped per user
- [ ] **MULTI-04**: Events are shared globally (single cache, multiple users' rules)
- [ ] **MULTI-05**: Each user can link Telegram by messaging the bot (auto-detects chat ID)
- [ ] **MULTI-06**: Admin configures shared Telegram bot token
- [ ] **SESSION-01**: Session management with secure cookies
- [ ] **SESSION-02**: Sessions expire after configurable timeout
- [ ] **SESSION-03**: User can see active sessions (stretch)

### Out of Scope

- OAuth/social login — email/password sufficient for v1 multi-user
- Per-user Telegram bot tokens — shared bot simplifies setup
- Fully isolated event caches per user — unnecessary duplication, events are public data
- Mobile app — web-first
- Real-time WebSocket updates — polling/refresh sufficient
- Password reset via email — requires email sending infrastructure, defer to later

## Context

**Existing Codebase:**
- Layered architecture: API client → Services → Web/Scheduler → Database
- Global singletons for config/database (will need refactoring for multi-user)
- SQLite database with rules, events, notifications tables
- FastAPI web server with Jinja2 templates
- APScheduler for background event fetching
- No authentication currently — all routes publicly accessible

**Technical Debt to Address:**
- Global singleton pattern makes testing and multi-user difficult
- No CSRF protection on forms
- Web server binds to 0.0.0.0 by default (security concern with auth)

**Known Issues:**
- Artist tuple unpacking bug in notifier (3-tuple vs 2-tuple)
- Exposed Telegram bot token in config.yaml (needs rotation)

## Constraints

- **Database**: SQLite — sufficient for expected user count, simpler deployment
- **Stack**: Python/FastAPI — maintain consistency with existing codebase
- **Auth Library**: Use established library (e.g., passlib for hashing, itsdangerous for sessions)
- **No Email Sending**: Avoid email infrastructure complexity for now (no password reset emails)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Email/password auth over OAuth | Simpler implementation, no external dependencies | — Pending |
| Shared event cache, per-user rules | Events are public data, avoid duplication | — Pending |
| Shared Telegram bot, per-user chat ID | Simpler user onboarding, admin manages bot | — Pending |
| SQLite over PostgreSQL | Sufficient scale, simpler deployment | — Pending |

---
*Last updated: 2026-01-19 after Milestone 2 initialization*
