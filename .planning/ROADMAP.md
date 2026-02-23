# Roadmap: Rave Tracker

## Milestones

- ✅ **v1.0 MVP** - Single-user event tracker (shipped 2026-01-19)
- ✅ **v2.0 Multi-User Support** - Phases 1-4 (shipped 2026-02-01)
- ✅ **v2.1 Security Hardening** - Phases 5-8 (shipped 2026-02-08)
- ✅ **v2.2 UX Polish & Branding** - Phase 9 (shipped 2026-02-10)
- ✅ **v3.0 Production Deployment & Hosting** - Phases 10-13 (shipped 2026-02-18)
- ✅ **v3.1 Observability & Monitoring** - Phase 14 (shipped 2026-02-20)
- ✅ **v3.2 Tracking Page UX** - Phase 15 (shipped 2026-02-22)
- 🚧 **v3.3 Settings Split** - Phases 16-18 (in progress)

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

<details>
<summary>✅ v2.2 UX Polish & Branding (Phase 9) - SHIPPED 2026-02-10</summary>

### Phase 9: UX Polish & Branding
**Goal**: Application presents as "Rave Tracker" with improved region selection UX
**Plans**: 3 plans

Plans:
- [x] 09-01: Rebrand all user-facing text to "Rave Tracker"
- [x] 09-02: UX improvements (toggle labels, region prompt, banner removal)
- [x] 09-03: Fix per-user local area storage (gap closure)

</details>

<details>
<summary>✅ v3.0/v3.1 Production Deployment, Hosting & Observability (Phases 10-14) — SHIPPED 2026-02-20</summary>

- [x] Phase 10: Environment & Secrets Cleanup (1/1 plans) — completed 2026-02-12
- [x] Phase 11: PostgreSQL Migration & Production Server (3/3 plans) — completed 2026-02-16
- [x] Phase 12: Hosting & SSL Deployment (3/3 plans) — completed 2026-02-15
- [x] Phase 13: Scraper Resilience (3/3 plans) — completed 2026-02-18
- [x] Phase 14: Observability & Monitoring (4/4 plans) — completed 2026-02-20

Full details: `.planning/milestones/v3.1-ROADMAP.md`

</details>

<details>
<summary>✅ v3.2 Tracking Page UX (Phase 15) — SHIPPED 2026-02-22</summary>

### Phase 15: Tracking Page UX
**Goal**: Tracking page is the default entry point for rule management, with persistent local area selection
**Plans**: 1 plan

Plans:
- [x] 15-01: Berlin default, area widget, /rules→/tracking rename

</details>

### 🚧 v3.3 Settings Split (Phases 16-18)

**Milestone Goal:** Split /settings into personal settings (all users) and system config (admins only), add daily digest notification mode, and harden admin-only endpoints server-side.

#### Phase 16: Settings Page Split
**Goal**: Users see only their personal settings; admins access system configuration on a dedicated page
**Depends on**: Phase 15
**Requirements**: SETT-01, SETT-02, SETT-03, SETT-04, SETT-05, SETT-06, SETT-07, SETT-08, SETT-09, SETT-10, SETT-11
**Success Criteria** (what must be TRUE):
  1. Any logged-in user visiting /settings sees only Notification Preferences, Account Security, and Delete Account — no system config fields, no Local Area section
  2. An admin user sees a visible link to /admin/settings on the /settings page
  3. A non-admin visiting /admin/settings receives a 403 response
  4. An admin on /admin/settings can view and save Telegram bot token, admin chat ID, fetch schedule times, event horizon, and notification mode
  5. An admin on /admin/settings sees database info (read-only) and can trigger a test Telegram message
**Plans**: 2 plans

Plans:
- [x] 16-01-PLAN.md — Strip /settings to personal-only; add admin link for admin users
- [x] 16-02-PLAN.md — Create /admin/settings page with system config fields (+ config.py extension)

#### Phase 17: Notification Dispatch Modes
**Goal**: Admins can choose between immediate notifications on fetch and a daily digest that batches all events
**Depends on**: Phase 16
**Requirements**: SETT-12, SETT-13, SETT-14
**Success Criteria** (what must be TRUE):
  1. With "Upon fetch" mode active, notifications arrive within minutes of a fetch completing (existing behaviour preserved)
  2. With "Daily digest" mode active, a fetch run does not send any notifications immediately — events are queued
  3. At the configured digest time each day, each user with queued events receives a single batched notification covering all events since the last digest
**Plans**: 2 plans

Plans:
- [ ] 17-01-PLAN.md — DB schema: queued_for_digest column + queue/retrieve/mark-sent DB methods
- [ ] 17-02-PLAN.md — CronTrigger fetch schedule, mode-conditional dispatch, daily digest job (+ human-verify checkpoint)

#### Phase 18: Endpoint Hardening
**Goal**: Admin-only POST endpoints reject non-admin requests at the server level, regardless of UI state
**Depends on**: Phase 16
**Requirements**: SETT-15, SETT-16
**Success Criteria** (what must be TRUE):
  1. A non-admin user who submits POST /settings/save with system config fields receives a 403 response — no data is saved
  2. A non-admin user who calls POST /settings/test-telegram receives a 403 response — no Telegram message is sent
**Plans**: TBD

Plans:
- [ ] 18-01: Server-side admin guards on /settings/save and /settings/test-telegram

## Phase Details

### Phase 16: Settings Page Split
**Goal**: Users see only their personal settings; admins access system configuration on a dedicated page
**Depends on**: Phase 15
**Requirements**: SETT-01, SETT-02, SETT-03, SETT-04, SETT-05, SETT-06, SETT-07, SETT-08, SETT-09, SETT-10, SETT-11
**Success Criteria** (what must be TRUE):
  1. Any logged-in user visiting /settings sees only Notification Preferences, Account Security, and Delete Account — no system config fields, no Local Area section
  2. An admin user sees a visible link to /admin/settings on the /settings page
  3. A non-admin visiting /admin/settings receives a 403 response
  4. An admin on /admin/settings can view and save Telegram bot token, admin chat ID, fetch schedule times, event horizon, and notification mode
  5. An admin on /admin/settings sees database info (read-only) and can trigger a test Telegram message
**Plans**: 2 plans

Plans:
- [x] 16-01-PLAN.md — Strip /settings to personal-only; add admin link for admin users
- [x] 16-02-PLAN.md — Create /admin/settings page with system config fields (+ config.py extension)

### Phase 17: Notification Dispatch Modes
**Goal**: Admins can choose between immediate notifications on fetch and a daily digest that batches all events
**Depends on**: Phase 16
**Requirements**: SETT-12, SETT-13, SETT-14
**Success Criteria** (what must be TRUE):
  1. With "Upon fetch" mode active, notifications arrive within minutes of a fetch completing (existing behaviour preserved)
  2. With "Daily digest" mode active, a fetch run does not send any notifications immediately — events are queued
  3. At the configured digest time each day, each user with queued events receives a single batched notification covering all events since the last digest
**Plans**: 2 plans

Plans:
- [ ] 17-01-PLAN.md — DB schema: queued_for_digest column + queue/retrieve/mark-sent DB methods
- [ ] 17-02-PLAN.md — CronTrigger fetch schedule, mode-conditional dispatch, daily digest job (+ human-verify checkpoint)

### Phase 18: Endpoint Hardening
**Goal**: Admin-only POST endpoints reject non-admin requests at the server level, regardless of UI state
**Depends on**: Phase 16
**Requirements**: SETT-15, SETT-16
**Success Criteria** (what must be TRUE):
  1. A non-admin user who submits POST /settings/save with system config fields receives a 403 response — no data is saved
  2. A non-admin user who calls POST /settings/test-telegram receives a 403 response — no Telegram message is sent
**Plans**: TBD

Plans:
- [ ] 18-01: Server-side admin guards on /settings/save and /settings/test-telegram

## Progress

**Execution Order:**
Phases execute in numeric order: 16 → 17 → 18

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
| 9. UX Polish & Branding | v2.2 | 3/3 | Complete | 2026-02-10 |
| 10. Environment & Secrets | v3.0 | 1/1 | Complete | 2026-02-12 |
| 11. PostgreSQL & Server | v3.0 | 3/3 | Complete | 2026-02-16 |
| 12. Hosting & SSL | v3.0 | 3/3 | Complete | 2026-02-15 |
| 13. Scraper Resilience | v3.0 | 3/3 | Complete | 2026-02-18 |
| 14. Observability | v3.1 | 4/4 | Complete | 2026-02-20 |
| 15. Tracking Page UX | v3.2 | 1/1 | Complete | 2026-02-22 |
| 16. Settings Page Split | 2/2 | Complete    | 2026-02-22 | 2026-02-22 |
| 17. Notification Dispatch Modes | 2/2 | Complete   | 2026-02-23 | - |
| 18. Endpoint Hardening | v3.3 | 0/1 | Not started | - |

---
*Roadmap created: 2026-02-11*
*Last updated: 2026-02-22 — Phase 16 complete; /admin/settings page delivered*
