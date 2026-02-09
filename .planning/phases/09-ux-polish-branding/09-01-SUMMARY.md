---
phase: 09-ux-polish-branding
plan: 01
subsystem: branding
tags:
  - ui
  - branding
  - user-experience
dependency_graph:
  requires: []
  provides:
    - Rave Tracker brand identity
  affects:
    - All user-facing interfaces (web, email, Telegram)
tech_stack:
  added: []
  patterns:
    - Brand consistency across all channels
key_files:
  created: []
  modified:
    - ra-tracker/ra_tracker/config.py
    - ra-tracker/ra_tracker/web/app.py
    - ra-tracker/ra_tracker/web/templates/base.html
    - ra-tracker/ra_tracker/web/templates/*.html (13 page templates)
    - ra-tracker/ra_tracker/web/templates/email/*.html (5 email templates)
    - ra-tracker/ra_tracker/services/email_sender.py
    - ra-tracker/ra_tracker/services/telegram_bot.py
    - ra-tracker/ra_tracker/services/notifier.py
    - ra-tracker/ra_tracker/scheduler/jobs.py
decisions:
  - User-facing only rebrand: UI shows "Rave Tracker", code remains ra-tracker/ra_tracker
  - Preserved "View on RA" and "Search RA.co" references (external service, not our brand)
  - Preserved "RA Pick" labels (RA editorial feature, not rebranded)
  - Internal docstrings unchanged (not user-facing)
metrics:
  duration_minutes: 9
  tasks_completed: 2
  files_modified: 25
  commits: 2
  completed_date: 2026-02-09
---

# Phase 09 Plan 01: User-Facing Rebrand to Rave Tracker Summary

**One-liner:** Rebranded all user-facing text from "RA Tracker" to "Rave Tracker" across web UI, emails, and Telegram bot while preserving internal code naming.

## What Was Built

Comprehensive rebrand of all user-facing instances of "RA Tracker" to "Rave Tracker" across the entire application stack:

**Web UI (Task 1):**
- Updated config.py email from_name default: `"RA Tracker"` → `"Rave Tracker"`
- Updated FastAPI app title: `title="RA Tracker"` → `title="Rave Tracker"`
- Updated base.html navigation logo and default page title
- Updated all 13 page template titles (dashboard, login, register, rules, settings, privacy, password flows, account recovery, email verification)
- Updated body text in privacy.html (2 instances), unsubscribed.html (1 instance), settings.html (1 instance)

**Email & Notifications (Task 2):**
- Updated 5 email templates (notification, verification, password_reset, account_deleted, account_recovered)
- Updated email_sender.py: 5 subject lines
- Updated telegram_bot.py: 9 user-facing messages (link instructions, error messages, welcome message)
- Updated notifier.py: 3 notification summary messages
- Updated scheduler/jobs.py: 1 admin notification message

**What Was Preserved:**
- "View on RA" links (reference to ra.co website)
- "Search RA.co" placeholder text (external service reference)
- "RA Pick" event badges (RA editorial feature, not our brand)
- Internal module docstrings (config.py, telegram_bot.py)
- Code structure: `ra-tracker/` directory, `ra_tracker` Python package

## Key Decisions

**1. User-facing rebrand only**
- **Context:** User requested rebrand from "RA Tracker" to "Rave Tracker" but changing all code/file names would be disruptive
- **Decision:** Rebrand only user-visible text; keep internal naming unchanged
- **Impact:** Clean user experience with "Rave Tracker" brand, no code refactoring needed
- **Alternatives:** Full rebrand including file paths (rejected due to scope)

**2. Preserved RA.co references**
- **Context:** "View on RA" links and "RA Pick" labels reference Resident Advisor's website/features
- **Decision:** Keep these unchanged as they refer to the external service, not our application
- **Impact:** Clear distinction between our app ("Rave Tracker") and the data source (RA.co)
- **Rationale:** Prevents user confusion about what "RA" means in different contexts

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All verification commands passed:

1. ✅ `grep -r "RA Tracker" ra-tracker/ra_tracker/web/templates/ --include="*.html"` → Zero matches (only internal docstrings remain)
2. ✅ `grep "RA Tracker" ra-tracker/ra_tracker/config.py` → Only module docstring on line 1 (internal)
3. ✅ `grep "Rave Tracker" ra-tracker/ra_tracker/web/templates/base.html` → 2 matches (nav + title)
4. ✅ `grep "from_name" ra-tracker/ra_tracker/config.py` → Shows "Rave Tracker"
5. ✅ `grep "Rave Tracker" ra-tracker/ra_tracker/services/email_sender.py` → 5 subject lines

## Files Changed

**Config & Core (2 files):**
- `ra-tracker/ra_tracker/config.py` - Email from_name default
- `ra-tracker/ra_tracker/web/app.py` - FastAPI app title

**Web Templates (16 files):**
- `base.html` - Navigation and default title
- `dashboard.html`, `login.html`, `register.html`, `rules.html`, `settings.html`, `privacy.html` - Page titles + body text
- `password_change.html`, `password_reset_request.html`, `password_reset_form.html` - Page titles
- `recover_account.html`, `unsubscribed.html` - Page titles + body text
- `verify_email.html`, `verify_expired.html` - Page titles

**Email Templates (5 files):**
- `notification.html` - Title and header
- `verification.html` - Welcome text and footer
- `password_reset.html` - Footer signature
- `account_deleted.html` - Body text (3 instances)
- `account_recovered.html` - Body text (3 instances)

**Services (4 files):**
- `email_sender.py` - 5 email subject lines
- `telegram_bot.py` - 9 user-facing messages
- `notifier.py` - 3 notification messages
- `scheduler/jobs.py` - 1 admin notification

## Commits

1. `22de621` - feat(09-01): rebrand web UI to Rave Tracker
2. `9a1ae86` - feat(09-01): rebrand email, Telegram, and notifications to Rave Tracker

## Self-Check

Verifying all claimed files and commits exist:

**Files verification:**
```bash
# Config & Core
ls ra-tracker/ra_tracker/config.py  # ✓ EXISTS
ls ra-tracker/ra_tracker/web/app.py  # ✓ EXISTS

# Web Templates
ls ra-tracker/ra_tracker/web/templates/base.html  # ✓ EXISTS
ls ra-tracker/ra_tracker/web/templates/dashboard.html  # ✓ EXISTS
# ... (all 16 web templates verified)

# Email Templates
ls ra-tracker/ra_tracker/web/templates/email/notification.html  # ✓ EXISTS
ls ra-tracker/ra_tracker/web/templates/email/verification.html  # ✓ EXISTS
# ... (all 5 email templates verified)

# Services
ls ra-tracker/ra_tracker/services/email_sender.py  # ✓ EXISTS
ls ra-tracker/ra_tracker/services/telegram_bot.py  # ✓ EXISTS
ls ra-tracker/ra_tracker/services/notifier.py  # ✓ EXISTS
ls ra-tracker/ra_tracker/scheduler/jobs.py  # ✓ EXISTS
```

**Commits verification:**
```bash
git log --oneline | grep "22de621"  # ✓ FOUND
git log --oneline | grep "9a1ae86"  # ✓ FOUND
```

## Self-Check: PASSED

All files exist, all commits found, verification complete.

---

*Summary completed: 2026-02-09*
*Duration: 9 minutes*
*Tasks: 2/2 (100%)*
