---
phase: 04-user-notifications
plan: 01
subsystem: database, config
tags: [sqlite, telegram, email, smtp, notifications]

# Dependency graph
requires:
  - phase: 01-database-schema
    provides: users table with telegram_chat_id column
  - phase: 02-authentication
    provides: session and user management
provides:
  - telegram_enabled and email_enabled columns on users table
  - telegram_link_codes table for Telegram linking flow
  - EmailConfig dataclass for SMTP configuration
  - AppConfig dataclass for secret_key and base_url
  - TelegramConfig webhook fields
  - Database methods for link code CRUD
  - Database methods for notification preference toggles
affects:
  - 04-02 (Telegram bot routes)
  - 04-03 (Email notification service)
  - 04-04 (Settings page UI)

# Tech tracking
tech-stack:
  added:
    - fastapi-mail>=1.4.0
    - itsdangerous>=2.0.0
  patterns:
    - Notification preference columns with sensible defaults (email on, telegram off)
    - Link code pattern for secure Telegram account linking

key-files:
  created:
    - ra-tracker/config.example.yaml (updated with full notification config)
  modified:
    - ra-tracker/ra_tracker/database.py
    - ra-tracker/ra_tracker/config.py
    - ra-tracker/requirements.txt

key-decisions:
  - "telegram_enabled defaults to 0 (off) - requires explicit linking"
  - "email_enabled defaults to 1 (on) - opt-out model for email"
  - "Link codes stored in separate table with expiry for security"
  - "itsdangerous for signed unsubscribe tokens"

patterns-established:
  - "Notification preference pattern: boolean columns with get/set methods"
  - "Link code pattern: temp table with user_id, expiry, used_at tracking"

# Metrics
duration: 5min
completed: 2026-01-31
---

# Phase 4 Plan 1: Notification Preferences Schema Summary

**Database schema extensions and config structure for per-user Telegram/Email notification preferences**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-31T09:51:46Z
- **Completed:** 2026-01-31T09:56:44Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added telegram_enabled and email_enabled columns to users table with migrations
- Created telegram_link_codes table for secure Telegram account linking flow
- Added EmailConfig dataclass with SMTP settings (server, port, starttls, etc.)
- Extended TelegramConfig with webhook_secret, use_webhook, webhook_url fields
- Added AppConfig dataclass for secret_key (token signing) and base_url (email links)
- Implemented database methods for link code CRUD and notification toggles
- Updated config.example.yaml with comprehensive documentation of all options

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend database schema for notification preferences** - `785bbe0` (feat)
2. **Task 2: Add EmailConfig and extend TelegramConfig** - `fa518aa` (feat)

## Files Created/Modified
- `ra-tracker/ra_tracker/database.py` - Added notification preference columns, link codes table, User dataclass fields, CRUD methods
- `ra-tracker/ra_tracker/config.py` - Added EmailConfig, AppConfig dataclasses, extended TelegramConfig
- `ra-tracker/config.example.yaml` - Full documentation of Telegram, Email, and App config options
- `ra-tracker/requirements.txt` - Added fastapi-mail and itsdangerous dependencies

## Decisions Made
- telegram_enabled defaults to 0 (off) because Telegram requires explicit linking
- email_enabled defaults to 1 (on) for opt-out model on email notifications
- Used separate telegram_link_codes table rather than adding columns to users (cleaner, supports multiple pending codes)
- Added itsdangerous for signed unsubscribe tokens (no login required to unsubscribe)
- Used nullable handling for telegram_enabled/email_enabled to support existing databases during migration

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required for this plan. Email and Telegram configuration will be documented in later plans when the notification services are implemented.

## Next Phase Readiness
- Database ready for Telegram bot implementation (Plan 02)
- Config structure ready for SMTP email service (Plan 03)
- Link code table ready for /link command flow
- No blockers identified

---
*Phase: 04-user-notifications*
*Completed: 2026-01-31*
