# Phase 17 Context: Notification Dispatch Modes

**Captured:** 2026-02-23
**Source:** Design discussion in new-milestone session
**Depends on:** Phase 16 (config.py already extended with notification_mode, digest_time, fetch_times)

## What Phase 16 Already Built

`config.py` `SchedulerConfig` now has:
- `fetch_times: list[str]` — list of HH:MM strings (e.g. ["08:00", "20:00"])
- `notification_mode: str` — "upon_fetch" (default) or "daily_digest"
- `digest_time: str` — HH:MM string for daily digest send time (e.g. "09:00")

These are persisted to config.yaml and editable via `/admin/settings`.

## Notification Mode: Two Behaviours

### "Upon fetch" (default)
Current behaviour — preserved exactly as-is. When a fetch cycle finds new events matching a user's rules, notifications are sent immediately via Telegram/Email. No changes to this flow.

### "Daily digest"
New behaviour. When a fetch cycle finds new events:
- Events are **not sent immediately**
- They are **queued** — stored with a flag indicating "pending digest"
- A new daily scheduler job runs at `config.scheduler.digest_time` each day
- The digest job collects all queued events per user, sends a single batched message, then marks them as sent

## DB Schema Changes

The existing `notifications` table (or equivalent) needs a way to distinguish queued-but-not-sent events from already-sent ones. Options:
- Add a `queued_for_digest` boolean column (default False)
- Or add a `sent_at` nullable timestamp — NULL = queued, set = sent

Use whatever fits cleanest with the existing schema. The key constraint: in digest mode, the fetch job must NOT call the send functions — only mark events as pending.

## APScheduler: Fetch Schedule Migration

Current: `IntervalTrigger(hours=config.scheduler.fetch_interval_hours)`

New: `CronTrigger` based on `config.scheduler.fetch_times` list.

Example: fetch_times = ["08:00", "20:00"] → schedule fetch job at hour=8 and hour=20.

The old `fetch_interval_hours` field can remain in `SchedulerConfig` for backward compat but the scheduler should use `fetch_times` if set, falling back to `fetch_interval_hours` if `fetch_times` is empty.

Implementation note: Multiple specific times = multiple CronTrigger jobs (one per time), or a single job with `hour="8,20"` syntax. Either approach is fine.

## Daily Digest Job

New APScheduler job:
- Trigger: `CronTrigger` at `config.scheduler.digest_time`
- Action: For each user with queued events, collect all pending events, format a digest message, send via their enabled channels (Telegram/Email), mark as sent
- Only runs if `notification_mode == "daily_digest"` (or just always runs but skips if no queued events)

## Batched Notification Format

The digest message should group events clearly. Suggested format:
- Header: "Your daily Rave Tracker digest — [date]"
- Events grouped or listed with: artist/venue/promoter match, event name, date, venue, RA link
- Footer: unsubscribe link (for email)

Keep it consistent with existing notification message style.

## What "Upon fetch" Means for Existing Code

The existing fetch + notify flow in `scheduler/jobs.py` (`fetch_and_notify`) sends notifications inside the job. In digest mode, this send step must be skipped — events found but notifications deferred to the digest job.

The cleanest approach: after finding new events, check `config.scheduler.notification_mode`. If "upon_fetch" → send immediately (current path). If "daily_digest" → queue events, skip send.

## Out of Scope for This Phase

- Per-user notification mode override (admin sets system-wide policy)
- Quiet hours
- Minimum notification gap
- Retry logic for failed digest sends (use existing send error handling)
