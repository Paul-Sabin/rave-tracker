# Requirements: RA Tracker v2.1

**Defined:** 2026-02-02
**Core Value:** Users never miss events from artists, venues, or promoters they care about

## v2.1 Requirements

Requirements for Security Hardening & Account Lifecycle milestone.

### Authentication Hardening

- [ ] **SEC-01**: Rate limiting on login route (5 attempts per 15 minutes per IP/email)
- [ ] **SEC-02**: Rate limiting on password reset requests (3 per hour per email)
- [x] **SEC-03**: Global CSRF protection on all POST forms (token-based)
- [ ] **SEC-04**: Email verification required for new user registration
- [ ] **SEC-05**: Existing unverified users must verify on next login
- [ ] **SEC-06**: Verification email with secure token link
- [ ] **SEC-07**: Resend verification email option

### Account Management

- [ ] **ACCT-01**: Password reset request form (enter email)
- [ ] **ACCT-02**: Password reset email with secure expiring token (24h)
- [ ] **ACCT-03**: Password reset completion form (enter new password)
- [ ] **ACCT-04**: Change password form (current + new password, authenticated)
- [ ] **ACCT-05**: Delete account request (password confirmation)
- [ ] **ACCT-06**: Soft delete marks account inactive (30-day grace period)
- [ ] **ACCT-07**: Account recovery during grace period (login restores)
- [ ] **ACCT-08**: Hard purge after grace period (cascade delete all user data)

### Audit Logging

- [x] **AUDIT-01**: Audit log database schema (event_type, user_id, ip, timestamp, details)
- [ ] **AUDIT-02**: Log login attempts (success and failure with IP)
- [ ] **AUDIT-03**: Log password changes
- [ ] **AUDIT-04**: Log password reset requests and completions
- [ ] **AUDIT-05**: Log account creation
- [ ] **AUDIT-06**: Log account deletion requests and purges
- [ ] **AUDIT-07**: Log email verification status changes
- [ ] **AUDIT-08**: Admin audit log page at /admin/audit-log
- [ ] **AUDIT-09**: Audit log filtering (by user, event type, date range)
- [x] **AUDIT-10**: Forever retention (no auto-purge)

## v2.2+ Candidates

Deferred to future milestones.

- **SEC-08**: Login attempt notifications to user
- **SEC-09**: Two-factor authentication (TOTP)
- **ACCT-09**: Account export (GDPR data portability)
- **AUDIT-11**: Audit log export (CSV/JSON)

## Out of Scope

Explicitly excluded from this milestone.

| Feature | Reason |
|---------|--------|
| OAuth/social login | Email/password auth sufficient, avoid external dependencies |
| Hardware security keys | Complexity beyond current needs |
| Real-time login alerts | Email notifications sufficient for v2.1 |
| Audit log pagination | Filtering sufficient for expected volume |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 6 | Pending |
| SEC-02 | Phase 7 | Pending |
| SEC-03 | Phase 5 | Complete |
| SEC-04 | Phase 6 | Pending |
| SEC-05 | Phase 6 | Pending |
| SEC-06 | Phase 6 | Pending |
| SEC-07 | Phase 6 | Pending |
| ACCT-01 | Phase 7 | Pending |
| ACCT-02 | Phase 7 | Pending |
| ACCT-03 | Phase 7 | Pending |
| ACCT-04 | Phase 7 | Pending |
| ACCT-05 | Phase 8 | Pending |
| ACCT-06 | Phase 8 | Pending |
| ACCT-07 | Phase 8 | Pending |
| ACCT-08 | Phase 8 | Pending |
| AUDIT-01 | Phase 5 | Complete |
| AUDIT-02 | Phase 6 | Pending |
| AUDIT-03 | Phase 7 | Pending |
| AUDIT-04 | Phase 7 | Pending |
| AUDIT-05 | Phase 6 | Pending |
| AUDIT-06 | Phase 8 | Pending |
| AUDIT-07 | Phase 6 | Pending |
| AUDIT-08 | Phase 8 | Pending |
| AUDIT-09 | Phase 8 | Pending |
| AUDIT-10 | Phase 5 | Complete |

**Coverage:**
- v2.1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0

---
*Requirements defined: 2026-02-02*
*Last updated: 2026-02-02 after Phase 5 completion*
