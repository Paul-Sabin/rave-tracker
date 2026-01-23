# Roadmap: RA Tracker Milestone 2

**Created:** 2026-01-19
**Milestone:** Multi-User Support
**Phases:** 4
**Depth:** Quick

## Overview

| # | Phase | Goal | Requirements |
|---|-------|------|--------------|
| 1 | Database Schema | Add users table and foreign key relationships | MULTI-01 |
| 2 | Authentication | User registration, login, logout with secure sessions | AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, SESSION-01, SESSION-02 |
| 3 | Multi-Tenant Access | Scope rules and notifications to users, protect routes | MULTI-02, MULTI-03, MULTI-04 |
| 4 | User Telegram Config | Per-user Telegram chat ID configuration | TELEGRAM-01, TELEGRAM-02 |

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

## Phase 2: Authentication

**Goal:** Implement user registration, login, logout with secure password hashing and session management

**Requirements:**
- AUTH-01: User can register with email and password
- AUTH-02: User can log in with email and password
- AUTH-03: User can log out
- AUTH-04: User session persists across browser refresh
- AUTH-05: Passwords are securely hashed (bcrypt)
- SESSION-01: Secure session cookies with httponly flag
- SESSION-02: Sessions expire after configurable timeout

**Success Criteria:**
1. Registration page accepts email/password and creates user
2. Login page authenticates user and creates session
3. Logout clears session
4. Session cookie is httponly and secure
5. Passwords stored as bcrypt hashes, never plaintext
6. Session timeout configurable in config.yaml

**Dependencies:** Phase 1 (users table must exist)

---

## Phase 3: Multi-Tenant Access

**Goal:** Scope data access to logged-in user and protect routes

**Requirements:**
- MULTI-02: Rules are scoped to the user who created them
- MULTI-03: Notification history is scoped per user
- MULTI-04: Events remain shared globally (single cache)

**Success Criteria:**
1. All routes except login/register require authentication
2. User only sees their own rules on dashboard
3. User only sees notifications for their own rules
4. Adding a rule assigns it to current user
5. Events remain visible to all users (shared cache)
6. Unauthenticated access redirects to login

**Dependencies:** Phase 2 (authentication must work)

---

## Phase 4: User Telegram Config

**Goal:** Allow each user to link their Telegram account via bot interaction for notifications

**Requirements:**
- TELEGRAM-01: Each user can link Telegram by messaging the bot
- TELEGRAM-02: Admin configures shared bot token in config

**Success Criteria:**
1. Settings page shows "Link Telegram" button with instructions
2. User sends /start (or any message) to the configured bot
3. Bot generates a unique linking code per user
4. App detects user's chat ID when they message the bot with code
5. Notifications sent to user's linked chat ID
6. Bot token remains in config.yaml (admin-managed)
7. Users can unlink their Telegram
8. Users without linked Telegram don't receive notifications

**Linking Flow:**
1. User clicks "Link Telegram" in settings
2. App generates unique code, shows "Send this to @BotName: /link ABC123"
3. User messages bot with code
4. Bot webhook/polling receives message, extracts chat_id, validates code
5. App associates chat_id with user
6. Settings page shows "Linked" status

**Dependencies:** Phase 3 (user must be identifiable)

---

## Milestone Completion Criteria

- [ ] New users can register and log in
- [ ] Each user has isolated rules and notification history
- [ ] Events shared across all users
- [ ] Each user can configure their own Telegram notifications
- [ ] Existing single-user functionality preserved during migration

---
*Roadmap created: 2026-01-19*
