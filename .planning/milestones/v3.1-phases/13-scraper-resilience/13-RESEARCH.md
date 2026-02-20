# Phase 13: Scraper Resilience - Research

**Researched:** 2026-02-17
**Domain:** Web scraping resilience, retry logic, circuit breakers, anti-blocking
**Confidence:** HIGH

## Summary

This phase adds fault-tolerance to the RA.co GraphQL scraper to handle cloud IP blocking, API failures, and transient errors. The research confirms that the user's chosen architecture (exponential backoff with jitter, circuit breaker pattern, User-Agent rotation, differential HTTP error handling) aligns with industry best practices for production web scrapers.

**Key findings:**
- The `requests` library already supports exponential backoff via `urllib3.Retry`, but lacks built-in circuit breaker and jitter
- Python circuit breaker libraries exist but are simple to hand-roll for this use case
- User-Agent rotation is critical for cloud-hosted scrapers (datacenter IPs have 3-4x higher block rates)
- 403 vs 429 errors require fundamentally different strategies (IP reputation vs rate limiting)
- APScheduler (already in use) supports dynamic schedule reconfiguration at runtime

**Primary recommendation:** Build retry/backoff/circuit-breaker logic directly into `RAClient` using `urllib3.Retry` + custom wrapper. Keep it simple and tailored to RA.co's specific behavior patterns rather than adding dependencies.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Retry & backoff strategy:**
- 3 retries per failed request with exponential backoff (1s, 2s, 4s base delays)
- Add jitter (randomness) to backoff delays to look less bot-like
- Differentiate HTTP error types: 403 (blocked), 429 (rate limited), 5xx (server error) each get distinct handling
- After all retries exhausted: log the failure and wait for next scheduled cycle (no admin notification)

**Blocking response:**
- User-Agent rotation: Claude's discretion on approach (real browser UAs vs simple rotation)
- 403 (blocked): significantly longer cooldown before retrying (e.g., 30min-1hr), not normal backoff
- 429 (rate limited): respect Retry-After header if present
- Add random delays (1-3s) between individual requests within a fetch cycle — pacing to look more human

**Circuit breaker behavior:**
- Trip after 3 consecutive failed fetch cycles
- Half-open probe recovery: after cooldown, send single test request before resuming full scraping
- Progressive cooldown: starts at 1 hour, doubles on repeated failures (1h, 2h, 4h, max 24h)
- Circuit breaker state resets on app restart (in-memory, not persisted)

**Fetch access control:**
- Remove regular user ability to trigger event fetches
- Only scheduled fetches and admin manual fetch allowed
- Admin page: configurable fetch schedule (time and frequency)

**Degradation UX:**
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
- Exact jitter algorithm (Full Jitter vs Equal Jitter vs Decorrelated)
- Exact 403 cooldown duration within the 30min-1hr range
- Status code logging format and storage
- Admin status panel layout and styling

### Deferred Ideas (OUT OF SCOPE)

- Admin configurable notification schedule (time and frequency) — separate from scraper resilience, belongs in a notification management phase
</user_constraints>

## Standard Stack

### Core Libraries (Already Installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| requests | 2.31.0+ | HTTP client | Industry standard, built on urllib3 with retry support |
| urllib3 | (via requests) | HTTP connection pooling, retry logic | Mature retry mechanism with Retry-After header support |
| apscheduler | 3.10.0+ | Job scheduling | Already in use, supports dynamic schedule changes via `modify_job()` |

### Supporting Libraries (Recommended)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| fake-useragent | 1.5.0+ | User-Agent rotation | Maintains 326k+ real-world browser strings, auto-updates |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled circuit breaker | pybreaker/circuitbreaker library | Libraries add dependency but user wants in-memory (not persistent) state — simple enough to hand-roll |
| fake-useragent | Manual UA list | Library stays current with latest browsers, manual list goes stale |
| Custom backoff | backoff/tenacity decorator library | Decorators elegant but harder to integrate with existing RAClient session — urllib3.Retry better fit |

**Installation:**
```bash
pip install fake-useragent>=1.5.0
```

## Architecture Patterns

### Recommended Project Structure

```
ra-tracker/
├── ra_tracker/
│   ├── api/
│   │   ├── ra_client.py          # Enhanced with retry/backoff/UA rotation
│   │   └── circuit_breaker.py    # New: Circuit breaker state manager
│   ├── services/
│   │   └── fetcher.py            # Modified: Use circuit breaker, track health
│   ├── scheduler/
│   │   └── jobs.py               # Modified: Check circuit breaker before fetch
│   ├── web/
│   │   ├── admin.py              # New route: /admin/scraper-status
│   │   └── routes.py             # Modified: Admin-only fetch trigger
│   └── database.py               # New table: scraper_health_log
```

### Pattern 1: Layered Resilience

**What:** Separate concerns across three layers:
1. **Request-level resilience** (RAClient): Retry individual HTTP requests with exponential backoff + jitter
2. **Fetch-cycle resilience** (CircuitBreaker): Track entire fetch cycle success/failure, trip on consecutive failures
3. **System-level resilience** (Scheduler): Continue serving existing events when scraper is down

**When to use:** Always — this is the production-grade pattern for scrapers.

**Example:**
```python
# Layer 1: Request-level retry (in RAClient._execute)
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

retry_strategy = Retry(
    total=3,
    backoff_factor=1,  # 1s, 2s, 4s
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST"],  # GraphQL uses POST
    respect_retry_after_header=True  # For 429 responses
)
adapter = HTTPAdapter(max_retries=retry_strategy)
self.session.mount("https://", adapter)

# Layer 2: Circuit breaker (in CircuitBreaker)
class CircuitBreaker:
    def __init__(self):
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        self.last_failure_time = None
        self.cooldown_duration = 3600  # 1 hour base

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
        self.cooldown_duration = 3600  # Reset to 1 hour

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= 3:
            self.state = "OPEN"
            self.last_failure_time = datetime.now()

    def should_allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            # Check if cooldown expired
            elapsed = (datetime.now() - self.last_failure_time).total_seconds()
            if elapsed >= self.cooldown_duration:
                self.state = "HALF_OPEN"
                return True  # Allow one probe
            return False
        if self.state == "HALF_OPEN":
            return True  # Allow probe
        return False

# Layer 3: Graceful degradation (in routes)
@router.get("/dashboard")
async def dashboard(user: User = Depends(require_verified_email)):
    events = db.get_upcoming_events()  # Always works, even if scraper down
    return templates.TemplateResponse("dashboard.html", {"events": events})
```

### Pattern 2: Differential Error Handling

**What:** Different HTTP errors require different strategies:
- **403 (Forbidden)**: IP reputation issue → Long cooldown (30-60min), rotate User-Agent
- **429 (Rate Limited)**: Too fast → Respect Retry-After header, slow down
- **5xx (Server Error)**: RA.co having issues → Normal exponential backoff

**When to use:** For all production scrapers dealing with anti-bot systems.

**Example:**
```python
def _execute(self, query: str, variables: dict = None) -> dict:
    try:
        response = self.session.post(RA_GRAPHQL_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        if e.response.status_code == 403:
            # IP blocked - record and bail out for this cycle
            logger.error(f"403 Forbidden - IP blocked. Cooldown for 30-60min.")
            self._record_403_block()
            raise  # Don't retry, let circuit breaker handle
        elif e.response.status_code == 429:
            # Rate limited - urllib3.Retry handles this with Retry-After
            logger.warning(f"429 Rate Limited")
            raise  # Retry will honor Retry-After header
        else:
            # 5xx or other - normal retry
            logger.warning(f"HTTP {e.response.status_code}: {e}")
            raise
```

### Pattern 3: Jitter for Humanization

**What:** Add randomness to backoff delays to:
1. Prevent synchronized retries from multiple sources
2. Make request timing less predictable (look less bot-like)

**When to use:** Always with exponential backoff in production systems.

**Example (Full Jitter - AWS recommended):**
```python
import random

def exponential_backoff_with_jitter(attempt: int, base_delay: float = 1.0) -> float:
    """Full Jitter: sleep = random_between(0, min(cap, base * 2^attempt))"""
    max_delay = min(60, base_delay * (2 ** attempt))  # Cap at 60 seconds
    return random.uniform(0, max_delay)

# Usage in retry logic
for attempt in range(3):
    try:
        return self._make_request()
    except Exception as e:
        if attempt < 2:  # Don't sleep after last attempt
            sleep_time = exponential_backoff_with_jitter(attempt)
            logger.info(f"Retry {attempt+1}/3 after {sleep_time:.2f}s")
            time.sleep(sleep_time)
        else:
            raise
```

### Pattern 4: User-Agent Rotation

**What:** Rotate User-Agent strings across requests to avoid fingerprinting. Use real browser strings, not custom/outdated ones.

**When to use:** Always for cloud-hosted scrapers (datacenter IPs are flagged 3-4x more than residential).

**Example:**
```python
from fake_useragent import UserAgent

class RAClient:
    def __init__(self):
        self.session = requests.Session()
        self.ua_generator = UserAgent(
            browsers=['chrome', 'firefox', 'safari'],
            os=['windows', 'macos', 'linux'],
            min_version=100.0  # Only modern browsers
        )
        self._rotate_user_agent()

    def _rotate_user_agent(self):
        """Rotate User-Agent to a new random browser."""
        new_ua = self.ua_generator.random
        self.session.headers.update({
            "User-Agent": new_ua,
            "Content-Type": "application/json",
            "Referer": "https://ra.co/",
        })
        logger.debug(f"Rotated User-Agent: {new_ua[:50]}...")

    def _execute(self, query: str, variables: dict = None) -> dict:
        # Rotate UA every 5-10 requests (randomized)
        if random.randint(1, 10) <= 2:  # 20% chance
            self._rotate_user_agent()

        # Add random delay (1-3s) before request
        time.sleep(random.uniform(1.0, 3.0))

        # Make request...
```

### Pattern 5: Admin Monitoring Dashboard

**What:** Admin-only page showing scraper health, error logs, circuit breaker state, manual fetch trigger.

**When to use:** Essential for production systems with automated scrapers.

**Example structure:**
```html
<!-- templates/admin/scraper_status.html -->
<div class="scraper-status">
    <div class="status-indicator {{ 'healthy' if state == 'CLOSED' else 'degraded' if state == 'HALF_OPEN' else 'down' }}">
        {{ state }}
    </div>

    <div class="metrics">
        <p>Last successful fetch: {{ last_success or 'Never' }}</p>
        <p>Failed cycles: {{ failure_count }}</p>
        <p>Next scheduled: {{ next_fetch }}</p>
        {% if state == 'OPEN' %}
        <p>Cooldown remaining: {{ cooldown_remaining }}</p>
        {% endif %}
    </div>

    <div class="recent-errors">
        <h3>Recent Errors (Last 10)</h3>
        <table>
            <tr><th>Time</th><th>HTTP Code</th><th>Message</th></tr>
            {% for error in recent_errors %}
            <tr>
                <td>{{ error.timestamp }}</td>
                <td>{{ error.status_code or 'N/A' }}</td>
                <td>{{ error.message }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <form method="POST" action="/admin/scraper/fetch-now">
        <button type="submit">Force Fetch Now (Bypasses Circuit Breaker)</button>
    </form>
</div>
```

### Anti-Patterns to Avoid

- **Infinite retries**: Always set max retry count (3-5 is standard)
- **Retrying 4xx errors**: Client errors (except 429) won't be fixed by retrying
- **Ignoring Retry-After header**: 429 responses often include exact wait time
- **Static User-Agent**: Modern anti-bot systems fingerprint unchanging UAs
- **Synchronous retries**: Multiple clients retrying at same intervals creates thundering herd
- **Persistent circuit breaker state**: Can lock system in failed state across restarts

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| User-Agent database | Manual list of UAs | `fake-useragent` library | Library maintains 326k+ real strings, auto-updates with new browsers |
| Retry-After header parsing | Custom parser | `urllib3.Retry` built-in | Already handles header parsing, sleep timing, edge cases |
| Exponential backoff math | Custom formula | `urllib3.Retry(backoff_factor=N)` | Industry-tested implementation, handles overflow/caps |

**Key insight:** Web scraping resilience is complex because:
1. Anti-bot systems evolve (manual solutions go stale)
2. Edge cases are numerous (connection timeouts, DNS failures, partial responses)
3. Libraries like urllib3 have battle-tested logic from millions of deployments

**Exceptions where custom is OK:**
- Circuit breaker (simple state machine, user wants in-memory)
- Jitter addition (urllib3.Retry doesn't add jitter by default)
- 403 cooldown logic (specific to anti-bot behavior)

## Common Pitfalls

### Pitfall 1: Not Differentiating Error Types

**What goes wrong:** Treating all HTTP errors the same leads to ineffective retries. Retrying 403 errors with normal backoff wastes time and may worsen IP reputation.

**Why it happens:** Default retry libraries retry all 5xx and sometimes 429, but don't distinguish blocking (403) from rate limiting (429).

**How to avoid:**
- Configure `status_forcelist=[429, 500, 502, 503, 504]` (exclude 403)
- Handle 403 separately with long cooldown or circuit breaker trip
- Respect Retry-After for 429 via `respect_retry_after_header=True`

**Warning signs:**
- Logs show many 403 retries with 1s, 2s, 4s delays (won't help)
- Circuit breaker never trips (403s should trigger it)

### Pitfall 2: Cloud IP Detection

**What goes wrong:** Cloud providers (AWS, Railway, Google Cloud) use datacenter IP ranges. Websites detect these and apply stricter rate limits or block entirely. One study shows datacenter IPs have 3-4x higher block rate than residential.

**Why it happens:** RA.co may whitelist residential IPs but flag datacenter traffic as bots.

**How to avoid:**
- User-Agent rotation (critical on cloud IPs)
- Request pacing (1-3s delays between requests)
- Circuit breaker to avoid hammering when blocked
- Monitor 403 rate after deployment to Railway

**Warning signs:**
- High 403 rate in production vs local development
- Blocks occur quickly (within first 10-20 requests)
- Works locally but fails on Railway

### Pitfall 3: Circuit Breaker State Explosion

**What goes wrong:** Circuit breaker trips, cooldown never resets, system stays down even after external issue resolved.

**Why it happens:**
- No half-open state to test recovery
- Cooldown too long with no progressive backoff
- State persisted across restarts (old failures affect new deployments)

**How to avoid:**
- Implement half-open state with single probe request
- Progressive cooldown (1h, 2h, 4h, max 24h) gives system multiple chances
- In-memory state resets on restart (fresh start after deploy/fix)
- Admin "Force Fetch" button to manually recover

**Warning signs:**
- Circuit stays open for days
- Manual restart required to recover
- No way to test if external service recovered

### Pitfall 4: Losing Scraper Health Visibility

**What goes wrong:** Scraper fails silently, users see stale data, admins don't know there's a problem until users complain.

**Why it happens:** No monitoring dashboard, logs buried, no alerting.

**How to avoid:**
- Admin dashboard showing:
  - Last successful fetch timestamp
  - Current state (healthy/degraded/down)
  - Recent error log (last 10 with HTTP codes)
  - Circuit breaker cooldown timer
- Regular users see existing events (silent degradation is feature, not bug)

**Warning signs:**
- Events stop updating but no one notices
- Admin has to SSH and tail logs to check health
- No visibility into 403 vs 429 vs 5xx error rates

### Pitfall 5: Thundering Herd on Recovery

**What goes wrong:** After circuit breaker opens, when it transitions to half-open, multiple scrapers/services send recovery probes simultaneously, overwhelming the recovering service.

**Why it happens:** Synchronized timers, no jitter on cooldown.

**How to avoid:**
- Add jitter to cooldown duration (e.g., 1h ± 5 minutes)
- Single probe in half-open state (not full retry storm)
- If probe fails, double cooldown before next try

**Warning signs:**
- Service recovers briefly then fails again
- Spikes in error rate at regular intervals
- Multiple "recovery attempt" log entries at same timestamp

## Code Examples

### Example 1: Enhanced RAClient with Retry & Jitter

```python
# Source: Synthesized from urllib3 docs + AWS backoff best practices
import random
import time
import logging
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class RAClient:
    """GraphQL client for ra.co with retry, backoff, jitter, UA rotation."""

    def __init__(self):
        self.session = requests.Session()

        # User-Agent rotation
        self.ua_generator = UserAgent(
            browsers=['chrome', 'firefox', 'safari'],
            os=['windows', 'macos', 'linux'],
            min_version=100.0
        )

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,  # 3 retries per user decision
            backoff_factor=1,  # 1s base, becomes 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],  # NOT 403
            allowed_methods=["POST"],  # GraphQL uses POST
            respect_retry_after_header=True,  # For 429
            raise_on_status=False  # We'll handle status codes manually
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self._rotate_user_agent()
        self._request_count = 0
        self._last_request_time = 0

    def _rotate_user_agent(self):
        """Rotate User-Agent to a fresh browser string."""
        new_ua = self.ua_generator.random
        self.session.headers.update({
            "User-Agent": new_ua,
            "Content-Type": "application/json",
            "Referer": "https://ra.co/",
        })
        logger.debug(f"Rotated UA: {new_ua[:60]}...")

    def _add_jitter_delay(self):
        """Add random 1-3s delay between requests (humanization)."""
        delay = random.uniform(1.0, 3.0)
        time.sleep(delay)
        logger.debug(f"Request pacing: {delay:.2f}s")

    def _execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query with retry/backoff/jitter."""

        # Rotate UA every 5-10 requests (random)
        self._request_count += 1
        if self._request_count % random.randint(5, 10) == 0:
            self._rotate_user_agent()

        # Add humanization delay (1-3s)
        self._add_jitter_delay()

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = self.session.post(RA_GRAPHQL_URL, json=payload, timeout=30)

            # Handle 403 specially (IP blocked)
            if response.status_code == 403:
                logger.error("403 Forbidden - IP blocked. Aborting cycle.")
                raise IPBlockedException("IP blocked by RA.co")

            # Raise for other HTTP errors (429, 5xx will be retried by urllib3)
            response.raise_for_status()

            data = response.json()
            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                raise GraphQLException(f"GraphQL errors: {data['errors']}")

            return data.get("data", {})

        except requests.HTTPError as e:
            # Log status code for monitoring
            status = e.response.status_code if e.response else None
            logger.error(f"HTTP {status}: {e}")
            raise
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

class IPBlockedException(Exception):
    """Raised when IP is blocked (403), should trip circuit breaker."""
    pass

class GraphQLException(Exception):
    """Raised when GraphQL returns errors."""
    pass
```

### Example 2: Circuit Breaker State Manager

```python
# Source: Synthesized from pybreaker patterns + user requirements
from datetime import datetime, timedelta
from typing import Optional, Literal
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

State = Literal["CLOSED", "OPEN", "HALF_OPEN"]

@dataclass
class CircuitBreakerStatus:
    """Circuit breaker status for admin dashboard."""
    state: State
    failure_count: int
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    cooldown_duration: int  # seconds
    cooldown_remaining: Optional[int]  # seconds, None if not in OPEN state

class CircuitBreaker:
    """Circuit breaker for fetch operations.

    - Trips OPEN after 3 consecutive failed fetch cycles
    - OPEN -> HALF_OPEN after progressive cooldown (1h, 2h, 4h, max 24h)
    - HALF_OPEN allows single probe; success -> CLOSED, failure -> OPEN
    - State is in-memory (resets on app restart)
    """

    def __init__(self):
        self.state: State = "CLOSED"
        self.failure_count = 0
        self.last_success: Optional[datetime] = None
        self.last_failure: Optional[datetime] = None
        self.cooldown_duration = 3600  # Start at 1 hour
        self.max_cooldown = 86400  # 24 hours max

    def should_allow_fetch(self) -> bool:
        """Check if fetch should be allowed based on circuit breaker state."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Check if cooldown period expired
            if self.last_failure:
                elapsed = (datetime.now() - self.last_failure).total_seconds()
                if elapsed >= self.cooldown_duration:
                    logger.info(f"Circuit breaker cooldown expired. Transitioning to HALF_OPEN for probe.")
                    self.state = "HALF_OPEN"
                    return True
                else:
                    remaining = self.cooldown_duration - elapsed
                    logger.debug(f"Circuit breaker OPEN. Cooldown remaining: {remaining:.0f}s")
                    return False
            return False

        if self.state == "HALF_OPEN":
            # Allow single probe
            logger.info("Circuit breaker HALF_OPEN. Allowing probe request.")
            return True

        return False

    def record_success(self):
        """Record successful fetch cycle."""
        logger.info("Fetch cycle successful. Circuit breaker CLOSED.")
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_success = datetime.now()
        self.cooldown_duration = 3600  # Reset to 1 hour

    def record_failure(self):
        """Record failed fetch cycle."""
        self.failure_count += 1
        self.last_failure = datetime.now()

        if self.state == "HALF_OPEN":
            # Probe failed, go back to OPEN with doubled cooldown
            logger.warning(f"Probe failed. Circuit breaker OPEN. Doubling cooldown.")
            self.state = "OPEN"
            self._double_cooldown()
        elif self.failure_count >= 3:
            # Trip to OPEN
            logger.error(f"Circuit breaker tripped after {self.failure_count} failures. State: OPEN")
            self.state = "OPEN"
        else:
            logger.warning(f"Fetch cycle failed ({self.failure_count}/3). Circuit breaker still CLOSED.")

    def _double_cooldown(self):
        """Double cooldown duration (progressive backoff), max 24h."""
        self.cooldown_duration = min(self.cooldown_duration * 2, self.max_cooldown)
        logger.info(f"Cooldown doubled to {self.cooldown_duration}s ({self.cooldown_duration/3600:.1f}h)")

    def get_status(self) -> CircuitBreakerStatus:
        """Get current status for admin dashboard."""
        cooldown_remaining = None
        if self.state == "OPEN" and self.last_failure:
            elapsed = (datetime.now() - self.last_failure).total_seconds()
            cooldown_remaining = max(0, int(self.cooldown_duration - elapsed))

        return CircuitBreakerStatus(
            state=self.state,
            failure_count=self.failure_count,
            last_success=self.last_success,
            last_failure=self.last_failure,
            cooldown_duration=self.cooldown_duration,
            cooldown_remaining=cooldown_remaining
        )

    def force_close(self):
        """Admin override to force circuit closed (for manual fetch)."""
        logger.warning("Circuit breaker FORCE CLOSED by admin.")
        self.state = "CLOSED"
        self.failure_count = 0
```

### Example 3: Modified Fetcher with Circuit Breaker Integration

```python
# Source: Modified from existing fetcher.py
from ..api.circuit_breaker import CircuitBreaker, IPBlockedException
from ..database import get_db

circuit_breaker = CircuitBreaker()  # Global singleton

class Fetcher:
    def __init__(self):
        self.client = RAClient()
        self.db = get_db()

    def fetch_all_rules(self) -> Dict[int, List[Event]]:
        """Fetch events for all active rules (respects circuit breaker)."""

        # Check circuit breaker
        if not circuit_breaker.should_allow_fetch():
            status = circuit_breaker.get_status()
            logger.warning(f"Fetch blocked by circuit breaker. State: {status.state}, Cooldown: {status.cooldown_remaining}s")
            return {}

        rules = self.db.get_active_rules()
        if not rules:
            logger.warning("No active rules configured")
            return {}

        results = {}
        fetch_succeeded = True

        try:
            for rule in rules:
                try:
                    events = self.fetch_for_rule(rule)
                    results[rule.id] = events
                except IPBlockedException:
                    # 403 error - abort entire cycle
                    logger.error("IP blocked. Aborting fetch cycle.")
                    fetch_succeeded = False
                    break
                except Exception as e:
                    logger.error(f"Failed to fetch for rule {rule.target_name}: {e}")
                    fetch_succeeded = False

            if fetch_succeeded:
                circuit_breaker.record_success()
            else:
                circuit_breaker.record_failure()

            return results

        except Exception as e:
            logger.error(f"Fetch cycle failed: {e}", exc_info=True)
            circuit_breaker.record_failure()
            return {}
```

### Example 4: Admin Scraper Status Route

```python
# Source: New route in admin.py
from fastapi import APIRouter, Request, Depends
from ..api.circuit_breaker import circuit_breaker
from ..scheduler.jobs import get_last_fetch_time, get_next_fetch_time
from ..database import get_db

@admin_router.get("/scraper-status", response_class=HTMLResponse)
async def scraper_status(request: Request, user: User = Depends(require_admin)):
    """Admin scraper health monitoring dashboard."""
    templates = get_templates(request)
    db = get_db()

    # Get circuit breaker status
    cb_status = circuit_breaker.get_status()

    # Get recent errors (last 10 from scraper_health_log table)
    recent_errors = db.get_recent_scraper_errors(limit=10)

    # Scheduler info
    last_fetch = get_last_fetch_time()
    next_fetch = get_next_fetch_time()

    return templates.TemplateResponse(
        "admin/scraper_status.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "state": cb_status.state,
            "failure_count": cb_status.failure_count,
            "last_success": cb_status.last_success,
            "last_failure": cb_status.last_failure,
            "cooldown_duration": cb_status.cooldown_duration,
            "cooldown_remaining": cb_status.cooldown_remaining,
            "recent_errors": recent_errors,
            "last_fetch": last_fetch,
            "next_fetch": next_fetch,
        },
    )

@admin_router.post("/scraper/fetch-now")
async def force_fetch(request: Request, user: User = Depends(require_admin)):
    """Admin manual fetch (bypasses circuit breaker)."""
    from ..scheduler.jobs import run_fetch_now
    import threading

    # Force circuit breaker closed for this fetch
    circuit_breaker.force_close()

    # Run fetch in background
    threading.Thread(target=run_fetch_now, daemon=True).start()

    return RedirectResponse(url="/admin/scraper-status", status_code=303)
```

### Example 5: Scraper Health Log Schema

```python
# Source: New database migration
CREATE TABLE IF NOT EXISTS scraper_health_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status_code INTEGER,  -- HTTP status code (or NULL for non-HTTP errors)
    error_message TEXT,
    error_type TEXT,  -- 'HTTP', 'TIMEOUT', 'DNS', 'GRAPHQL', etc.
    circuit_breaker_state TEXT,  -- 'CLOSED', 'OPEN', 'HALF_OPEN'
    rule_id INTEGER REFERENCES rules(id) ON DELETE SET NULL
);

CREATE INDEX idx_scraper_health_timestamp ON scraper_health_log(timestamp DESC);
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Static User-Agent | Rotating real browser strings | 2023-2024 | Anti-bot systems fingerprint static UAs; rotation critical for cloud IPs |
| Retry all 4xx | Differentiate 403/429/other | 2022-2023 | 403 (blocked) needs different strategy than 429 (rate limited) |
| Linear backoff | Exponential backoff + jitter | 2018 (AWS blog post) | Prevents thundering herd, faster recovery |
| urllib3.Retry defaults | `respect_retry_after_header=True` | 2020 (urllib3 1.26) | Honors 429 Retry-After header automatically |
| Persistent circuit breaker | In-memory with restart reset | 2024-2025 | Prevents stale state locking system after fixes/deploys |

**Deprecated/outdated:**
- **Manual UA lists**: `fake-useragent` library (326k+ UAs) replaces static lists
- **Retrying all errors**: Modern practice is differentiated error handling (403 ≠ 429 ≠ 5xx)
- **No jitter**: AWS research proved jitter essential for distributed retry systems

## Open Questions

### Question 1: RA.co's Actual Rate Limiting on Railway IPs

**What we know:**
- RA.co likely has stricter limits for datacenter IPs (AWS, Railway)
- Existing scraper uses 1s delay between requests (MIN_REQUEST_INTERVAL = 1.0)
- No current 403 blocking observed in development (local IP)

**What's unclear:**
- What's RA.co's actual threshold for Railway IPs? (requests per minute/hour)
- Will 1-3s delays be sufficient or need wider range?
- Does RA.co block at IP level or subnet level?

**Recommendation:**
- Start with 1-3s delays as planned
- Monitor 403 rate after Railway deployment
- Add logging for "requests per cycle" and "time per cycle" metrics
- Be prepared to increase delay range to 3-5s if blocks occur

### Question 2: Should Circuit Breaker Trip on First 403?

**What we know:**
- User decided: 3 retries per request, circuit trips after 3 consecutive *cycles*
- 403 means IP blocked (won't be fixed by retries)

**What's unclear:**
- Should a single 403 abort the cycle and count as cycle failure?
- Or should circuit require 3 consecutive 403s (across cycles)?

**Recommendation:**
- Single 403 should abort current cycle and count as cycle failure
- 3 consecutive cycles with 403 = circuit trips
- This gives some tolerance (maybe 403 was transient) while preventing hammering

### Question 3: Error Log Storage Strategy

**What we know:**
- Admin dashboard needs last 5-10 errors with timestamps and HTTP codes
- Errors should include: timestamp, HTTP code, message, circuit breaker state

**What's unclear:**
- Database table vs in-memory ring buffer?
- Retention period? (keep errors for 7 days? 30 days?)
- Should we log ALL requests or only failures?

**Recommendation:**
- Use database table `scraper_health_log` (survives restarts)
- Log only failures (403, 429, 5xx, timeouts, exceptions)
- Retain for 30 days (auto-cleanup in daily purge job)
- Query via `SELECT * FROM scraper_health_log ORDER BY timestamp DESC LIMIT 10`

## Sources

### Primary (HIGH confidence)

**Retry & Backoff:**
- [How to Retry Failed Python Requests [2026] - ZenRows](https://www.zenrows.com/blog/python-requests-retry)
- [urllib3 Utilities Documentation](https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html)
- [backoff · PyPI](https://pypi.org/project/backoff/)
- [How to Retry Failed Python Requests in 2025 - Oxylabs](https://oxylabs.io/blog/python-requests-retry)

**Circuit Breaker:**
- [Circuit Breaker Pattern - Azure Architecture Center | Microsoft Learn](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
- [pybreaker · PyPI](https://pypi.org/project/pybreaker/)
- [circuitbreaker · PyPI](https://pypi.org/project/circuitbreaker/)
- [bliki: Circuit Breaker - Martin Fowler](https://martinfowler.com/bliki/CircuitBreaker.html)

**User-Agent Rotation:**
- [fake-useragent · PyPI](https://pypi.org/project/fake-useragent/)
- [How to Fake and Rotate User Agents Using Python 3 - ScrapeHero](https://www.scrapehero.com/how-to-fake-and-rotate-user-agents-using-python-3/)
- [Top User Agents for Web Scraping in 2026 [Updated List] - IProyal](https://iproyal.com/blog/user-agents-for-scraping/)

**HTTP Error Handling:**
- [What are 402, 403, 404, and 429 Errors in Web Scraping? - CapSolver](https://www.capsolver.com/blog/web-scraping/402-403-404-429-errors-web-scraping)
- [429 status code - what is it and how to avoid it? - ScrapingBee](https://www.scrapingbee.com/webscraping-questions/web-scraping-blocked/429-status-code-what-it-is-and-how-to-avoid-it/)
- [Rate Limit in Web Scraping: How It Works and 5 Bypass Methods - Scrape.do](https://scrape.do/blog/web-scraping-rate-limit/)

**Exponential Backoff with Jitter:**
- [Exponential Backoff And Jitter | AWS Architecture Blog](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [Timeouts, retries and backoff with jitter - AWS Builder's Library](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [Mastering Exponential Backoff in Distributed Systems - Better Stack](https://betterstack.com/community/guides/monitoring/exponential-backoff/)

**Cloud IP Blocking:**
- [How to Avoid Web Scraper IP Blocking? - ScrapFly](https://scrapfly.io/blog/posts/how-to-avoid-web-scraping-blocking-ip-addresses)
- [How to Avoid IP Bans: A Complete Web Scraping Guide 2026 - Affinco](https://affinco.com/avoid-ip-bans-scraping/)

**APScheduler:**
- [User guide — APScheduler 3.x documentation](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- [Job Scheduling in Python with APScheduler - Better Stack](https://betterstack.com/community/guides/scaling-python/apscheduler-scheduled-tasks/)

### Secondary (MEDIUM confidence)

- [Retrying and Exponential Backoff: Smart Strategies for Robust Software - HackerOne](https://www.hackerone.com/blog/retrying-and-exponential-backoff-smart-strategies-robust-software)
- [Circuit Breaker Pattern: How It Works, Benefits, Best Practices - Groundcover](https://www.groundcover.com/learn/performance/circuit-breaker-pattern)
- [User Agents in Web Scraping (Complete Guide + List of Agents) - ScrapingDog](https://www.scrapingdog.com/blog/user-agent-in-web-scraping/)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - urllib3.Retry is industry standard, fake-useragent widely used, APScheduler already in project
- Architecture: HIGH - Patterns verified across multiple authoritative sources (AWS, Microsoft Azure, Martin Fowler)
- Pitfalls: HIGH - Based on documented experiences from web scraping guides and anti-bot system studies
- Cloud IP blocking: MEDIUM - General principle well-documented, but RA.co's specific behavior on Railway unknown until tested

**Research date:** 2026-02-17
**Valid until:** 30 days (stable domain, but anti-bot systems evolve)
