# Roadmap: Rave Tracker

## Milestones

- ✅ **v1.0 MVP** - Single-user event tracker (shipped 2026-01-19)
- ✅ **v2.0 Multi-User Support** - Phases 1-4 (shipped 2026-02-01)
- ✅ **v2.1 Security Hardening** - Phases 5-8 (shipped 2026-02-08)
- 🚧 **v2.2 UX Polish & Branding** - Phase 9 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP - SHIPPED 2026-01-19</summary>

Single-user event tracker with fetching, rules, and notifications.

</details>

<details>
<summary>✅ v2.0 Multi-User Support (Phases 1-4) - SHIPPED 2026-02-01</summary>

### Phase 1: Database Foundation
**Goal**: Multi-user database schema ready
**Plans**: 2 plans

Plans:
- [x] 01-01: Database schema and models
- [x] 01-02: Migration and data seeding

### Phase 2: Authentication System
**Goal**: Users can securely access their accounts
**Plans**: 3 plans

Plans:
- [x] 02-01: Password infrastructure (Argon2id hashing)
- [x] 02-02: Login and registration routes
- [x] 02-03: Authentication UI (login, register, logout)

### Phase 3: Multi-Tenant Access Control
**Goal**: Users access only their own data
**Plans**: 4 plans

Plans:
- [x] 03-01: Session management and middleware
- [x] 03-02: User-scoped rules and events
- [x] 03-03: Privacy policy with explicit consent
- [x] 03-04: UI updates for multi-user mode

### Phase 4: User Notification Delivery
**Goal**: Users receive notifications via their chosen channels
**Plans**: 3 plans

Plans:
- [x] 04-01: Telegram bot linking and notifications
- [x] 04-02: Email notifications infrastructure
- [x] 04-03: Notification preferences and delivery logic

</details>

<details>
<summary>✅ v2.1 Security Hardening (Phases 5-8) - SHIPPED 2026-02-08</summary>

### Phase 5: Audit Foundation & CSRF Protection
**Goal**: Security events are logged and CSRF attacks are prevented
**Plans**: 2 plans

Plans:
- [x] 05-01: Audit logging infrastructure
- [x] 05-02: CSRF protection (Double Submit Cookie)

### Phase 6: Email Verification & Login Hardening
**Goal**: Only verified email addresses can receive notifications, login attempts are rate-limited
**Plans**: 3 plans

Plans:
- [x] 06-01: Login rate limiting and auth audit logging
- [x] 06-02: Verification token infrastructure
- [x] 06-03: Email verification flow UI

### Phase 7: Password Management
**Goal**: Users can reset forgotten passwords and change existing passwords
**Plans**: 3 plans

Plans:
- [x] 07-01: Password reset infrastructure
- [x] 07-02: Password reset flow (forgot password, reset email)
- [x] 07-03: Password change (settings, strength meter)

### Phase 8: Account Lifecycle & Admin Audit UI
**Goal**: Users can delete accounts with recovery grace period, admins can review audit logs
**Plans**: 3 plans

Plans:
- [x] 08-01: Soft delete and purge infrastructure
- [x] 08-02: Admin audit log UI
- [x] 08-03: Account deletion and recovery flows

</details>

### 🚧 v2.2 UX Polish & Branding (In Progress)

**Milestone Goal:** Rebrand to "Rave Tracker", improve region selection UX, and clean up legacy UI elements.

#### Phase 9: UX Polish & Branding
**Goal**: Application presents as "Rave Tracker" with improved region selection UX
**Depends on**: Phase 8
**Requirements**: BRAND-01, BRAND-02, UX-01, UX-02, UX-03
**Success Criteria** (what must be TRUE):
  1. User sees "Rave Tracker" branding throughout application (nav, titles, footer)
  2. User receives emails from "Rave Tracker" (not "RA Tracker")
  3. User without region sees prompt to select region before first rule
  4. User sees clear "Global events" and "Local only" toggle labels on dashboard
  5. User sees clean dashboard without legacy admin banner
**Plans**: TBD

Plans:
- [ ] 09-01: TBD (during planning)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Database Foundation | v2.0 | 2/2 | Complete | 2026-01-23 |
| 2. Authentication System | v2.0 | 3/3 | Complete | 2026-01-27 |
| 3. Multi-Tenant Access Control | v2.0 | 4/4 | Complete | 2026-01-29 |
| 4. User Notification Delivery | v2.0 | 3/3 | Complete | 2026-01-31 |
| 5. Audit Foundation & CSRF Protection | v2.1 | 2/2 | Complete | 2026-02-02 |
| 6. Email Verification & Login Hardening | v2.1 | 3/3 | Complete | 2026-02-06 |
| 7. Password Management | v2.1 | 3/3 | Complete | 2026-02-07 |
| 8. Account Lifecycle & Admin Audit UI | v2.1 | 3/3 | Complete | 2026-02-08 |
| 9. UX Polish & Branding | v2.2 | 0/? | Not started | - |
