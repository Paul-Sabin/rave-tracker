# Requirements: RA Tracker v2.1

**Defined:** 2026-02-02
**Core Value:** Users never miss events from artists, venues, or promoters they care about

## v2.1 Requirements

Requirements for Security Hardening & Account Lifecycle milestone.

### Authentication Hardening

- [ ] **SEC-01**: Rate limiting on login route (5 attempts per 15 minutes per IP/email)
- [ ] **SEC-02**: Rate limiting on password reset requests (3 per hour per email)
- [ ] **SEC-03**: Global CSRF protection on all POST forms (token-based)
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

- [ ] **AUDIT-01**: Audit log database schema (event_type, user_id, ip, timestamp, details)
- [ ] **AUDIT-02**: Log login attempts (success and failure with IP)
- [ ] **AUDIT-03**: Log password changes
- [ ] **AUDIT-04**: Log password reset requests and completions
- [ ] **AUDIT-05**: Log account creation
- [ ] **AUDIT-06**: Log account deletion requests and purges
- [ ] **AUDIT-07**: Log email verification status changes
- [ ] **AUDIT-08**: Admin audit log page at /admin/audit-log
- [ ] **AUDIT-09**: Audit log filtering (by user, event type, date range)
- [ ] **AUDIT-10**: Forever retention (no auto-purge)

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
| SEC-01 | TBD | Pending |
| SEC-02 | TBD | Pending |
| SEC-03 | TBD | Pending |
| SEC-04 | TBD | Pending |
| SEC-05 | TBD | Pending |
| SEC-06 | TBD | Pending |
| SEC-07 | TBD | Pending |
| ACCT-01 | TBD | Pending |
| ACCT-02 | TBD | Pending |
| ACCT-03 | TBD | Pending |
| ACCT-04 | TBD | Pending |
| ACCT-05 | TBD | Pending |
| ACCT-06 | TBD | Pending |
| ACCT-07 | TBD | Pending |
| ACCT-08 | TBD | Pending |
| AUDIT-01 | TBD | Pending |
| AUDIT-02 | TBD | Pending |
| AUDIT-03 | TBD | Pending |
| AUDIT-04 | TBD | Pending |
| AUDIT-05 | TBD | Pending |
| AUDIT-06 | TBD | Pending |
| AUDIT-07 | TBD | Pending |
| AUDIT-08 | TBD | Pending |
| AUDIT-09 | TBD | Pending |
| AUDIT-10 | TBD | Pending |

**Coverage:**
- v2.1 requirements: 25 total
- Mapped to phases: 0
- Unmapped: 25

---
*Requirements defined: 2026-02-02*
*Last updated: 2026-02-02 after initial definition*
