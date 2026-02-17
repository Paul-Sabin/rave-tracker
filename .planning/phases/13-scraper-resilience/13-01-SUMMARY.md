---
phase: 13-scraper-resilience
plan: 01
subsystem: scraper-resilience
tags: [resilience, retry, circuit-breaker, user-agent-rotation]
dependency_graph:
  requires:
    - ra-tracker/ra_tracker/api/ra_client.py (existing GraphQL client)
  provides:
    - Enhanced RAClient with retry/backoff/jitter/UA rotation
    - Circuit breaker state machine for fetch cycle protection
  affects:
    - All event fetching operations (artist, venue, promoter)
tech_stack:
  added:
    - fake-useragent>=1.5.0 (browser User-Agent rotation)
    - urllib3.util.retry.Retry (exponential backoff)
    - requests.adapters.HTTPAdapter (retry strategy mounting)
  patterns:
    - Circuit breaker pattern (CLOSED/OPEN/HALF_OPEN)
    - Exponential backoff with jitter
    - Progressive cooldown doubling
key_files:
  created:
    - ra-tracker/ra_tracker/api/circuit_breaker.py (139 lines)
  modified:
    - ra-tracker/ra_tracker/api/ra_client.py (+87 lines, -13 lines)
    - ra-tracker/requirements.txt (+1 dependency)
decisions:
  - "Use fake-useragent library for real browser UA strings (Chrome, Firefox, Safari 100+)"
  - "Rotate User-Agent every 5-10 requests (random interval)"
  - "Random 1-3s delays between all requests (not just rate limiting)"
  - "403 raises IPBlockedException immediately (no retry)"
  - "429/5xx use urllib3 Retry with exponential backoff (1s, 2s, 4s)"
  - "Circuit breaker trips after 3 consecutive failures, cooldown doubles (1h, 2h, 4h, max 24h)"
  - "Circuit breaker is in-memory singleton (resets on app restart)"
metrics:
  duration: "2m 51s"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
  commits: 2
  completed_at: "2026-02-17T20:22:13Z"
---

# Phase 13 Plan 01: Enhanced Scraper Resilience Summary

**One-liner:** JWT-style retry with exponential backoff, User-Agent rotation via fake-useragent, and circuit breaker state machine for fetch cycle protection.

## What Was Built

Added production-grade resilience to the RA.co scraper to handle cloud IP blocking (403), rate limiting (429), and server errors (5xx) gracefully:

1. **Enhanced RAClient** (`ra_client.py`):
   - urllib3 Retry strategy: 3 attempts with 1s/2s/4s exponential backoff
   - fake-useragent: Rotates real browser User-Agent strings every 5-10 requests
   - Random 1-3s delays between all requests (pacing to appear more human)
   - Differential error handling: 403 → IPBlockedException, 429 → respect Retry-After, 5xx → retry
   - Logs all response status codes at info level

2. **Circuit Breaker State Machine** (`circuit_breaker.py`):
   - CLOSED → OPEN after 3 consecutive failed fetch cycles
   - OPEN → HALF_OPEN after cooldown (probe recovery)
   - Progressive cooldown: starts at 1h, doubles to max 24h
   - Admin override: force_close() method
   - Status API: get_status() and get_recent_errors() for dashboard integration
   - In-memory singleton (resets on app restart per user decision)

## Deviations from Plan

None - plan executed exactly as written.

## Key Decisions Made

1. **User-Agent rotation pattern**: Chose 5-10 request interval (random) to balance between looking human-like and not thrashing the UA generator too frequently.

2. **Retry strategy mounting**: Used HTTPAdapter on both https:// and http:// for complete coverage.

3. **Error logging**: Log response status codes at INFO level (not DEBUG) since these are critical for diagnosing scraper issues.

4. **Circuit breaker diagnostics**: Store last 10 errors with timestamps for admin dashboard (not just count).

## Technical Implementation

**RAClient enhancements:**
```python
# Retry strategy with exponential backoff
retry_strategy = Retry(
    total=3,  # 3 retries
    backoff_factor=1,  # Produces 1s, 2s, 4s delays
    status_forcelist=[429, 500, 502, 503, 504],  # NOT 403
    allowed_methods=["POST"],
    respect_retry_after_header=True,
    raise_on_status=False
)
```

**Circuit breaker state transitions:**
- CLOSED (normal) → OPEN (after 3 failures)
- OPEN (blocking) → HALF_OPEN (after cooldown elapsed)
- HALF_OPEN (probe) → CLOSED (if successful) or OPEN (if failed, double cooldown)

## Files Changed

**Created:**
- `ra-tracker/ra_tracker/api/circuit_breaker.py` (139 lines)
  - CircuitBreaker class
  - CircuitBreakerStatus dataclass
  - Module-level singleton: circuit_breaker

**Modified:**
- `ra-tracker/ra_tracker/api/ra_client.py` (+87, -13 lines)
  - Added imports: random, HTTPAdapter, Retry, UserAgent
  - New exception classes: ScraperError, IPBlockedException
  - Enhanced __init__: UA generator, retry strategy, adapter mounting
  - New methods: _rotate_user_agent(), _add_request_delay()
  - Enhanced _execute(): UA rotation, delays, differential error handling
- `ra-tracker/requirements.txt` (+1 line)
  - Added: fake-useragent>=1.5.0

## Testing & Verification

**Verified:**
- RAClient imports work (IPBlockedException, ScraperError)
- fake-useragent generates browser UA strings
- Circuit breaker state transitions: CLOSED → OPEN → HALF_OPEN → CLOSED
- Circuit breaker blocks fetches when OPEN
- force_close() resets state
- get_status() returns correct state snapshot

**Backward compatibility:**
All existing RAClient public methods (get_artist_events, get_venue_events, get_promoter_events, search_*) unchanged - they inherit resilience automatically through _execute().

## Next Steps

**Immediate:**
1. Plan 13-02: Admin dashboard integration
   - Scraper status panel showing circuit breaker state
   - Recent error log display
   - Manual fetch button (bypasses circuit breaker)
   - Configurable fetch schedule

2. Plan 13-03: Fetch access control
   - Remove user-triggered fetches
   - Keep only scheduled fetches and admin manual fetch

**Future considerations:**
- Monitor 403 frequency in production (may need proxy rotation if persistent)
- Consider persisting circuit breaker state across restarts (currently in-memory)
- Add metrics tracking for scraper reliability (uptime, error rates)

## Self-Check: PASSED

**Files exist:**
- FOUND: ra-tracker/ra_tracker/api/circuit_breaker.py
- FOUND: ra-tracker/ra_tracker/api/ra_client.py
- FOUND: ra-tracker/requirements.txt

**Commits exist:**
- FOUND: cf53545 (Task 1: RAClient enhancements)
- FOUND: 61991da (Task 2: Circuit breaker)

**Imports work:**
- PASSED: from ra_tracker.api.ra_client import RAClient, IPBlockedException
- PASSED: from ra_tracker.api.circuit_breaker import circuit_breaker
- PASSED: fake-useragent in requirements.txt
