# Phase 16 Context: Settings Page Split

**Captured:** 2026-02-22
**Source:** Design discussion in new-milestone session

## Core Decision: Option B — Two Separate Pages

Single `/settings` page split into two distinct pages:

- **`/settings`** — Personal settings only (all authenticated users)
- **`/admin/settings`** — System configuration (admin users only)

Rejected Option A (single page with conditional sections) in favour of cleaner separation matching the existing `/admin/` pattern.

## /settings — What Stays (All Users)

- **Notification Preferences** — Telegram link/unlink/toggle, Email toggle, Test notification button, Link modal
- **Account Security** — Change password link
- **Delete Account** — Danger zone with password confirmation modal

Admin users see the same personal sections PLUS a visible link to `/admin/settings`.

## /settings — What Is Removed

- **Local Area** — Removed entirely from settings; it now lives on `/tracking` page (moved in v3.2)
- **Scheduler Settings** (fetch interval field) — Moved to `/admin/settings`
- **Telegram Configuration** (bot token, admin chat ID) — Moved to `/admin/settings`
- **Test Admin Telegram** button — Moved to `/admin/settings`
- **Scheduler Status** — NOT moved anywhere; already covered by `/admin/scraper-status`, no duplication needed
- **Database info** — Moved to `/admin/settings`

## /admin/settings — What Goes Here

New page, sits alongside other admin pages (`/admin/scraper-status`, `/admin/audit-log`, etc.).

**System Configuration fields:**
- Telegram bot token (masked input)
- Admin chat ID (for admin alert notifications)
- Fetch schedule: specific times of day (e.g. 08:00, 20:00) — replaces the current interval field
- Event horizon (days) — currently hidden in config.yaml, expose as editable
- Notification mode toggle: "Upon fetch completion" (default) vs "Daily digest"
- Daily digest time field (shown/required when digest mode selected)

**Read-only display:**
- Database info (path or URL)

**Actions:**
- Test Admin Telegram button

**Access control:** Admin only. Non-admins get 403.

## Fetch Scheduling: Interval → Specific Times

Current behaviour: APScheduler `IntervalTrigger` with `fetch_interval_hours` (1–24h range).

New behaviour: Specific times of day (e.g. 08:00, 20:00). Admin adds/removes times. APScheduler switches to `CronTrigger`.

The interval field is removed from the UI entirely.

## Notification Mode

Two modes, admin-configured system-wide:

1. **Upon fetch completion** (default) — current behaviour preserved, notifications sent immediately when fetch finds new events
2. **Daily digest** — events found during fetch are queued (not sent); a new daily job sends batched notifications to each user at the configured digest time

Implementation note: Daily digest requires DB changes (queue state on notifications) and a new scheduler job.

## Overlap Resolution

`/admin/scraper-status` already shows: circuit breaker state, last/next fetch times, 7-day health metrics, recent cycles, force-fetch button. **Do not duplicate any of this on `/admin/settings`.**

## Endpoint Hardening (Phase 18 Concern, Noted Here)

Phase 16 is UI/template work. Server-side hardening of admin POST endpoints (`/settings/save`, `/settings/test-telegram`) is explicitly Phase 18.

For Phase 16: the UI simply doesn't show admin controls to non-admins. The backend enforcement follows in Phase 18.

## Navigation

Admin nav should include a link to `/admin/settings` consistent with existing admin nav links (audit-log, scraper-status, users).
