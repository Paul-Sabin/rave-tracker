# Project State: Rave Tracker

**Last Updated:** 2026-02-08
**Current Milestone:** v2.2 UX Polish & Branding
**Current Phase:** Not started (defining requirements)

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-08)

**Core value:** Users never miss events from artists, venues, or promoters they care about
**Current focus:** Rebrand to "Rave Tracker", improve region selection UX, clean up legacy UI

## Milestone Progress

| Milestone | Status | Notes |
|-----------|--------|-------|
| 1 - Core Functionality | Complete | Single-user event tracker with fetching, rules, notifications |
| 2 - Multi-User Support | Complete | 4 phases, 14 plans, 25 requirements shipped |
| 3 - Security Hardening | Complete | 4 phases (5-8), 25 requirements shipped |
| 4 - UX Polish & Branding | In Progress | Defining requirements |

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-02-08 — Milestone v2.2 started

Progress: [░░░░░░░░░░] 0% of v2.2

## What's Shipped

**v2.0 Multi-User Support (2026-02-01):**
- Multi-user authentication with Argon2id password hashing
- Per-user rules and notification isolation
- Telegram bot linking and Email notifications
- Mobile-first responsive UI with Tailwind CSS v4
- Privacy Policy with explicit consent

**v2.1 Security Hardening (2026-02-08):**
- Audit logging infrastructure with forever retention
- CSRF protection (Double Submit Cookie pattern)
- Login rate limiting (dual IP/email)
- Email verification (mandatory for all users)
- Password reset and change flows
- Soft-delete account with 30-day recovery
- Admin audit log with filtering and pagination

## Accumulated Decisions

See .planning/milestones/v2.0-ROADMAP.md for full decision log from Milestone 2.

Key patterns established:
- Argon2id for password hashing
- httponly/secure/samesite cookies
- Cycling buttons for mode toggles
- AJAX forms to preserve scroll position
- 44px touch targets (WCAG AAA)

## Accumulated Context

**Decisions (v2.1):**
- Forever retention for audit logs (no auto-purge) per AUDIT-10
- JSON details column for flexible audit context without schema migrations
- Non-blocking audit writes (errors logged but don't fail requests)
- Event type format: category.action (e.g., auth.login_success, rule.create)
- Double Submit Cookie pattern for CSRF (stateless, no server-side token storage)
- CSRF cookie httponly=False (JS must read for AJAX header injection)
- Telegram webhook exempt from CSRF (external caller with own auth)
- Dual rate limiting: both IP AND email must pass (prevents distributed attacks)
- Email SHA256-hashed in rate limit keys (privacy: no plaintext storage)
- Rate limit checked BEFORE password verification (prevents timing attacks)
- Successful login clears rate limit counters (no lockout after correct password)
- Verification tokens use 'email-verify' salt (separate from 'email-unsubscribe')
- 24-hour verification token expiry
- get_user_id_from_expired_token helper for auto-resend flow
- Redirect unverified users to /verify-email (not 403)
- Auto-send new verification email when expired link clicked
- Migration 9 auto-verifies existing admin users
- python-dotenv for sensitive config (.env file, gitignored, loaded at startup)
- BREVO_SMTP_USERNAME/PASSWORD and SECRET_KEY/BASE_URL env vars (short names preferred)
- Pure ASGI middleware for CSRF (avoids BaseHTTPMiddleware body consumption issues)
- Password reset tokens use 'password-reset' salt (separate from verification)
- NIST SP 800-63B password rules: min 8 chars, no complexity requirements, common password blocklist
- ResetRateLimiter tracks email only (not IP) - targeted attack prevention
- Case-insensitive common password comparison (prevents Password vs password bypass)
- Password change keeps session valid (user proved identity via current password)
- Password reset invalidates all sessions (password may have been compromised)
- zxcvbn CDN for client-side password strength meter (no build tooling)
- Soft delete with 30-day grace period (deleted_at + scheduled_purge_at columns)
- Daily purge cron job at 3 AM UTC using APScheduler CronTrigger
- Audit log anonymization: NULL user_id + anonymized flag + 8-char SHA256 hash
- log_audit_event_direct helper for background job audit logging
- Audit log filtering uses LEFT JOIN for user info, prefix matching for event type/IP
- Password-only confirmation for account deletion (no checkbox or typing 'delete')
- Recovery via login intercept shows interstitial before session creation
- Flash messages via query params (deleted, deletion_confirmed, recovered)

**Technical Debt:**
- None

**Blockers:**
- None

## Session History

| Date | Action | Outcome |
|------|--------|---------|
| 2026-01-19 | Initialized Milestone 2 | PROJECT.md, REQUIREMENTS.md, ROADMAP.md |
| 2026-01-23 | Executed Phase 1 | Database schema complete |
| 2026-01-27 | Executed Phase 2 | Authentication complete |
| 2026-01-29 | Executed Phase 3 | Multi-tenant access complete |
| 2026-01-31 | Executed Phase 4 | User notifications complete |
| 2026-02-01 | Completed Milestone 2 | Archived to milestones/v2.0-* |
| 2026-02-02 | Initialized Milestone 3 | v2.1 ROADMAP.md, STATE.md updated |
| 2026-02-02 | Executed 05-01 | Audit logging infrastructure complete |
| 2026-02-02 | Executed 05-02 | CSRF protection complete |
| 2026-02-02 | Completed Phase 5 | Audit Foundation & CSRF Protection complete |
| 2026-02-03 | Executed 06-01 | Login rate limiting and auth audit logging complete |
| 2026-02-03 | Executed 06-02 | Verification token and email infrastructure complete |
| 2026-02-06 | Executed 06-03 | Email verification flow UI and integration complete |
| 2026-02-06 | Completed Phase 6 | Email Verification & Login Hardening complete |
| 2026-02-07 | Fixed CSRF middleware | Rewrote as pure ASGI to fix body consumption issue |
| 2026-02-07 | Added python-dotenv | Sensitive config via .env file, env var overrides for email/app |
| 2026-02-07 | Executed 07-01 | Password infrastructure complete (tokens, validation, rate limiter) |
| 2026-02-07 | Executed 07-02 | Password reset flow complete (forgot password, reset email, routes) |
| 2026-02-07 | Executed 07-03 | Password change complete (settings, strength meter, routes) |
| 2026-02-07 | Completed Phase 7 | Password Management complete |
| 2026-02-08 | Executed 08-01 | Soft delete infrastructure (migration, methods, purge cron job) |
| 2026-02-08 | Executed 08-02 | Admin audit log complete (filtering, pagination, template) |
| 2026-02-08 | Executed 08-03 | Account deletion and recovery flows complete |
| 2026-02-08 | Completed Phase 8 | Account Lifecycle & Admin Audit UI complete |
| 2026-02-08 | Completed Milestone 3 | v2.1 Security Hardening complete |
| 2026-02-08 | Initialized Milestone 4 | v2.2 UX Polish & Branding started |

## Session Continuity

Last session: 2026-02-08
Stopped at: Defining v2.2 requirements
Resume file: None

---
*State updated: 2026-02-08*
