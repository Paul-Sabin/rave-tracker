# Phase 14: Observability & Monitoring - Research

**Researched:** 2026-02-19
**Domain:** Python structured logging, error tracking, and scraper health monitoring
**Confidence:** HIGH

## Summary

Phase 14 implements production observability through structured JSON logging, Sentry error tracking, enhanced scraper health dashboards, and Telegram alerting. The stack builds on existing FastAPI infrastructure with asgi-correlation-id for request tracking, python-json-logger for structured output, and Better Stack Logs (formerly Logtail) for external aggregation.

Key architectural insight: The project already has circuit breaker monitoring and scraper error logging infrastructure in place. This phase enhances visibility by externalizing logs, adding request correlation, and persisting scraper health state to the database (fixing the gunicorn worker memory isolation issue where "Last Successful Fetch: Never" appears despite successful fetches).

**Primary recommendation:** Use asgi-correlation-id + python-json-logger + Better Stack Logs (3GB free tier) for structured logging, Sentry free tier (5K errors/month) for error tracking, and extend existing database-backed scraper health logging with dashboard enhancements and Telegram admin alerts.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Log format & visibility:**
- Structured JSON format in production (machine-parseable, one JSON object per line)
- Every HTTP request gets a unique request ID (UUID), included in both response headers (X-Request-ID) and all log entries
- Ship logs to an external log aggregation service (not just Railway built-in)
- Standard fields per log entry: timestamp, level, message, request ID, user ID, path, HTTP status code

**Error tracking:**
- Use Sentry free tier (sentry.io) for error tracking
- Capture per error: stack trace, request info (URL, method, status), and user context (user ID, email if logged in, session info)
- Group duplicate errors automatically (Sentry's built-in fingerprinting)

**Alert delivery & thresholds:**
- Scraper failure alerts via Telegram only (existing bot integration)
- Alert fires after 3 consecutive scraper failures
- Alert fires once, then silences until recovery (no repeating reminders)
- Send recovery notification when scraper starts working again ("Scraper recovered after X failures")

**Scraper health dashboard:**
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

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

## Standard Stack

### Core Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asgi-correlation-id | 4.3.4 | Request ID generation/propagation | Production-stable ASGI middleware with FastAPI integration, automatic UUID validation, and built-in logging filter support |
| python-json-logger | 3.2.1+ | JSON log formatting | Minimal dependency, works with stdlib logging, widely used for production JSON logging without heavy framework |
| sentry-sdk | 2.19.0+ | Error tracking and performance monitoring | Official Sentry SDK with automatic FastAPI integration, requires zero middleware configuration |
| logtail-python | 0.2.13+ | Better Stack Logs integration | Official Better Stack (formerly Logtail) handler for Python stdlib logging |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-telegram-bot | 20.0+ (already installed) | Admin alert delivery | Already in use for user notifications, reuse for admin scraper alerts |
| psycopg2 | 2.9+ (already installed) | Database persistence for scraper health | Fix gunicorn worker isolation by persisting fetch state to PostgreSQL |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-json-logger | structlog | Structlog is more powerful but adds complexity and has sync/async isolation issues in FastAPI hybrid apps. python-json-logger is simpler, uses stdlib logging, and avoids context variable pitfalls. |
| Better Stack Logs | Datadog Logs | Datadog has richer features but expensive at scale ($0.10/GB vs enterprise pricing). Better Stack's 3GB free tier covers small-medium apps. |
| Better Stack Logs | Papertrail | Papertrail offers free tier but Better Stack provides 3GB free + SQL query interface + modern UX. Better Stack is successor to Logtail with active development. |
| Sentry | Self-hosted error tracking | Self-hosting requires infrastructure overhead. Sentry free tier (5K errors/month, 1 user) is sufficient for single-admin app. |

**Installation:**
```bash
pip install asgi-correlation-id python-json-logger sentry-sdk logtail-python
```

## Architecture Patterns

### Recommended Integration Structure

```
ra_tracker/
├── observability/
│   ├── __init__.py
│   ├── logging_config.py      # Centralized logging setup
│   ├── request_middleware.py  # Request ID + context binding
│   └── sentry_config.py       # Sentry initialization
├── services/
│   └── scraper_alerter.py     # Telegram admin alerts for scraper
└── database.py                # Enhanced scraper health persistence
```

### Pattern 1: Request ID Middleware with Logging Integration

**What:** ASGI middleware generates/validates UUIDs, adds to response headers, and makes available to loggers via context filter.

**When to use:** Every FastAPI application requiring request correlation across logs and errors.

**Example:**
```python
# Source: https://github.com/snok/asgi-correlation-id
from fastapi import FastAPI
from asgi_correlation_id import CorrelationIdMiddleware
from asgi_correlation_id.context import correlation_id
import logging

app = FastAPI()

# Add middleware first (before other middleware)
app.add_middleware(
    CorrelationIdMiddleware,
    header_name='X-Request-ID',
    update_request_header=True,
    generator=lambda: uuid4().hex,
    validator=is_valid_uuid4,
)

# Logging configuration with correlation ID filter
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'correlation_id': {
            '()': 'asgi_correlation_id.CorrelationIdFilter',
            'uuid_length': 32,
            'default_value': '-',
        },
    },
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s',
            'rename_fields': {'asctime': 'timestamp', 'levelname': 'level', 'name': 'logger'},
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['correlation_id'],
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
```

### Pattern 2: Sentry Automatic FastAPI Integration

**What:** Sentry SDK auto-detects FastAPI and captures errors, performance traces, and user context without explicit middleware.

**When to use:** Production error tracking with zero-configuration integration.

**Example:**
```python
# Source: https://docs.sentry.io/platforms/python/integrations/fastapi/
import sentry_sdk

sentry_sdk.init(
    dsn="https://...@sentry.io/...",
    # Performance monitoring
    traces_sample_rate=0.1,  # 10% of transactions (adjust for traffic)

    # Error tracking
    send_default_pii=True,  # Include user context (email, user_id)

    # Optional: Enable logging integration
    enable_logs=False,  # Keep False - logs go to Better Stack, not Sentry

    # Environment tagging
    environment="production",  # or "staging", "development"

    # Release tracking
    release="ra-tracker@1.0.0",  # Tag errors by version
)

# FastAPI integration is automatic - no middleware needed
app = FastAPI()
```

### Pattern 3: Database-Backed Scraper Health Tracking

**What:** Persist fetch cycle results (timestamp, duration, events_found, success/failure) to database table, enabling cross-worker visibility and historical trending.

**When to use:** Multi-worker deployments (gunicorn, Railway) where in-memory state is isolated per worker.

**Example:**
```python
# Database schema extension
CREATE TABLE IF NOT EXISTS scraper_fetch_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    events_found INTEGER,
    rules_processed INTEGER,
    status TEXT NOT NULL,  -- 'SUCCESS', 'FAILURE', 'PARTIAL'
    error_message TEXT,
    circuit_breaker_state TEXT
);

CREATE INDEX idx_scraper_fetch_started ON scraper_fetch_log(started_at DESC);

# Usage in fetch job
def fetch_and_notify():
    db = get_db()
    fetch_id = db.start_scraper_fetch()  # Insert row with started_at

    try:
        # ... fetch logic ...
        db.complete_scraper_fetch(fetch_id,
            events_found=len(events),
            rules_processed=len(rules),
            status='SUCCESS'
        )
        circuit_breaker.record_success()
    except Exception as e:
        db.complete_scraper_fetch(fetch_id,
            status='FAILURE',
            error_message=str(e)
        )
        circuit_breaker.record_failure({'error': str(e)})
        raise
```

### Pattern 4: Telegram Admin Alert with Rate Limiting

**What:** Send scraper failure alerts to admin via Telegram bot, with alert silencing after first notification and recovery message.

**When to use:** Critical system alerts that require human attention but shouldn't spam.

**Example:**
```python
# Source: https://github.com/python-telegram-bot/python-telegram-bot/wiki
from telegram import Bot
from datetime import datetime, timedelta

class ScraperAlerter:
    def __init__(self, bot_token: str, admin_chat_id: int):
        self.bot = Bot(token=bot_token)
        self.admin_chat_id = admin_chat_id
        self.alert_sent = False  # In-memory flag (could persist to DB)

    async def check_and_alert(self):
        """Check circuit breaker state and send alerts."""
        cb_status = circuit_breaker.get_status()

        # Alert on 3+ failures (circuit OPEN)
        if cb_status.state == 'OPEN' and not self.alert_sent:
            await self._send_alert(
                f"🚨 Scraper Failure Alert\n\n"
                f"Circuit breaker OPEN after {cb_status.failure_count} consecutive failures.\n"
                f"Last failure: {cb_status.last_failure.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Cooldown: {cb_status.cooldown_duration}s\n\n"
                f"Check /admin/scraper-status for details."
            )
            self.alert_sent = True

        # Recovery notification
        elif cb_status.state == 'CLOSED' and self.alert_sent:
            await self._send_alert(
                f"✅ Scraper Recovered\n\n"
                f"Circuit breaker CLOSED after {cb_status.error_count_since_success} failures.\n"
                f"System operating normally."
            )
            self.alert_sent = False

    async def _send_alert(self, message: str):
        """Send message without sound (non-urgent)."""
        await self.bot.send_message(
            chat_id=self.admin_chat_id,
            text=message,
            disable_notification=True,  # Silent notification
        )
```

### Anti-Patterns to Avoid

- **Logging PII to external services:** Never log email addresses, passwords, or session tokens to Better Stack. Use email hashes or user IDs only.
- **100% Sentry trace sampling in production:** Setting `traces_sample_rate=1.0` floods quota. Use 0.1-0.2 (10-20%) for production FastAPI apps.
- **structlog in FastAPI hybrid apps:** structlog has sync/async context variable isolation issues. Stick with python-json-logger + stdlib logging.
- **In-memory scraper state in gunicorn:** Workers don't share memory. Always persist health state to database for cross-worker visibility.
- **Repeating alerts without silencing:** Telegram rate limits ~30 messages/second. Implement alert cooldown to avoid flooding admin.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Request ID generation/validation | Custom UUID middleware | asgi-correlation-id | Handles UUID validation, header propagation, logging filter integration, and CORS exposure. Production-stable with 4+ years of use. |
| JSON log formatting | Manual json.dumps() in logging formatter | python-json-logger | Handles complex objects, exception serialization, timestamp formatting, and field renaming. Avoids edge cases like circular references. |
| Error grouping and deduplication | Database-backed error tracking | Sentry | Automatic stack trace fingerprinting, source map integration, release tracking, and user impact analysis. Free tier sufficient for most apps. |
| Log aggregation and search | Self-hosted ELK stack | Better Stack Logs | Avoids infrastructure overhead. 3GB free tier with SQL queries, live tail, and alerting. No Elasticsearch tuning or Logstash configuration. |

**Key insight:** Observability tooling is mature and commoditized. Building custom solutions for logging, error tracking, or alerting burns time on undifferentiated infrastructure. Use proven SaaS tools and invest effort in domain-specific monitoring (scraper health metrics, user behavior patterns).

## Common Pitfalls

### Pitfall 1: Request ID Not Propagating to Sentry

**What goes wrong:** Sentry captures errors but doesn't include the X-Request-ID, making cross-correlation with logs impossible.

**Why it happens:** Sentry SDK doesn't automatically read custom headers. Request ID must be explicitly bound to Sentry scope.

**How to avoid:** Use Sentry's before_send hook to inject request ID from asgi-correlation-id context:

```python
from asgi_correlation_id.context import correlation_id

def before_send(event, hint):
    """Inject request ID into Sentry events."""
    request_id = correlation_id.get()
    if request_id:
        event.setdefault('tags', {})['request_id'] = request_id
    return event

sentry_sdk.init(
    dsn="...",
    before_send=before_send,
)
```

**Warning signs:** Sentry errors lack request_id tag. Logs and errors can't be correlated for the same request.

### Pitfall 2: Logging Configuration Overridden by Uvicorn/Gunicorn

**What goes wrong:** Custom JSON logging works in dev but reverts to plain text in production (Railway/gunicorn).

**Why it happens:** Gunicorn and Uvicorn apply their own logging configs via `--log-config` flag, overriding application setup.

**How to avoid:** Disable Uvicorn's default logging and apply configuration at FastAPI startup:

```python
# In main.py or app.py startup
from logging.config import dictConfig

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure logging at app startup."""
    dictConfig(LOGGING_CONFIG)  # Apply before any logs
    yield

app = FastAPI(lifespan=lifespan)

# In gunicorn command, disable default logging:
# gunicorn --log-config-dict '{}' ra_tracker.web.app:app
```

**Warning signs:** JSON logs in `python -m ra_tracker.main` but plain text in `gunicorn`. Railway logs show default Uvicorn format.

### Pitfall 3: Scraper Alerts Spamming During Extended Outage

**What goes wrong:** Circuit breaker stays OPEN for hours, admin receives alert on every scheduler tick (e.g., every 15 minutes).

**Why it happens:** Alert logic checks circuit breaker state but doesn't track "already notified" state across fetch cycles.

**How to avoid:** Persist alert state to database, not in-memory:

```python
# Database table
CREATE TABLE scraper_alert_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    alert_sent BOOLEAN DEFAULT FALSE,
    alert_sent_at TIMESTAMP,
    CHECK (id = 1)  -- Singleton table
);

# Alert logic
def check_and_alert(db):
    state = db.get_scraper_alert_state()
    cb_status = circuit_breaker.get_status()

    if cb_status.state == 'OPEN' and not state.alert_sent:
        send_telegram_alert(...)
        db.set_scraper_alert_sent(True)
    elif cb_status.state == 'CLOSED' and state.alert_sent:
        send_recovery_notification(...)
        db.set_scraper_alert_sent(False)
```

**Warning signs:** Admin receives multiple identical alerts during single outage. Telegram bot rate limits kick in.

### Pitfall 4: Better Stack Handler Blocking Request Processing

**What goes wrong:** HTTP requests hang or timeout when Better Stack API is slow/unreachable.

**Why it happens:** LogtailHandler sends logs synchronously over HTTP. Network delays block the logging call, which blocks request handling.

**How to avoid:** Use QueueHandler + QueueListener for async log shipping:

```python
from logging.handlers import QueueHandler, QueueListener
from queue import Queue
from logtail import LogtailHandler

# Setup queue-based async logging
log_queue = Queue(-1)  # Unlimited size
queue_handler = QueueHandler(log_queue)

logtail_handler = LogtailHandler(source_token='...')

# Listener runs in background thread
queue_listener = QueueListener(
    log_queue,
    logtail_handler,
    respect_handler_level=True
)

# Apply to root logger
logging.root.addHandler(queue_handler)
queue_listener.start()

# On shutdown
atexit.register(queue_listener.stop)
```

**Warning signs:** Slow request times correlating with Better Stack API latency. Requests time out during Better Stack outages.

## Code Examples

Verified patterns from official sources:

### Complete Logging Setup with Request IDs

```python
# observability/logging_config.py
# Source: Combined from asgi-correlation-id and python-json-logger docs
import logging.config
from pythonjsonlogger import jsonlogger

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'correlation_id': {
            '()': 'asgi_correlation_id.CorrelationIdFilter',
            'uuid_length': 32,
            'default_value': '-',
        },
    },
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s %(user_id)s %(pathname)s %(lineno)d',
            'rename_fields': {
                'asctime': 'timestamp',
                'levelname': 'level',
                'name': 'logger',
                'correlation_id': 'request_id',
            },
        },
        'console': {  # Plain format for dev
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        },
    },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'filters': ['correlation_id'],
            'formatter': 'json',  # Use 'console' for dev
            'stream': 'ext://sys.stdout',
        },
    },
    'loggers': {
        'ra_tracker': {
            'handlers': ['stdout'],
            'level': 'INFO',
            'propagate': False,
        },
        'uvicorn.access': {
            'handlers': ['stdout'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['stdout'],
        'level': 'INFO',
    },
}

def setup_logging(environment: str = 'production'):
    """Configure logging based on environment."""
    config = LOGGING_CONFIG.copy()

    # Use console formatter in dev
    if environment == 'development':
        config['handlers']['stdout']['formatter'] = 'console'

    logging.config.dictConfig(config)
```

### Sentry Integration with User Context

```python
# observability/sentry_config.py
# Source: https://docs.sentry.io/platforms/python/integrations/fastapi/
import sentry_sdk
from asgi_correlation_id.context import correlation_id

def init_sentry(dsn: str, environment: str, release: str):
    """Initialize Sentry with FastAPI integration."""

    def before_send(event, hint):
        """Inject request ID and sanitize PII."""
        # Add request ID for log correlation
        request_id = correlation_id.get()
        if request_id:
            event.setdefault('tags', {})['request_id'] = request_id

        # Sanitize sensitive data
        if 'request' in event:
            headers = event['request'].get('headers', {})
            # Remove auth headers
            headers.pop('Authorization', None)
            headers.pop('Cookie', None)

        return event

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,

        # Performance monitoring (10% sample rate for production)
        traces_sample_rate=0.1,

        # Include user context
        send_default_pii=True,

        # Don't send logs to Sentry (use Better Stack instead)
        enable_logs=False,

        # Custom processing
        before_send=before_send,

        # Failed request tracking
        integrations=[
            # FastAPI integration is automatic
        ],
    )
```

### Adding User Context to Logs and Errors

```python
# Middleware to bind user context
# Source: FastAPI dependency injection + asgi-correlation-id patterns
from fastapi import Request, Depends
from asgi_correlation_id.context import correlation_id
import logging

async def bind_user_context(request: Request):
    """Bind user ID to request context for logging."""
    user = getattr(request.state, 'user', None)

    if user:
        # Add to Sentry scope
        sentry_sdk.set_user({
            'id': user.id,
            'email': user.email,
        })

        # Add to log context (requires structlog or custom filter)
        # For python-json-logger, use LoggerAdapter:
        logger = logging.LoggerAdapter(
            logging.getLogger(__name__),
            {'user_id': user.id, 'request_id': correlation_id.get()}
        )
        request.state.logger = logger

    return user

# Use in routes
@app.get("/dashboard")
async def dashboard(user = Depends(bind_user_context)):
    logger = getattr(request.state, 'logger', logging.getLogger(__name__))
    logger.info("Dashboard accessed")  # Includes user_id and request_id
```

### Dashboard Metrics Query Patterns

```python
# Database queries for scraper health dashboard
# Based on existing scraper_health_log and circuit_breaker patterns

class Database:
    def get_scraper_health_summary(self, days: int = 7):
        """Get scraper health metrics for dashboard."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                WITH recent_fetches AS (
                    SELECT
                        started_at,
                        completed_at,
                        EXTRACT(EPOCH FROM (completed_at - started_at)) as duration,
                        events_found,
                        status,
                        error_message
                    FROM scraper_fetch_log
                    WHERE started_at > NOW() - INTERVAL '{days} days'
                    ORDER BY started_at DESC
                )
                SELECT
                    COUNT(*) as total_fetches,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'FAILURE' THEN 1 ELSE 0 END) as failed,
                    ROUND(AVG(duration), 2) as avg_duration_seconds,
                    SUM(events_found) as total_events_found,
                    MAX(started_at) as last_fetch_time
                FROM recent_fetches
            """)

            return dict(cursor.fetchone())

    def get_recent_fetch_history(self, limit: int = 20):
        """Get recent fetch cycles for timeline display."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT
                    started_at,
                    completed_at,
                    EXTRACT(EPOCH FROM (completed_at - started_at)) as duration,
                    events_found,
                    rules_processed,
                    status,
                    error_message,
                    circuit_breaker_state
                FROM scraper_fetch_log
                ORDER BY started_at DESC
                LIMIT {limit}
            """)

            return [dict(row) for row in cursor.fetchall()]

    def get_fetch_success_rate_trend(self, days: int = 7):
        """Calculate daily success rate trend."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT
                    DATE(started_at) as date,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
                    ROUND(
                        100.0 * SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) / COUNT(*),
                        1
                    ) as success_rate
                FROM scraper_fetch_log
                WHERE started_at > NOW() - INTERVAL '{days} days'
                GROUP BY DATE(started_at)
                ORDER BY date DESC
            """)

            return [dict(row) for row in cursor.fetchall()]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ELK stack self-hosted | SaaS log aggregation (Better Stack, Datadog) | 2020-2022 | Eliminated infrastructure overhead. Free tiers sufficient for small-medium apps. SQL-based querying replaced Lucene DSL. |
| Sentry on-premise | Sentry SaaS free tier | 2019+ | Free tier (5K errors/month) covers most indie/small team apps. Official SDKs auto-integrate with frameworks. |
| Manual request tracing | ASGI correlation ID middleware | 2020+ | Zero-config UUID propagation across logs, errors, and distributed traces. Standard X-Request-ID header convention. |
| Plain text logs | Structured JSON logging | 2018+ | Machine-parseable logs enable aggregation, filtering, and alerting. JSON is de-facto standard for cloud-native apps. |
| Prometheus + Grafana | Application-level health dashboards | Ongoing | For simple apps, database-backed health metrics + HTML dashboard cheaper than Prometheus infrastructure. |

**Deprecated/outdated:**
- **Logstash for log shipping:** Replaced by language-native handlers (logtail-python, winston for Node, etc.). Logstash config complexity eliminated.
- **Rollbar for error tracking:** Still viable but Sentry has better free tier and FastAPI auto-integration. Market consolidation favors Sentry.
- **Statsd + Graphite:** Replaced by Prometheus (for metrics-heavy apps) or application-level metrics (for simple apps). Graphite maintenance burden too high.
- **100% trace sampling:** Sentry blog (Feb 2026) recommends strategic sampling (10-20% baseline, 100% for critical paths) to avoid quota waste.

## Open Questions

1. **Better Stack vs Railway native logs for retention**
   - What we know: Railway retains logs for limited time (hours/days), Better Stack free tier offers 3 days retention + 3GB/month
   - What's unclear: Whether Railway's native log viewer is sufficient for quick debugging, or if Better Stack's SQL queries justify integration overhead
   - Recommendation: Start with Better Stack for structured logging. Railway logs are plain text and non-queryable. Better Stack's SQL interface enables filtering by user_id, request_id, or error type.

2. **Scraper errors in Sentry vs separate tracking**
   - What we know: Sentry groups errors by stack trace. Scraper errors are operational (IP blocks, rate limits) not code bugs.
   - What's unclear: Whether scraper operational errors should go to Sentry or stay in database-only logging
   - Recommendation: Keep scraper errors in database (existing scraper_health_log table) for operational visibility. Only send to Sentry if exception is unhandled (e.g., unexpected HTTP status code). This avoids Sentry quota burn on expected operational errors.

3. **Alert delivery: Telegram vs email for admin**
   - What we know: User decision is Telegram-only for alerts. Email requires BREVO_API_KEY configuration.
   - What's unclear: Whether admin has Telegram bot linked or prefers email
   - Recommendation: Implement Telegram alerts per user decision. Optionally add email fallback if Telegram send fails (using existing email_sender.py infrastructure).

4. **Log volume and Better Stack quota management**
   - What we know: 3GB free tier, ~$0.10/GB after. Gunicorn workers multiply log volume (4 workers = 4x logs).
   - What's unclear: Actual log volume in production with JSON format + all request logs
   - Recommendation: Start with INFO level logging, excluding uvicorn.access logs from Better Stack (keep in Railway stdout only). Monitor Better Stack usage in first week and adjust log levels if approaching 3GB/month.

## Sources

### Primary (HIGH confidence)

- [Sentry FastAPI Integration](https://docs.sentry.io/platforms/python/integrations/fastapi/) - Official Sentry documentation
- [asgi-correlation-id GitHub](https://github.com/snok/asgi-correlation-id) - Production-stable middleware (4.3.4)
- [asgi-correlation-id PyPI](https://pypi.org/project/asgi-correlation-id/) - Version and configuration details
- [structlog Context Variables](https://www.structlog.org/en/stable/contextvars.html) - Official docs on sync/async isolation
- [Better Stack Python Logging](https://betterstack.com/docs/logs/python/) - Official integration guide
- [Sentry Sampling Configuration](https://docs.sentry.io/platforms/python/configuration/sampling/) - Official sampling docs

### Secondary (MEDIUM confidence)

- [How to Add Structured Logging to FastAPI](https://oneuptime.com/blog/post/2026-02-02-fastapi-structured-logging/view) - Feb 2026 best practices
- [Production-Grade Logging for FastAPI Applications](https://medium.com/@laxsuryavanshi.dev/production-grade-logging-for-fastapi-applications-a-complete-guide-f384d4b8f43b) - Feb 2026 comprehensive guide
- [Setting up request ID logging for your FastAPI application](https://medium.com/@sondrelg_12432/setting-up-request-id-logging-for-your-fastapi-application-4dc190aac0ea) - asgi-correlation-id author's guide
- [Better Stack Pricing](https://betterstack.com/pricing) - Official pricing page (3GB free tier confirmed)
- [Sentry Pricing Comprehensive Guide 2025](https://www.baytechconsulting.com/blog/sentry-io-comprehensive-guide-2025) - Free tier details (5K errors/month)
- [Watching everything is watching nothing: Sampling strategy for Sentry](https://blog.sentry.io/sampling-strategy-sentry/) - Feb 2, 2026 Sentry blog on strategic sampling
- [Sharing data across workers in a Gunicorn + Flask application](https://medium.com/@jgleeee/sharing-data-across-workers-in-a-gunicorn-flask-application-2ad698591875) - Gunicorn worker isolation patterns
- [Python Telegram bot design patterns](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-requested-design-patterns) - Official wiki
- [10 Best SolarWinds Papertrail Alternatives in 2026](https://betterstack.com/community/comparisons/papertrail-alternatives/) - Log aggregation comparison

### Tertiary (LOW confidence)

- [Logging in Python: A Comparison of the Top 6 Libraries](https://betterstack.com/community/guides/logging/best-python-logging-libraries/) - Library comparison survey
- [Circuit Breaker Pattern monitoring best practices](https://medium.com/@ragigeo/implementing-and-monitoring-circuit-breaker-retry-and-rate-limiter-with-spring-boot-ebd6b6554c51) - Metrics guidance (Java-focused but patterns apply)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are production-stable with official FastAPI integration docs
- Architecture: HIGH - Patterns verified from official sources and existing codebase (circuit_breaker.py, telegram_bot.py)
- Pitfalls: MEDIUM-HIGH - Based on documented issues in GitHub discussions and community guides, plus analysis of gunicorn worker isolation
- Log service selection: MEDIUM - Better Stack chosen based on free tier comparison, but Papertrail/Datadog viable alternatives

**Research date:** 2026-02-19
**Valid until:** 2026-04-19 (60 days - observability tooling relatively stable)

**Key assumptions:**
- Railway deployment with gunicorn multi-worker setup (confirmed in prior decisions)
- Single admin user (Sentry free tier 1-user limit acceptable)
- Low-moderate traffic (3GB/month log volume, 5K errors/month sufficient)
- PostgreSQL database available (confirmed in Phase 12 decisions)
- Existing Telegram bot infrastructure functional (confirmed in telegram_bot.py)
