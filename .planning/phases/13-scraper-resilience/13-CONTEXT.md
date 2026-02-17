# Phase 13: Scraper Resilience - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

RA.co scraper handles cloud IP blocking, API failures, and transient errors gracefully. The app continues serving existing events when the scraper is down. Regular users can no longer trigger fetches — only scheduled fetches and admin manual fetch.

</domain>

<decisions>
## Implementation Decisions

### Retry & backoff strategy
- 3 retries per failed request with exponential backoff (1s, 2s, 4s base delays)
- Add jitter (randomness) to backoff delays to look less bot-like
- Differentiate HTTP error types: 403 (blocked), 429 (rate limited), 5xx (server error) each get distinct handling
- After all retries exhausted: log the failure and wait for next scheduled cycle (no admin notification)

### Blocking response
- User-Agent rotation: Claude's discretion on approach (real browser UAs vs simple rotation)
- 403 (blocked): significantly longer cooldown before retrying (e.g., 30min-1hr), not normal backoff
- 429 (rate limited): respect Retry-After header if present
- Add random delays (1-3s) between individual requests within a fetch cycle — pacing to look more human

### Circuit breaker behavior
- Trip after 3 consecutive failed fetch cycles
- Half-open probe recovery: after cooldown, send single test request before resuming full scraping
- Progressive cooldown: starts at 1 hour, doubles on repeated failures (1h, 2h, 4h, max 24h)
- Circuit breaker state resets on app restart (in-memory, not persisted)

### Fetch access control
- Remove regular user ability to trigger event fetches
- Only scheduled fetches and admin manual fetch allowed
- Admin page: configurable fetch schedule (time and frequency)

### Degradation UX
- Users see no indication of scraper issues — existing events display silently without stale warnings
- Admin dashboard: detailed scraper status panel showing:
  - Last successful fetch time
  - Current state (healthy/degraded/down)
  - Error count since last success
  - Recent error log (last 5-10 errors with timestamps and HTTP codes)
  - Circuit breaker cooldown timer
- Admin "Fetch Now" button that bypasses circuit breaker for immediate scrape

### Claude's Discretion
- User-Agent string selection and rotation pattern
- Exact jitter algorithm
- Exact 403 cooldown duration within the 30min-1hr range
- Status code logging format and storage
- Admin status panel layout and styling

</decisions>

<specifics>
## Specific Ideas

- Scraper should pace requests with 1-3s random delays between them even during normal operation
- 403 handling is distinct from other errors — treat it as "IP is flagged, back off significantly"
- Circuit breaker self-heals via half-open probes, no manual intervention required (though admin can force fetch)
- App restart is effectively a manual circuit breaker reset

</specifics>

<deferred>
## Deferred Ideas

- Admin configurable notification schedule (time and frequency) — separate from scraper resilience, belongs in a notification management phase

</deferred>

---

*Phase: 13-scraper-resilience*
*Context gathered: 2026-02-17*
