# Roadmap: RA Tracker Milestone 2

**Created:** 2026-01-19
**Milestone:** Multi-User Support
**Phases:** 4
**Depth:** Quick

## Overview

| # | Phase | Goal | Requirements |
|---|-------|------|--------------|
| 1 | Database Schema | Add users table and foreign key relationships | MULTI-01 |
| 2 | Authentication | User registration, login, logout with secure sessions + mobile-first UI + privacy policy | AUTH-01 to AUTH-05, SESSION-01, SESSION-02, UI-01, PRIVACY-01 to PRIVACY-04 |
| 3 | Multi-Tenant Access | Scope rules and notifications to users, protect routes | MULTI-02, MULTI-03, MULTI-04 |
| 4 | User Notifications | Per-user notification config (Telegram and/or Email) | TELEGRAM-01, TELEGRAM-02, EMAIL-01, EMAIL-02, NOTIFY-01 to NOTIFY-03 |

---

## Phase 1: Database Schema ✓

**Goal:** Add users table and establish foreign key relationships for multi-tenancy

**Status:** Complete (2026-01-23)

**Requirements:**
- MULTI-01: Database schema supports multiple users (users table)

**Plans:** 1 plan

Plans:
- [x] 01-01-PLAN.md - Add users table, User dataclass, user_id migrations, and user CRUD operations

**Success Criteria:**
1. Users table exists with id, email, password_hash, created_at columns
2. Rules table has user_id foreign key column
3. Notifications table has user_id foreign key column
4. Existing data migrated (assigned to a default user or handled gracefully)
5. Database operations still work for single-user case

**Dependencies:** None

---

## Phase 2: Authentication ✓

**Goal:** Implement user registration, login, logout with secure password hashing and session management. Migrate UI to Tailwind CSS with mobile-first responsive design.

**Status:** Complete (2026-01-27)

**Requirements:**
- AUTH-01: User can register with email and password
- AUTH-02: User can log in with email and password
- AUTH-03: User can log out
- AUTH-04: User session persists across browser refresh
- AUTH-05: Passwords are securely hashed (Argon2id via argon2-cffi)
- SESSION-01: Secure session cookies with httponly flag
- SESSION-02: Sessions expire after configurable timeout
- UI-01: All authentication flows and dashboard features fully functional on mobile (min-width 375px)
- PRIVACY-01: Privacy Policy page explains what data is collected
- PRIVACY-02: Privacy Policy explains how data is stored/protected
- PRIVACY-03: Registration requires explicit consent checkbox (not pre-ticked)
- PRIVACY-04: Privacy Policy link visible on registration page

**Plans:** 5 plans in 3 waves

Plans:
- [x] 02-01-PLAN.md - Session infrastructure (database table, CRUD, config, auth module) [Wave 1]
- [x] 02-02-PLAN.md - Authentication routes (register, login, logout, privacy) and templates [Wave 2]
- [x] 02-03-PLAN.md - Tailwind CSS migration and mobile navigation in base.html [Wave 2]
- [x] 02-04-PLAN.md - Route protection and mobile artist tracking UI [Wave 3]
- [x] 02-05-PLAN.md - Mobile responsiveness for existing templates and verification [Wave 3]

**Wave Structure:**
| Wave | Plans | Description |
|------|-------|-------------|
| 1 | 02-01 | Session infrastructure (no dependencies) |
| 2 | 02-02, 02-03 | Auth routes/templates + Tailwind base.html (parallel) |
| 3 | 02-04, 02-05 | Route protection + mobile polish (parallel) |

**Success Criteria:**
1. Registration page accepts email/password/display_name and creates user
2. Registration includes unticked consent checkbox with Privacy Policy link
3. Login page authenticates user and creates session
4. Logout clears session
5. Session cookie is httponly and secure
6. Passwords stored as Argon2id hashes, never plaintext
7. Session timeout configurable in config.yaml
8. Privacy Policy page accessible at /privacy
9. All pages use Tailwind CSS with responsive mobile-first design
10. Navigation works on mobile (hamburger menu or similar pattern)
11. Forms are touch-friendly with appropriate input sizes

**Dependencies:** Phase 1 (users table must exist)

---

## Phase 3: Multi-Tenant Access ✓

**Goal:** Scope data access to logged-in user and protect routes

**Status:** Complete (2026-01-29)

**Requirements:**
- MULTI-02: Rules are scoped to the user who created them
- MULTI-03: Notification history is scoped per user
- MULTI-04: Events remain shared globally (single cache)

**Plans:** 3 plans in 2 waves

Plans:
- [x] 03-01-PLAN.md - User-scoped database methods (user_id parameters, ownership checks, user-scoped queries) [Wave 1]
- [x] 03-02-PLAN.md - User-scoped routes (dashboard, rules page, rule mutations, API endpoints) [Wave 2]
- [x] 03-03-PLAN.md - Admin routes and templates (require_admin, /admin/rules, /admin/users) [Wave 2]

**Wave Structure:**
| Wave | Plans | Description |
|------|-------|-------------|
| 1 | 03-01 | Database methods (no dependencies) |
| 2 | 03-02, 03-03 | Routes + Admin UI (parallel, both depend on 03-01) |

**Success Criteria:**
1. All routes except login/register require authentication
2. User only sees their own rules on dashboard
3. User only sees notifications for their own rules
4. Adding a rule assigns it to current user
5. Events remain visible to all users (shared cache)
6. Unauthenticated access redirects to login
7. Admin can view all users' rules (read-only)
8. Admin can view list of registered users

**Dependencies:** Phase 2 (authentication must work)

---

## Phase 4: User Notifications

**Goal:** Allow each user to configure notification channels (Telegram and/or Email) with independent on/off toggles

**Requirements:**
- TELEGRAM-01: Each user can link Telegram by messaging the bot
- TELEGRAM-02: Admin configures shared bot token in config
- EMAIL-01: Email notifications sent to login email
- EMAIL-02: Admin configures SMTP settings in config
- NOTIFY-01: User can toggle Telegram notifications on/off
- NOTIFY-02: User can toggle Email notifications on/off
- NOTIFY-03: At least one channel must be configured before notifications are sent
- NOTIFY-05: Email includes one-click unsubscribe link (no login required)
- NOTIFY-06: Telegram bot responds to /stop command to disable notifications

**Success Criteria:**
1. Settings page shows notification preferences section
2. Telegram: "Link Telegram" button with bot interaction flow (proves ownership)
3. Email: Uses login email (no separate notification email in v1)
4. Independent toggle switches for each channel (Telegram on/off, Email on/off)
5. Visual indicator showing which channels are configured vs enabled
6. Bot token and SMTP settings remain in config.yaml (admin-managed)
7. Users can unlink Telegram; email toggle simply enables/disables
8. Notifications sent only to enabled channels
9. Users with no configured channels see prompt to set up notifications
10. Every email notification includes one-click unsubscribe link with signed token
11. Clicking unsubscribe link disables email notifications without login
12. Sending /stop to Telegram bot disables Telegram notifications
13. Bot confirms "/stop" with message and instructions to re-enable via settings

**Telegram Linking Flow:**
1. User clicks "Link Telegram" in settings
2. App generates unique code, shows "Send this to @BotName: /link ABC123"
3. User messages bot with code
4. Bot webhook/polling receives message, extracts chat_id, validates code
5. App associates chat_id with user
6. Settings page shows "Linked" status with toggle to enable/disable

**Dependencies:** Phase 3 (user must be identifiable)

---

## Milestone Completion Criteria

- [ ] New users can register and log in with explicit privacy consent
- [ ] Privacy Policy clearly explains data collection and storage
- [ ] Each user has isolated rules and notification history
- [ ] Events shared across all users
- [ ] Each user can configure Telegram and/or Email notifications independently
- [ ] All flows work on mobile devices (375px+)
- [ ] Existing single-user functionality preserved during migration

---
*Roadmap created: 2026-01-19*
*Last updated: 2026-01-28 - Added Phase 3 plans (3 plans in 2 waves)*
