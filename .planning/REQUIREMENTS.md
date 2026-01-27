# Requirements: RA Tracker Milestone 2

**Defined:** 2026-01-19
**Core Value:** Users never miss events from artists, venues, or promoters they care about

## v1 Requirements

Requirements for Milestone 2: Multi-User Support.

### Authentication

- [x] **AUTH-01**: User can register with email and password
- [x] **AUTH-02**: User can log in with email and password
- [x] **AUTH-03**: User can log out
- [x] **AUTH-04**: User session persists across browser refresh
- [x] **AUTH-05**: Passwords are securely hashed (Argon2id)

### Mobile UI

- [x] **UI-01**: All authentication flows and dashboard features fully functional on mobile devices (min-width 375px)

### Multi-Tenant Database

- [x] **MULTI-01**: Database schema supports multiple users (users table)
- [ ] **MULTI-02**: Rules are scoped to the user who created them
- [ ] **MULTI-03**: Notification history is scoped per user
- [ ] **MULTI-04**: Events remain shared globally (single cache)

### Session Management

- [x] **SESSION-01**: Secure session cookies with httponly flag
- [x] **SESSION-02**: Sessions expire after configurable timeout

### Notification Channels

- [ ] **NOTIFY-01**: User can toggle Telegram notifications on/off independently
- [ ] **NOTIFY-02**: User can toggle Email notifications on/off independently
- [ ] **NOTIFY-03**: At least one notification channel must be configured before notifications are sent
- [ ] **NOTIFY-05**: Email notifications include one-click unsubscribe link (no login required)
- [ ] **NOTIFY-06**: Telegram bot responds to /stop command to disable notifications

### Telegram Integration

- [ ] **TELEGRAM-01**: Each user can link Telegram by messaging the bot (auto-detects chat ID)
- [ ] **TELEGRAM-02**: Admin configures shared bot token in config

### Email Integration

- [ ] **EMAIL-01**: Email notifications sent to user's login email (no separate notification email in v1)
- [ ] **EMAIL-02**: Admin configures SMTP settings in config

### Privacy & Consent

- [x] **PRIVACY-01**: Privacy Policy page clearly explains what data is collected (email, session cookies, Telegram ID)
- [x] **PRIVACY-02**: Privacy Policy explains how data is stored and protected
- [x] **PRIVACY-03**: Registration requires explicit consent checkbox (not pre-ticked)
- [x] **PRIVACY-04**: Privacy Policy link visible on registration page

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

### Notification Enhancements

- **NOTIFY-04**: Separate notification email (different from login email) with verification

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
| AUTH-01 | Phase 2 | Complete |
| AUTH-02 | Phase 2 | Complete |
| AUTH-03 | Phase 2 | Complete |
| AUTH-04 | Phase 2 | Complete |
| AUTH-05 | Phase 2 | Complete |
| SESSION-01 | Phase 2 | Complete |
| SESSION-02 | Phase 2 | Complete |
| UI-01 | Phase 2 | Complete |
| MULTI-02 | Phase 3 | Pending |
| MULTI-03 | Phase 3 | Pending |
| MULTI-04 | Phase 3 | Pending |
| TELEGRAM-01 | Phase 4 | Pending |
| TELEGRAM-02 | Phase 4 | Pending |
| NOTIFY-01 | Phase 4 | Pending |
| NOTIFY-02 | Phase 4 | Pending |
| NOTIFY-03 | Phase 4 | Pending |
| EMAIL-01 | Phase 4 | Pending |
| EMAIL-02 | Phase 4 | Pending |
| NOTIFY-05 | Phase 4 | Pending |
| NOTIFY-06 | Phase 4 | Pending |
| PRIVACY-01 | Phase 2 | Complete |
| PRIVACY-02 | Phase 2 | Complete |
| PRIVACY-03 | Phase 2 | Complete |
| PRIVACY-04 | Phase 2 | Complete |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0

---
*Requirements defined: 2026-01-19*
*Last updated: 2026-01-24 - Added notification channels, email integration, privacy & consent requirements*
