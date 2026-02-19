# Phase 14: Observability & Monitoring - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Production issues are detected and debuggable via structured logging, error tracking, and scraper health monitoring. Admin can diagnose issues without SSH access. Alerts notify on scraper failures.

</domain>

<decisions>
## Implementation Decisions

### Log format & visibility
- Structured JSON format in production (machine-parseable, one JSON object per line)
- Every HTTP request gets a unique request ID (UUID), included in both response headers (X-Request-ID) and all log entries
- Ship logs to an external log aggregation service (not just Railway built-in)
- Standard fields per log entry: timestamp, level, message, request ID, user ID, path, HTTP status code

### Error tracking
- Use Sentry free tier (sentry.io) for error tracking
- Capture per error: stack trace, request info (URL, method, status), and user context (user ID, email if logged in, session info)
- Group duplicate errors automatically (Sentry's built-in fingerprinting)

### Alert delivery & thresholds
- Scraper failure alerts via Telegram only (existing bot integration)
- Alert fires after 3 consecutive scraper failures
- Alert fires once, then silences until recovery (no repeating reminders)
- Send recovery notification when scraper starts working again ("Scraper recovered after X failures")

### Scraper health dashboard
- Enhance existing /admin/scraper-status page (no separate monitoring view)
- Show success rate + trend (improving/declining) at a glance
- Show recent fetch history: last 10-20 fetch cycles with timestamp, duration, events found, errors
- Persist fetch state to database (fixes "Last Successful Fetch: Never" across workers)

### Claude's Discretion
- Scraper errors in Sentry vs separate — Claude determines cleanest separation
- External log service selection (Logtail, Datadog, Papertrail — pick simplest/cheapest)
- Exact JSON log schema and field naming
- Dashboard layout and metric presentation
- Sentry SDK configuration details

</decisions>

<specifics>
## Specific Ideas

- Current /admin/scraper-status already has circuit breaker state, error count, and recent errors table — enhance this rather than rebuilding
- The "Last Successful Fetch: Never" problem is caused by in-memory state not shared across gunicorn workers — persist to DB
- Existing Telegram bot already sends user notifications — reuse for admin alerts
- Railway logs only capture stderr — structured logging should go to external service for full visibility

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-observability-monitoring*
*Context gathered: 2026-02-19*
