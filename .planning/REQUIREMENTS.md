# Requirements: RA Tracker Milestone 2

**Defined:** 2026-01-19
**Core Value:** Users never miss events from artists, venues, or promoters they care about

## v1 Requirements

Requirements for Milestone 2: Multi-User Support.

### Authentication

- [ ] **AUTH-01**: User can register with email and password
- [ ] **AUTH-02**: User can log in with email and password
- [ ] **AUTH-03**: User can log out
- [ ] **AUTH-04**: User session persists across browser refresh
- [ ] **AUTH-05**: Passwords are securely hashed (bcrypt)

### Multi-Tenant Database

- [x] **MULTI-01**: Database schema supports multiple users (users table)
- [ ] **MULTI-02**: Rules are scoped to the user who created them
- [ ] **MULTI-03**: Notification history is scoped per user
- [ ] **MULTI-04**: Events remain shared globally (single cache)

### Session Management

- [ ] **SESSION-01**: Secure session cookies with httponly flag
- [ ] **SESSION-02**: Sessions expire after configurable timeout

### Telegram Integration

- [ ] **TELEGRAM-01**: Each user can link Telegram by messaging the bot (auto-detects chat ID)
- [ ] **TELEGRAM-02**: Admin configures shared bot token in config

## v2 Requirements

Deferred to future milestone.

### Account Management

- **ACCOUNT-01**: User can reset password via email link
- **ACCOUNT-02**: User can change password when logged in
- **ACCOUNT-03**: User can delete their account

### Security Enhancements

- **SEC-01**: Rate limiting on login attempts
- **SEC-02**: Email verification on registration
- **SEC-03**: CSRF protection on all forms

## Out of Scope

| Feature | Reason |
|---------|--------|
| OAuth/social login | Email/password sufficient, avoids external dependencies |
| Per-user Telegram bots | Shared bot simpler for users, admin manages one token |
| Per-user event caches | Events are public data, unnecessary duplication |
| Password reset email | Requires email infrastructure, defer to v2 |
| Mobile app | Web-first approach |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MULTI-01 | Phase 1 | Complete |
| AUTH-01 | Phase 2 | Pending |
| AUTH-02 | Phase 2 | Pending |
| AUTH-03 | Phase 2 | Pending |
| AUTH-04 | Phase 2 | Pending |
| AUTH-05 | Phase 2 | Pending |
| SESSION-01 | Phase 2 | Pending |
| SESSION-02 | Phase 2 | Pending |
| MULTI-02 | Phase 3 | Pending |
| MULTI-03 | Phase 3 | Pending |
| MULTI-04 | Phase 3 | Pending |
| TELEGRAM-01 | Phase 4 | Pending |
| TELEGRAM-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0

---
*Requirements defined: 2026-01-19*
*Last updated: 2026-01-19 after initial definition*
