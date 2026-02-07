# Milestone v2.1: Security Hardening & Account Lifecycle

**Status:** In Progress
**Phases:** 5-8
**Total Requirements:** 25

## Overview

Harden authentication with rate limiting and CSRF protection, implement mandatory email verification, add password reset and change functionality, enable soft-delete account with recovery, and build comprehensive audit logging with admin visibility.

## Phases

### Phase 5: Audit Foundation & CSRF Protection

**Goal:** Establish audit logging infrastructure and global form security so all subsequent features can log events securely
**Depends on:** v2.0 (authentication, sessions)
**Requirements:** AUDIT-01, AUDIT-10, SEC-03
**Plans:** 2 plans (Wave 1: parallel)

Plans:
- [x] 05-01-PLAN.md - Audit log schema and service
- [x] 05-02-PLAN.md - CSRF middleware and template integration

**Success Criteria:**
1. All POST forms include CSRF token and reject requests without valid token
2. Audit log table exists with event_type, user_id, ip, timestamp, details columns
3. Audit records are never deleted (forever retention enforced at schema level)

---

### Phase 6: Email Verification & Login Hardening

**Goal:** Users must verify email ownership before using the application, with protection against brute-force login attempts
**Depends on:** Phase 5
**Requirements:** SEC-01, SEC-04, SEC-05, SEC-06, SEC-07, AUDIT-02, AUDIT-05, AUDIT-07
**Plans:** 3 plans (Wave 1: 2 parallel, Wave 2: 1 sequential)

Plans:
- [x] 06-01-PLAN.md - Rate limiting infrastructure and login audit logging
- [x] 06-02-PLAN.md - Email verification tokens and verification email
- [x] 06-03-PLAN.md - Verification flow UI and registration/login integration

**Success Criteria:**
1. New users receive verification email and cannot access dashboard until verified
2. Existing unverified users are redirected to verification prompt on login
3. User can request new verification email if original expired/lost
4. After 5 failed login attempts in 15 minutes, further attempts are blocked (by IP and email)
5. All login attempts (success/fail), account creations, and verification status changes appear in audit log

---

### Phase 7: Password Management

**Goal:** Users can reset forgotten passwords via email and change passwords when logged in
**Depends on:** Phase 6 (email token infrastructure)
**Requirements:** SEC-02, ACCT-01, ACCT-02, ACCT-03, ACCT-04, AUDIT-03, AUDIT-04
**Plans:** 3 plans (Wave 1: 1, Wave 2: 2 parallel)

Plans:
- [ ] 07-01-PLAN.md - Password infrastructure (tokens, validation, rate limiting)
- [ ] 07-02-PLAN.md - Password reset flow (forgot password, email, reset form)
- [ ] 07-03-PLAN.md - Password change (authenticated, settings integration)

**Success Criteria:**
1. User can request password reset by entering email, receives link with 24h expiring token
2. User can set new password via reset link without being logged in
3. Logged-in user can change password by confirming current password
4. Password reset requests are rate-limited (3 per hour per email)
5. All password changes and reset requests/completions appear in audit log

---

### Phase 8: Account Lifecycle & Admin Audit UI

**Goal:** Users can delete their accounts with a recovery period, and admins can view complete audit history
**Depends on:** Phase 7
**Requirements:** ACCT-05, ACCT-06, ACCT-07, ACCT-08, AUDIT-06, AUDIT-08, AUDIT-09

**Success Criteria:**
1. User can request account deletion (password confirmation required)
2. Deleted account enters 30-day grace period (soft delete, cannot login)
3. User can recover account by logging in during grace period
4. After 30 days, account and all user data are permanently purged
5. Admin can view audit log at /admin/audit-log with filtering by user, event type, and date range

---

## Progress

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 5 | Audit Foundation & CSRF Protection | 3 | Complete |
| 6 | Email Verification & Login Hardening | 8 | Complete |
| 7 | Password Management | 7 | Planned |
| 8 | Account Lifecycle & Admin Audit UI | 7 | Pending |

**Coverage:** 25/25 requirements mapped

## Requirement Mapping

| Requirement | Phase | Description |
|-------------|-------|-------------|
| SEC-01 | 6 | Rate limiting on login route |
| SEC-02 | 7 | Rate limiting on password reset requests |
| SEC-03 | 5 | Global CSRF protection |
| SEC-04 | 6 | Email verification for new users |
| SEC-05 | 6 | Existing users verify on next login |
| SEC-06 | 6 | Verification email with token link |
| SEC-07 | 6 | Resend verification email option |
| ACCT-01 | 7 | Password reset request form |
| ACCT-02 | 7 | Password reset email with token |
| ACCT-03 | 7 | Password reset completion form |
| ACCT-04 | 7 | Change password form |
| ACCT-05 | 8 | Delete account request |
| ACCT-06 | 8 | Soft delete with grace period |
| ACCT-07 | 8 | Account recovery during grace |
| ACCT-08 | 8 | Hard purge after grace period |
| AUDIT-01 | 5 | Audit log database schema |
| AUDIT-02 | 6 | Log login attempts |
| AUDIT-03 | 7 | Log password changes |
| AUDIT-04 | 7 | Log password reset events |
| AUDIT-05 | 6 | Log account creation |
| AUDIT-06 | 8 | Log account deletion events |
| AUDIT-07 | 6 | Log email verification changes |
| AUDIT-08 | 8 | Admin audit log page |
| AUDIT-09 | 8 | Audit log filtering |
| AUDIT-10 | 5 | Forever retention policy |

---
*Roadmap created: 2026-02-02*
*Last updated: 2026-02-07 (Phase 7 planned)*
