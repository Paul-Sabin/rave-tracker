# Roadmap: Rave Tracker

## Milestones

- ✅ **v1.0 MVP** - Single-user event tracker (shipped 2026-01-19)
- ✅ **v2.0 Multi-User Support** - Phases 1-4 (shipped 2026-02-01)
- ✅ **v2.1 Security Hardening** - Phases 5-8 (shipped 2026-02-08)
- ✅ **v2.2 UX Polish & Branding** - Phase 9 (shipped 2026-02-10)
- ✅ **v3.0 Production Deployment & Hosting** - Phases 10-13 (shipped 2026-02-18)
- ✅ **v3.1 Observability & Monitoring** - Phase 14 (shipped 2026-02-20)
- ✅ **v3.2 Tracking Page UX** - Phase 15 (shipped 2026-02-22)
- ✅ **v3.3 Settings Split** - Phases 16-18 (shipped 2026-02-28)
- 🚧 **v3.4 Onboarding & Welcome** - Phases 19-23 (in progress)

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

<details>
<summary>✅ v3.3 Settings Split (Phases 16-18) — SHIPPED 2026-02-28</summary>

- [x] Phase 16: Settings Page Split (2/2 plans) — completed 2026-02-22
- [x] Phase 17: Notification Dispatch Modes (2/2 plans) — completed 2026-02-23
- [x] Phase 18: Endpoint Hardening (1/1 plan) — completed 2026-02-28

Full details: `.planning/milestones/v3.3-ROADMAP.md`

</details>

### 🚧 v3.4 Onboarding & Welcome (In Progress)

**Milestone Goal:** New users are greeted by a 4-step welcome wizard guided by the Ravemonger mascot, covering local area, notifications, and a feature tour. The wizard is skippable at every step, accessible, and revisitable from settings.

- [x] **Phase 19: Database Foundation** - Migration adds onboarding_completed column with backfill for existing users (completed 2026-03-01)
- [ ] **Phase 20: Wizard Routes** - Welcome routes registered and step rendering confirmed via stub template
- [ ] **Phase 21: Welcome Template** - Full 4-step wizard UI with mascot, transitions, accessibility, and data interactions
- [ ] **Phase 22: Login Intercept** - First-run trigger wires new verified users into the wizard on login
- [ ] **Phase 23: Settings Revisit Link** - "Revisit Tour" entry point added to /settings

## Phase Details

### Phase 19: Database Foundation
**Goal**: The onboarding_completed column exists in production with existing users correctly backfilled so no deployed user sees the wizard unexpectedly
**Depends on**: Phase 18 (v3.3 complete)
**Requirements**: FOUND-01
**Success Criteria** (what must be TRUE):
  1. Migration 14 runs without error on both SQLite and PostgreSQL
  2. All existing users with a local area or Telegram configured have onboarding_completed = TRUE after migration
  3. Newly registered users have onboarding_completed = FALSE by default
  4. Database.set_onboarding_completed() method exists and updates the column correctly
**Plans**: 1 plan

Plans:
- [ ] 19-01: Migration 14 — onboarding_completed column, backfill, User dataclass, DB method

### Phase 20: Wizard Routes
**Goal**: The /welcome URL resolves and returns a rendered page; step routing is confirmed; the wizard is accessible by direct URL to a verified, logged-in user
**Depends on**: Phase 19
**Requirements**: WIZ-01
**Success Criteria** (what must be TRUE):
  1. GET /welcome redirects to /welcome/step/1
  2. GET /welcome/step/1 through /welcome/step/4 each return 200 with the correct step number rendered
  3. GET /welcome/step/99 is clamped to step 4 (no 404 or 500)
  4. Unauthenticated requests to /welcome/step/1 redirect to login
  5. Authenticated but unverified users cannot access the wizard routes
**Plans**: 1 plan

Plans:
- [ ] 20-01: Wizard routes — GET /welcome, GET /welcome/step/{step}, POST /welcome/complete, stub welcome.html

### Phase 21: Welcome Template
**Goal**: The welcome.html template delivers a complete, usable 4-step wizard experience — mascot present, all UI interactions functional, accessible to keyboard and screen reader users
**Depends on**: Phase 20
**Requirements**: WIZ-02, WIZ-03, WIZ-04, WIZ-05, RAVE-01, RAVE-02, DATA-01, DATA-02, FOUND-04
**Success Criteria** (what must be TRUE):
  1. Every step shows a Skip button that advances to the next step without saving any data
  2. A dot-row progress indicator shows the current step position at all times
  3. Step 4 completion shows a Ravemonger celebration (thumbs-up or confetti)
  4. Ravemonger mascot image and unique dialogue appear on each step
  5. Step 2 area search works inline — selecting an area saves it without leaving the wizard
  6. Step 3 notification toggles are unchecked for new users and save correctly via existing endpoints
  7. Keyboard users can navigate all steps and controls without a mouse
  8. Screen reader users receive an announcement when each step changes
**Plans**: TBD

Plans:
- [ ] 21-01: Step 1 — welcome screen, Ravemonger, nav suppression, slide transition framework
- [ ] 21-02: Step 2 — inline area search widget reuse, step 3 — notification toggles (GDPR-unchecked)
- [ ] 21-03: Step 4 — feature tour, completion celebration, POST /welcome/complete; accessibility pass (focus, aria-live)

### Phase 22: Login Intercept
**Goal**: New users who complete email verification are automatically redirected into the wizard on their next login; subsequent logins go directly to the dashboard
**Depends on**: Phase 21
**Requirements**: FOUND-02, FOUND-03
**Success Criteria** (what must be TRUE):
  1. A new user who registers, verifies email, and logs in lands on /welcome/step/1 (not the dashboard)
  2. A user who has not verified their email logs in and is NOT redirected to the wizard
  3. A user who has completed the wizard logs in and goes directly to the dashboard
  4. Completing the wizard sets onboarding_completed = TRUE in the database
**Plans**: TBD

Plans:
- [ ] 22-01: Login POST intercept — onboarding_completed + email_verified gate; end-to-end flow verification

### Phase 23: Settings Revisit Link
**Goal**: Any logged-in user can re-enter the wizard from /settings and experience the same flow with their current preferences pre-loaded
**Depends on**: Phase 22
**Requirements**: DATA-03
**Success Criteria** (what must be TRUE):
  1. A "Revisit Tour" link or card is visible on /settings for all logged-in users
  2. Clicking it navigates to /welcome/step/1 without error
  3. A user who has already completed onboarding can traverse all 4 steps again
  4. Step 2 and step 3 show the user's current area and notification state (not hardcoded defaults) on revisit
**Plans**: TBD

Plans:
- [ ] 23-01: "Revisit Tour" card in settings.html; verify revisit seeds from live DB values

## Progress

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
| 16. Settings Page Split | v3.3 | 2/2 | Complete | 2026-02-22 |
| 17. Notification Dispatch Modes | v3.3 | 2/2 | Complete | 2026-02-23 |
| 18. Endpoint Hardening | v3.3 | 1/1 | Complete | 2026-02-28 |
| 19. Database Foundation | 1/1 | Complete    | 2026-03-01 | - |
| 20. Wizard Routes | v3.4 | 0/1 | Not started | - |
| 21. Welcome Template | v3.4 | 0/3 | Not started | - |
| 22. Login Intercept | v3.4 | 0/1 | Not started | - |
| 23. Settings Revisit Link | v3.4 | 0/1 | Not started | - |

---
*Roadmap created: 2026-02-11*
*Last updated: 2026-03-01 — v3.4 roadmap added: phases 19-23, onboarding wizard*
