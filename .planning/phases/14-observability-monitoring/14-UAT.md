---
status: testing
phase: 14-observability-monitoring
source: [14-01-SUMMARY.md, 14-02-SUMMARY.md, 14-03-SUMMARY.md, 14-04-SUMMARY.md]
started: 2026-02-20T19:15:00Z
updated: 2026-02-20T19:20:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 2
name: Structured JSON access logs in stdout
expected: |
  When the app runs locally (or in Railway logs), each HTTP request produces a
  single JSON log line with these top-level keys: timestamp, level, logger
  (ra_tracker.access), message (e.g. "GET /admin 200 12.4ms"), request_id,
  method, path, status_code, duration_ms. Requests to /health and /static/*
  do not appear in the logs.
awaiting: user response

## Tests

### 1. X-Request-ID header on HTTP responses
expected: Make any request to the running app (e.g. navigate to the homepage or /admin). The response headers include X-Request-ID with a 32-character hex value. Every request gets a unique ID — refreshing gives a different value.
result: issue
reported: "There is no x-request-id header — only x-railway-request-id (Railway's own header) is present"
severity: major

### 2. Structured JSON access logs in stdout
expected: When the app runs locally (or in Railway logs), each HTTP request produces a single JSON log line containing these fields as top-level keys: timestamp, level, logger (ra_tracker.access), message (e.g. "GET /admin 200 12.4ms"), request_id, method, path, status_code, duration_ms. Requests to /health and /static/* do not appear in the logs.
result: [pending]

### 3. Admin scraper status — Health Overview card
expected: Navigate to /admin/scraper-status. A "Health Overview" card is visible showing: a success rate percentage (e.g. "95%"), a trend indicator (↑ / → / ↓), and a count of total fetch cycles.
result: [pending]

### 4. Admin scraper status — Fetch History table
expected: Navigate to /admin/scraper-status. A "Fetch History" section is visible with a table showing the last ~20 fetch cycles. Each row shows: started time, duration, status (success/failure/skipped), and optionally error details for failures.
result: [pending]

### 5. Admin scraper status — Consecutive Failures & Alert Status
expected: Navigate to /admin/scraper-status. The Current Status card includes: (a) a "Consecutive Failures" counter (shows 0 when scraper is healthy), and (b) an "Alert Status" section that shows "No alert" / warning / active-alert depending on failure state.
result: [pending]

### 6. App degrades gracefully without observability credentials
expected: Start the app with no SENTRY_DSN or LOGTAIL_SOURCE_TOKEN environment variables set. The app starts without errors. Logs still emit structured JSON to stdout. No crashes or import errors from the observability module.
result: [pending]

### 7. Sentry error tracking (requires live SENTRY_DSN)
expected: With SENTRY_DSN configured on Railway, trigger an unhandled exception in the app. The error appears in Sentry with: stack trace, request_id tag, user context (user_id + email) if the request was authenticated. Skip this test if Sentry is not yet configured.
result: [pending]

### 8. Better Stack log shipping (requires live LOGTAIL_SOURCE_TOKEN)
expected: With LOGTAIL_SOURCE_TOKEN configured on Railway, make a few requests. Structured JSON log lines appear in Better Stack (logs.betterstack.com) within ~30 seconds. Skip this test if Better Stack is not yet configured.
result: [pending]

### 9. Telegram scraper failure alert
expected: With Telegram bot configured (telegram.bot_token + telegram.chat_id in config.yaml), simulate or wait for 3 consecutive scraper fetch failures. Admin receives a Telegram message describing the failure. A 4th failure does NOT send a duplicate alert. When the scraper recovers, admin receives a recovery notification. Skip if Telegram is not yet configured.
result: [pending]

## Summary

total: 9
passed: 0
issues: 1
pending: 8
skipped: 0

## Gaps

- truth: "Every HTTP response includes an X-Request-ID header with a 32-character hex value"
  status: failed
  reason: "User reported: There is no x-request-id header — only x-railway-request-id (Railway's own header) is present"
  severity: major
  test: 1
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
