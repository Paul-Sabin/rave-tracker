---
phase: 06-email-verification-login-hardening
plan: 03
subsystem: auth
tags: [email-verification, ui, routes, migration]
dependency-graph:
  requires: ["06-01", "06-02"]
  provides: ["email-verification-flow", "require_verified_email"]
  affects: ["08-admin-ui"]
tech-stack:
  added: []
  patterns: ["verification-redirect", "auto-resend-expired"]
file-tracking:
  key-files:
    created:
      - ra-tracker/ra_tracker/web/templates/verify_email.html
      - ra-tracker/ra_tracker/web/templates/verify_expired.html
    modified:
      - ra-tracker/ra_tracker/web/routes.py
      - ra-tracker/ra_tracker/web/auth.py
      - ra-tracker/ra_tracker/database.py
      - ra-tracker/ra_tracker/web/templates/login.html
decisions:
  - key: verify-page-redirect
    choice: "Redirect unverified users to /verify-email, not 403"
    reason: "Better UX - user can resend or logout"
  - key: auto-resend-on-expired
    choice: "Auto-send new verification email when expired link clicked"
    reason: "Reduces friction - user doesn't need to login first"
  - key: admin-auto-verify
    choice: "Migration 9 auto-verifies existing admin users"
    reason: "Prevents admin lockout after email verification requirement deployed"
metrics:
  duration: "~15 minutes"
  completed: "2026-02-06"
---

# Phase 06 Plan 03: Email Verification Flow UI & Integration Summary

**One-liner:** Complete email verification UI with templates, routes, auth integration, and admin migration

## What Was Built

### 1. Verification UI Templates

**verify_email.html** - "Check your email" holding page:
- Displays user's email address
- Shows 24-hour expiry notice
- Resend button with CSRF protection
- Logout link to use different account
- Success/error message display
- 44px touch targets per CLAUDE.md

**verify_expired.html** - Expired/invalid link page:
- Yellow clock icon indicating time issue
- Dynamic message (expired vs invalid)
- Login redirect button

### 2. Verification Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/verify-email` | GET | Holding page for unverified users |
| `/verify-email/resend` | POST | Resend email (rate limited 3/hour) |
| `/verify/{token}` | GET | Process verification link |

**Verification token flow:**
1. Valid token -> mark user verified -> redirect to /login?verified=1
2. Already verified -> redirect to /login?verified=already
3. Expired token -> auto-resend new email -> show "new link sent" message
4. Invalid token -> show error message

### 3. Auth Flow Updates

**Registration:**
- Sends verification email immediately
- Redirects to /verify-email (not dashboard)
- Audit log: auth.verification_sent with trigger=registration

**Login (unverified user):**
- Sends verification email
- Redirects to /verify-email
- Audit log: auth.verification_sent with trigger=unverified_login

**Login page:**
- Shows success message when ?verified=1
- Shows "already verified" when ?verified=already

### 4. require_verified_email Dependency

New FastAPI dependency in auth.py:
- Returns 303 redirect to /verify-email if not verified
- Used on all protected routes except verify-email routes

**Protected routes (require_verified_email):**
- Dashboard (/)
- Rules (/rules, /rules/*)
- Settings (/settings, /settings/*)
- API (/api/*)
- Actions (/actions/*)

**Unprotected routes (require_auth only):**
- /verify-email
- /verify-email/resend

### 5. Admin Migration

Migration 9 added to database.py:
```sql
UPDATE users SET email_verified = 1 WHERE is_admin = 1;
```
Prevents admin lockout when verification requirement is deployed.

## Commits

| Hash | Description |
|------|-------------|
| 02b77b7 | feat(06-03): add verification UI templates |
| 5a109f7 | feat(06-03): add verification routes and update auth flow |
| b98fd0d | feat(06-03): add require_verified_email and admin migration |

## Files Changed

| File | Changes |
|------|---------|
| `templates/verify_email.html` | Created - holding page with resend |
| `templates/verify_expired.html` | Created - expired link page |
| `templates/login.html` | Added success message display |
| `routes.py` | Added 3 verification routes, updated registration/login |
| `auth.py` | Added require_verified_email dependency |
| `database.py` | Added Migration 9 for admin auto-verify |

## Audit Events Added

| Event | Trigger |
|-------|---------|
| auth.verification_sent | Registration, unverified login, manual resend |
| auth.email_verified | Successful token verification |
| auth.verification_resent_auto | Expired link auto-resend |

## Deviations from Plan

None - plan executed exactly as written.

## Testing Checklist

- [ ] New registration -> redirects to /verify-email
- [ ] Unverified login -> sends email, redirects to /verify-email
- [ ] Resend button -> sends new email (check audit log)
- [ ] Resend 4 times in hour -> rate limited
- [ ] Valid verification link -> redirects to /login?verified=1
- [ ] Expired link -> auto-resends, shows message
- [ ] Invalid link -> shows error
- [ ] Verified user -> can access dashboard
- [ ] Unverified user -> redirected from dashboard to /verify-email
- [ ] Admin users -> auto-verified by migration

## Next Phase Readiness

Phase 6 complete. Ready for Phase 7 (Password Management).

**Dependencies satisfied:**
- Rate limiting infrastructure (06-01)
- Verification tokens and email sending (06-02)
- Email verification flow (06-03) - this plan

**Requirements completed:**
- SEC-04: New user registration sends verification email
- SEC-05: Unverified user login triggers verification email
- SEC-06: Verification link handling (valid, expired, invalid)
- SEC-07: Resend verification email (rate limited)
- AUDIT-07: Verification events logged
