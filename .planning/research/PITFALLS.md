# Pitfalls Research: Production Deployment for FastAPI Scraper

**Domain:** Python FastAPI scraper application (GraphQL API client + APScheduler + multi-tenant)
**Researched:** 2026-02-11
**Confidence:** MEDIUM (based on training data and codebase analysis; web research unavailable)

## Critical Pitfalls

### Pitfall 1: APScheduler Runs in Every Worker Process

**What goes wrong:**
When deploying FastAPI with gunicorn/uvicorn workers, APScheduler starts in EVERY worker process. If you run `gunicorn -w 4`, you get 4 schedulers all executing the same cron jobs simultaneously. For a scraper, this means:
- 4x the API requests to ra.co (rate limit violations)
- 4x duplicate notifications sent to users
- Database race conditions as multiple workers try to update the same events

**Why it happens:**
The current architecture (main.py line 114-116) starts the scheduler unconditionally during startup. Each gunicorn worker runs the entire FastAPI application startup, including `start_scheduler()`. Developers assume scheduler is "global" but it's actually per-process.

**How to avoid:**
**Option A (Recommended):** Single-worker scheduler process
- Deploy scheduler and web server as SEPARATE processes
- Use `--no-scheduler` flag for web workers: `gunicorn -w 4 --bind 0.0.0.0:8080`
- Run ONE dedicated scheduler process: `python -m ra_tracker.main --no-web` (requires adding this flag)
- Or use systemd/supervisor to run `python -c "from ra_tracker.scheduler.jobs import start_scheduler; start_scheduler(); import time; time.sleep(float('inf'))"`

**Option B:** Worker ID detection (fragile)
- Use environment variable to designate one worker: `WORKER_ID=1 gunicorn ...`
- Only start scheduler if `os.getenv('WORKER_ID') == '1'`
- Problem: Worker crashes mean scheduler stops, requires manual intervention

**Option C:** External scheduler (production-grade)
- Use celery beat or system cron to trigger `curl http://localhost:8080/api/admin/fetch-now`
- Requires adding authenticated admin endpoint for triggering fetches
- More infrastructure but more reliable

**Warning signs:**
- Logs show "Scheduled fetch job" message appearing 4x at startup
- Telegram receives 4x duplicate notifications
- Database shows 4x event count spikes at fetch intervals
- ra.co API returns 429 Too Many Requests

**Phase to address:**
Phase 1 (Production Infrastructure Setup) - Must be resolved before multi-worker deployment

---

### Pitfall 2: SQLite Database Locking Under Multi-Worker Load

**What goes wrong:**
SQLite uses file-level locking. Under production load with multiple workers:
- Concurrent writes cause "database is locked" errors (timeout after 5 seconds default)
- User registration, rule changes, and fetch operations fail intermittently
- Workers retry, causing cascading failures
- No connection pooling means each request opens/closes connections (slow)

Current code (database.py) uses context managers opening connections per-operation. Under load:
```
Worker 1: Starts fetch, writes to events table (EXCLUSIVE lock)
Worker 2: User adds rule (waits for lock)
Worker 3: User loads dashboard (waits for lock)
Worker 4: Another user adds rule (times out after 5s)
```

**Why it happens:**
SQLite is designed for single-process applications. The WAL mode helps but doesn't eliminate lock contention with writes. Developers choose SQLite for dev simplicity, forget production concurrency constraints.

**How to avoid:**
**Migration to PostgreSQL (required for production):**
- Replace sqlite3 with psycopg2 or asyncpg
- Add connection pooling (SQLAlchemy recommended for FastAPI)
- Update all raw SQL queries for PostgreSQL compatibility (see Pitfall 3)

**Warning signs:**
- "OperationalError: database is locked" in production logs
- 5-second request timeouts during fetch operations
- User actions fail with 500 errors when scheduler is running
- Increasing error rate as user count grows

**Phase to address:**
Phase 1 (Production Infrastructure Setup) - PostgreSQL migration is prerequisite for multi-worker deployment

---

### Pitfall 3: Silent SQL Syntax Failures After PostgreSQL Migration

**What goes wrong:**
SQLite is permissive, PostgreSQL is strict. Queries that work in development fail or produce wrong results in production:

**Type coercion failures:**
```python
# database.py uses raw queries with type mismatches
# SQLite: INTEGER and BOOLEAN are aliases (both stored as integers)
# PostgreSQL: Strict typing, requires explicit BOOLEAN type

# This works in SQLite, fails in PostgreSQL:
cursor.execute("INSERT INTO rules (is_active) VALUES (1)")  # expects TRUE/FALSE
```

**Date/time handling:**
```python
# SQLite stores datetimes as TEXT, returns strings
# PostgreSQL has native DATETIME type, returns datetime objects

# Current code may break if assuming string comparison:
cursor.execute("SELECT * FROM events WHERE date >= ?", (date.today(),))
# SQLite: Compares strings "2026-02-11" >= "2026-01-01" (works)
# PostgreSQL: Requires date object comparison
```

**AUTOINCREMENT differences:**
```python
# SQLite: AUTOINCREMENT is optional, INTEGER PRIMARY KEY auto-increments
# PostgreSQL: Requires SERIAL or GENERATED ALWAYS AS IDENTITY

# Current schema (database.py line 24):
# "id INTEGER PRIMARY KEY AUTOINCREMENT"
# Must become: "id SERIAL PRIMARY KEY" or "id INTEGER GENERATED ALWAYS AS IDENTITY"
```

**Parameter placeholders:**
```python
# SQLite uses ? placeholders
# PostgreSQL (psycopg2) uses %s placeholders

# Every query in database.py needs updating:
cursor.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))  # SQLite
cursor.execute("SELECT * FROM rules WHERE id = %s", (rule_id,))  # PostgreSQL
```

**Boolean representation:**
```python
# SQLite: Stores booleans as 0/1 integers
# PostgreSQL: Has native BOOLEAN, stores as TRUE/FALSE

# Queries like this break:
cursor.execute("SELECT * FROM rules WHERE is_active = 1")  # Works in SQLite
cursor.execute("SELECT * FROM rules WHERE is_active = TRUE")  # Required for PostgreSQL
```

**Why it happens:**
SQLite's type affinity vs. PostgreSQL's strict typing. Developers test with SQLite, assume production will "just work". Migration scripts convert schema but not application code.

**How to avoid:**
1. **Use SQLAlchemy ORM or query builder (strongly recommended)**
   - Abstracts database differences
   - Handles parameter placeholders automatically
   - Type safety prevents common errors

2. **If keeping raw SQL:**
   - Replace ALL `?` placeholders with `%s`
   - Update schema: INTEGER AUTOINCREMENT → SERIAL
   - Add explicit type casts: `is_active = TRUE` not `= 1`
   - Test EVERY query against PostgreSQL before deployment

3. **Schema migration checklist:**
   - AUTOINCREMENT → SERIAL or IDENTITY
   - DATETIME DEFAULT CURRENT_TIMESTAMP → DEFAULT NOW()
   - INTEGER booleans → BOOLEAN with TRUE/FALSE defaults
   - TEXT → VARCHAR(n) where length limits make sense

4. **Add integration tests:**
   - Run test suite against PostgreSQL, not just SQLite
   - Use database.py test fixtures with both backends
   - Catch query incompatibilities before production

**Warning signs:**
- Different query results between dev and production
- Type errors like "column 'is_active' is of type boolean but expression is of type integer"
- Foreign key constraint failures (PostgreSQL enforces, SQLite ignores by default)
- INSERT statements succeed but return no ID
- Silent data truncation (PostgreSQL errors on overflow, SQLite coerces)

**Phase to address:**
Phase 1 (Production Infrastructure Setup) - Part of PostgreSQL migration task, must have verification checklist

---

### Pitfall 4: Scraper Blocked by Cloud Provider IP Reputation

**What goes wrong:**
ra.co (like most public sites) tracks request patterns and IP reputation. Cloud provider IP ranges (AWS, GCP, Azure, Digital Ocean) are flagged as "data center traffic" and treated differently than residential IPs:
- Requests from cloud IPs hit stricter rate limits
- May require JavaScript challenges (breaks requests.Session)
- Return 403 Forbidden or 429 Too Many Requests more aggressively
- CAPTCHA challenges that GraphQL client can't solve

**Current risk analysis:**
- ra_client.py uses basic User-Agent spoofing (line 85)
- 1 second rate limiting between requests (line 14)
- No retry logic or exponential backoff
- No IP rotation or proxy support
- Single requests.Session per RAClient instance

When deployed to cloud hosting, ra.co may:
1. Detect data center IP via WHOIS/ASN lookup
2. Apply stricter rate limiting (e.g., 1 req/10s instead of 1 req/1s)
3. Require JavaScript challenge before GraphQL endpoint access
4. Block IP entirely after repeated requests

**Why it happens:**
Scraping from residential IPs (dev laptop) looks like normal user traffic. Cloud IPs are associated with bots, scrapers, and abuse. Site operators preemptively block or rate-limit data center ASNs.

**How to avoid:**
**Detection strategy:**
1. Add response monitoring in ra_client.py:
   ```python
   def _execute(self, query, variables):
       response = self.session.post(...)

       # Detect blocking
       if response.status_code == 403:
           logger.error("403 Forbidden - possible IP block")
       elif response.status_code == 429:
           logger.error("429 Rate Limited - backoff required")
       elif 'captcha' in response.text.lower():
           logger.error("CAPTCHA challenge detected")
       elif response.status_code == 200 and 'data' not in response.json():
           logger.error("GraphQL returned empty data - possible soft block")
   ```

2. Add health check endpoint:
   - `/api/scraper/health` tests ra.co reachability
   - Returns last successful fetch time, error count
   - Alerts if blocking detected

**Mitigation options (in priority order):**

**Option A: Respect rate limits and reduce frequency (least risky)**
- Increase MIN_REQUEST_INTERVAL from 1.0s to 2.0s or 5.0s
- Reduce fetch_interval_hours from 6 to 12 or 24
- Monitor for 429s and back off exponentially
- Most cloud IPs work fine with conservative rate limiting

**Option B: Residential proxy service (moderate cost/complexity)**
- Services like Bright Data, Smartproxy provide residential IP rotation
- Appears as normal user traffic
- Cost: ~$500-1000/month for moderate use
- Legal concern: May violate ra.co ToS (check terms)

**Option C: Deploy on residential ISP (VPS with residential IP)**
- Rent VPS from providers with residential IP pools
- Harder to find, more expensive than cloud providers
- Example: Some European/Asian providers offer residential IPs

**Option D: Hybrid approach (recommended for this project)**
- Start with conservative rate limiting (Option A)
- Add monitoring to detect blocking (status codes, response patterns)
- If blocking occurs, add exponential backoff (double delay after each 429)
- Only escalate to proxies if rate limiting alone fails

**Warning signs:**
- Sudden increase in GraphQL errors after cloud deployment
- 403/429 status codes in production (worked fine in dev)
- Empty responses despite 200 status code
- Fetch operations succeed but return 0 events (soft block)
- Logs show "GraphQL errors: [...]" with authentication/permission errors

**Phase to address:**
Phase 1 (Production Infrastructure Setup) - Add detection monitoring
Phase 2 (Scraper Resilience) - Implement retry logic, exponential backoff, proxy support if needed

---

### Pitfall 5: Secrets Exposed in Version Control or Logs

**What goes wrong:**
Current config.yaml (line 3, 9-10, 22-23) contains PRODUCTION SECRETS in plaintext:
```yaml
secret_key: 3w--7yyBz4Mw3ZS3nvg0rYzdi_abAqmpmO1tIY5bqlk  # Session signing key
email.password: xsmtpsib-e6658e60cfd86c58442621688311e2fe2d7385da3a6e8d099dd672e14c87720a-IRMU3EyJmygtG2Qf
telegram.bot_token: 8200624905:AAFcNY1sdCHpakoVbeJBh6PQvFon3xfxxac
```

These secrets are:
1. **Committed to git** (config.yaml tracked, not .gitignored)
2. **Exposed in GitHub** if repo is public or ever made public
3. **Readable by anyone with access** to production server filesystem
4. **Logged in error traces** if config loading fails

Attack scenarios:
- Stolen bot_token → attacker sends spam as your bot
- Stolen email.password → attacker sends phishing emails from your domain
- Stolen secret_key → attacker forges session cookies, gains admin access

**Why it happens:**
Developers hard-code for local dev convenience, forget to externalize before pushing. .env pattern exists (main.py line 84) but config.yaml takes precedence. No enforcement that secrets MUST come from environment.

**How to avoid:**
**Immediate (before ANY cloud deployment):**
1. **Move ALL secrets to .env file:**
   ```bash
   # .env (NEVER commit this file)
   SECRET_KEY=3w--7yyBz4Mw3ZS3nvg0rYzdi_abAqmpmO1tIY5bqlk
   EMAIL_PASSWORD=xsmtpsib-e6658e60cfd86c58442621688311e2fe2d7385da3a6e8d099dd672e14c87720a-IRMU3EyJmygtG2Qf
   TELEGRAM_BOT_TOKEN=8200624905:AAFcNY1sdCHpakoVbeJBh6PQvFon3xfxxac
   TELEGRAM_CHAT_ID=769647676
   DATABASE_URL=postgresql://user:pass@localhost/ratracker
   ```

2. **Update config.yaml to use placeholders or remove secrets entirely:**
   ```yaml
   app:
     secret_key: ${SECRET_KEY}  # Read from environment
   email:
     password: ${EMAIL_PASSWORD}
   telegram:
     bot_token: ${TELEGRAM_BOT_TOKEN}
   ```

3. **Add .env to .gitignore:**
   ```gitignore
   .env
   .env.*
   !.env.example
   ```

4. **Create .env.example for documentation:**
   ```bash
   # .env.example (safe to commit)
   SECRET_KEY=generate-with-secrets-token-urlsafe-32
   EMAIL_PASSWORD=your-smtp-password
   TELEGRAM_BOT_TOKEN=your-bot-token
   ```

5. **Rotate ALL exposed secrets immediately:**
   - Generate new secret_key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - Regenerate Telegram bot token via BotFather
   - Change email SMTP password
   - Invalidate all existing user sessions (old secret_key won't validate)

**Production deployment:**
- Use cloud provider secret management (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault)
- Inject as environment variables at runtime
- Never store secrets in container images or config files

**Log safety:**
- Add log filtering to prevent secret leakage:
  ```python
  class SecretFilter(logging.Filter):
      def filter(self, record):
          # Redact common secret patterns
          record.msg = re.sub(r'(password|token|key)=\S+', r'\1=***', str(record.msg))
          return True
  ```
- Don't log full config object
- Use structured logging with explicit field inclusion (not dict dumps)

**Warning signs:**
- Secrets visible in GitHub repo history
- Container images contain .env files
- CloudWatch/StackDriver logs show tokens in error traces
- Security scanners flag exposed credentials
- Unexpected API usage (stolen bot token used elsewhere)

**Phase to address:**
Phase 0 (Pre-deployment) - MUST be fixed before ANY code reaches cloud hosting
Phase 1 - Implement cloud secret management

---

### Pitfall 6: No Health Check Endpoint (Kubernetes/LB Routing Failures)

**What goes wrong:**
Production deployments use load balancers, Kubernetes liveness probes, or uptime monitors. Without a health check endpoint:
- Load balancer can't determine if instance is healthy
- Sends traffic to crashed/degraded instances
- No automated recovery from database connection failures
- Can't distinguish "server starting" from "server broken"

Common failure scenario:
1. Deploy new version
2. Database migration runs, takes 30 seconds
3. Load balancer sends traffic immediately (no /health endpoint)
4. Requests fail with "database not initialized" errors
5. Users see 500 errors during deployment

Or:
1. PostgreSQL connection pool exhausted
2. App still responds to HTTP but all DB queries fail
3. Load balancer thinks instance is healthy (HTTP 200 on /)
4. Users get "database unavailable" errors
5. Manual intervention required to detect and restart

**Why it happens:**
FastAPI serves web UI but has no dedicated health endpoint. Load balancers check TCP port 8080 (returns 200 even if app is broken) or check `/` (requires database for dashboard rendering).

**How to avoid:**
Add dedicated health check endpoint:

```python
# web/app.py
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring.

    Returns:
        200 OK: Service is healthy (can connect to database)
        503 Service Unavailable: Database connection failed
    """
    try:
        # Verify database connectivity
        db = get_db()
        db.conn.execute("SELECT 1")

        # Verify scheduler is running (if expected)
        from ..scheduler.jobs import get_scheduler
        scheduler = get_scheduler()
        scheduler_ok = scheduler.running

        return {
            "status": "healthy",
            "database": "ok",
            "scheduler": "running" if scheduler_ok else "stopped",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes - only ready after startup tasks complete."""
    # Check if database schema is initialized
    # Check if required config is loaded
    # Return 200 only when truly ready to serve traffic
    pass
```

**Kubernetes/Docker Compose configuration:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 30
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
```

**Warning signs:**
- Load balancer sends traffic before app is ready
- Automated restarts don't occur when app is degraded
- Monitoring shows instance "up" but users report errors
- Database connection failures don't trigger instance replacement

**Phase to address:**
Phase 1 (Production Infrastructure Setup) - Required before load balancer/orchestrator deployment

---

### Pitfall 7: No Graceful Shutdown (In-Flight Requests Lost)

**What goes wrong:**
Current signal handlers (main.py line 35-39) call `sys.exit(0)` immediately:
```python
def signal_handler(signum, frame):
    logger.info("Shutdown signal received, stopping...")
    stop_scheduler()
    sys.exit(0)  # PROBLEM: Exits immediately
```

On deployment rollout (Kubernetes, Docker, systemd restart):
1. SIGTERM sent to process
2. signal_handler stops scheduler
3. sys.exit(0) terminates immediately
4. In-flight HTTP requests aborted mid-processing
5. Users see "connection reset" errors
6. Fetch operation interrupted, partial data in database

**Why it happens:**
Developers focus on graceful scheduler shutdown but forget web server shutdown. uvicorn.run() has built-in graceful shutdown but signal_handler bypasses it.

**How to avoid:**
**Remove manual signal handlers, let uvicorn handle shutdown:**
```python
def main():
    # Remove these:
    # signal.signal(signal.SIGINT, signal_handler)
    # signal.signal(signal.SIGTERM, signal_handler)

    # Add lifespan event handler instead:
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        start_scheduler()
        yield
        # Shutdown - called AFTER uvicorn finishes in-flight requests
        stop_scheduler()
        logger.info("Graceful shutdown complete")

    # Use in FastAPI app:
    app = FastAPI(lifespan=lifespan)
```

**Or keep signal handlers but don't exit immediately:**
```python
def signal_handler(signum, frame):
    logger.info("Shutdown signal received")
    stop_scheduler()
    # Don't call sys.exit() - let uvicorn finish gracefully
```

**Configure uvicorn timeout:**
```python
uvicorn.run(
    "ra_tracker.web.app:app",
    host=config.web.host,
    port=config.web.port,
    timeout_graceful_shutdown=30,  # Wait up to 30s for requests to complete
)
```

**Kubernetes deployment config:**
```yaml
spec:
  terminationGracePeriodSeconds: 60  # Must be > uvicorn timeout
  containers:
  - name: ra-tracker
    lifecycle:
      preStop:
        exec:
          command: ["/bin/sh", "-c", "sleep 5"]  # Delay before SIGTERM
```

**Warning signs:**
- "Connection reset by peer" errors during deployments
- Users report "something went wrong" mid-action
- Database shows partial/incomplete data after restarts
- Logs show "Scheduler stopped" but no "requests completed" message

**Phase to address:**
Phase 1 (Production Infrastructure Setup) - Part of deployment configuration

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep SQLite in production | No migration work, faster initial deploy | Database locking under load, data loss risk, can't scale past 1-2 workers | Never for multi-user production. Only acceptable for single-user self-hosted deployment |
| Run scheduler in web worker | Simple architecture, no separate processes | Duplicate jobs in multi-worker setup, race conditions | Only in development or single-worker production (not scalable) |
| Use raw SQL instead of ORM | More control, no ORM learning curve | Every query needs manual PostgreSQL migration, SQL injection risk, no type safety | Acceptable if team is SQL-expert and adds comprehensive integration tests |
| Hard-code secrets in config.yaml | Faster setup, no .env file management | Security breach if repo exposed, can't rotate secrets without code changes | Never acceptable. Always use environment variables or secret management |
| Skip health check endpoint | One less endpoint to maintain | Load balancers can't detect failures, no automated recovery, manual restarts required | Never for load-balanced deployments. Only acceptable for single-instance hobby projects |
| No exponential backoff on API errors | Simpler error handling | Rate limit violations, IP blocks, service degradation | Never for scrapers. Always implement backoff for external API calls |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| PostgreSQL connection pooling | Creating new connection per request (like current SQLite pattern) | Use SQLAlchemy with connection pooling: `create_engine(..., pool_size=10, max_overflow=20)` |
| Gunicorn + uvicorn workers | Using `gunicorn app:app` directly (creates sync workers) | Use uvicorn worker class: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app` |
| ra.co GraphQL API | Assuming residential rate limits apply in cloud | Add monitoring for 403/429 responses, implement exponential backoff, reduce request frequency |
| Telegram bot webhooks | Switching to webhooks without HTTPS/domain | Webhooks require public HTTPS endpoint. For polling mode, stick with `use_webhook: false` in production |
| Email via Brevo SMTP | Using same credentials across dev/prod environments | Separate Brevo accounts or API keys for dev/staging/prod to prevent accidental test emails to real users |
| APScheduler persistence | Using in-memory job store (lost on restart) | Use SQLAlchemy or Redis jobstore for persistence: `scheduler = BackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(...)})` |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading all events for dashboard | Works with 100 events, becomes slow | Add pagination, limit queries to date range (next 30 days), add database indexes | 1000+ events in database, dashboard takes 5+ seconds to load |
| No database connection pooling | First request slow, subsequent requests fast | Use SQLAlchemy with connection pooling, configure pool size based on worker count | 10+ concurrent users, connection overhead dominates |
| Fetching all rules in single scheduler run | Acceptable with 5 rules | Add batching, process rules in chunks, add timeout per rule to prevent one slow rule from blocking others | 100+ active rules, fetch takes 30+ minutes, blocks next scheduled run |
| Storing full event JSON in notifications table | Convenient for debugging | Store only event_id and rule_id, join to events table when needed | 10,000+ notifications, database size balloons, queries slow down |
| No index on events.date | Works fine with small dataset | Add index: `CREATE INDEX idx_events_date ON events(date)` | 5000+ events, dashboard filtering by date becomes slow |
| Synchronous HTTP requests in scheduler | Simple code, works for few rules | Use async httpx or parallel processing for multiple rules | 50+ rules, fetch takes 5+ minutes (1s * 50 rules + overhead) |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Exposing admin endpoints without authentication | Attackers can trigger fetch jobs, spam notifications, exhaust API rate limits | Add authentication middleware to all /api/admin/* endpoints, use API key or admin session check |
| Telegram chat_id in public config | Anyone can send notifications to your chat | Move chat_id to environment variables, validate webhook requests with secret token |
| No rate limiting on user actions | Users can spam rule creation, trigger excessive API calls to ra.co | Add rate limiting on rule creation (max 10 rules per user), add cooldown on manual fetch triggers |
| Session cookies without secure flags | Session hijacking via MITM attacks | Ensure `session.secure_cookies: true` enforced in production (config.yaml line 19), add `httponly=True, samesite='lax'` |
| SQL injection in raw queries | If any user input reaches SQL without parameterization | Use parameterized queries ALWAYS (current code does this correctly), add SQLAlchemy ORM as safer alternative |
| Logging full user objects | Passwords, email addresses in logs | Implement log filtering, never log password_hash field, use user.id not user.email in logs |
| No CSRF protection on state-changing endpoints | Attackers trick users into creating rules, deleting accounts | Current CSRF implementation (csrf.py) is good, ensure applied to ALL POST/PUT/DELETE endpoints |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No feedback when scraper is blocked | Users think app is broken, assume rules don't work | Show scraper health status on dashboard: "Last successful fetch: 2 hours ago (Warning: API rate limited)" |
| Fetch errors fail silently | Users don't know their notifications stopped working | Send email/Telegram alert when 3+ consecutive fetches fail: "Your rave tracker hasn't updated in 24 hours - check scraper status" |
| No indication of why no events found | User adds artist rule, sees no events, thinks it's broken | Show per-rule status: "Artist 'Amelie Lens' - Last fetch: 5 min ago, 0 events found (No upcoming shows)" vs "Fetch failed: API error" |
| Production deployment breaks notifications, no user alert | Users miss events because notifications stopped | Add health check page visible to users: /status shows scheduler running, last fetch time, error count |
| Deploying with IP block, no fallback | All fetches fail, no events for anyone | Implement graceful degradation: If 3+ fetches fail, reduce frequency to 1x/day and alert admin |
| No migration communication when moving to PostgreSQL | Users experience downtime without warning | Show maintenance banner 24h before: "We're upgrading the database on [date]. Service will be unavailable for ~30 minutes." |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **PostgreSQL migration:** Schema converted, but queries still use SQLite syntax (`?` placeholders, INTEGER booleans) - verify ALL queries tested against PostgreSQL
- [ ] **Multi-worker deployment:** Gunicorn runs with 4 workers, but scheduler runs in all 4 (4x duplicate jobs) - verify single scheduler process OR worker ID detection
- [ ] **Secret management:** Secrets moved to .env, but old secrets not rotated - verify ALL secrets regenerated before production deploy
- [ ] **Health check endpoint:** /health endpoint exists, but doesn't actually test database connection - verify health check includes DB query
- [ ] **Graceful shutdown:** Signal handlers call stop_scheduler(), but uvicorn exits immediately - verify timeout_graceful_shutdown configured
- [ ] **Error monitoring:** Logs show errors, but no alerting configured - verify Sentry/CloudWatch alarms trigger on error spikes
- [ ] **Database backups:** PostgreSQL running in production, but no backup schedule - verify automated daily backups configured
- [ ] **IP blocking detection:** Scraper code has retry logic, but doesn't detect 403/429 from ra.co - verify response status monitoring and exponential backoff
- [ ] **Connection pooling:** SQLAlchemy installed, but still using raw sqlite3.connect() pattern - verify connection pool configured with max_overflow

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| APScheduler duplicates in multi-worker | LOW | 1. Stop all workers. 2. Clear duplicate jobs: delete from apscheduler_jobs. 3. Restart with single scheduler process using --no-scheduler flag for web workers |
| SQLite database locked | MEDIUM | 1. Stop all workers. 2. Enable WAL mode: PRAGMA journal_mode=WAL. 3. Restart with single worker OR migrate to PostgreSQL immediately |
| Secrets exposed in git history | HIGH | 1. Rotate ALL secrets immediately. 2. Invalidate all user sessions. 3. Use BFG Repo-Cleaner to scrub git history. 4. Force-push cleaned history (breaks forks). 5. Add pre-commit hooks to prevent future leaks |
| IP blocked by ra.co | MEDIUM | 1. Stop scheduler to prevent further requests. 2. Wait 24-48 hours for auto-unblock. 3. Implement exponential backoff. 4. Reduce fetch frequency to 1x/day. 5. Consider residential proxy service |
| PostgreSQL migration data type errors | MEDIUM | 1. Rollback to SQLite backup. 2. Fix all query syntax issues locally. 3. Test migration on staging environment. 4. Re-run migration with verified queries |
| Graceful shutdown not working | LOW | 1. Update deployment to use SIGTERM with 30s grace period. 2. Add uvicorn timeout_graceful_shutdown=30. 3. Remove sys.exit() from signal handlers. 4. Deploy with rolling update (not all-at-once) |
| No health check causing bad routing | MEDIUM | 1. Add /health endpoint immediately. 2. Update load balancer config to use /health. 3. Restart load balancer to apply config. 4. Monitor for routing to unhealthy instances |
| Connection pool exhaustion | LOW | 1. Restart app to clear connections. 2. Increase pool_size and max_overflow in SQLAlchemy config. 3. Add connection leak detection logging. 4. Fix code not closing connections properly |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| APScheduler duplicates | Phase 1: Production Infrastructure | Load test with 4 workers, verify only 1 scheduler executes fetch job. Check logs for single "Fetch complete" message per interval |
| SQLite locking | Phase 1: Production Infrastructure | Migrate to PostgreSQL. Load test with 10 concurrent users performing writes. Verify no "database locked" errors in logs |
| SQL syntax incompatibility | Phase 1: Production Infrastructure | Run full integration test suite against PostgreSQL. Verify all queries return expected results. Check for placeholder errors |
| IP blocking from cloud | Phase 1: Add monitoring, Phase 2: Implement resilience | Deploy to cloud, run scheduled fetches for 7 days. Monitor for 403/429 responses. Verify exponential backoff triggers on rate limits |
| Secrets in version control | Phase 0: Pre-deployment | Git history scan for secrets. Verify .env file used, config.yaml has no hardcoded secrets. Rotate all production secrets |
| No health check endpoint | Phase 1: Production Infrastructure | Load balancer config references /health. Simulate database failure, verify /health returns 503. Check load balancer removes unhealthy instance |
| No graceful shutdown | Phase 1: Production Infrastructure | Send SIGTERM during active request. Verify request completes before shutdown. Check logs show scheduler stops after requests finish |
| Connection pool exhaustion | Phase 1: Production Infrastructure | Load test with 50 concurrent requests. Verify all requests succeed. Monitor connection pool metrics for leaks |
| No error monitoring | Phase 1: Production Infrastructure | Generate test error, verify alert triggered within 5 minutes. Check Sentry dashboard shows error with full context |
| Database backup missing | Phase 1: Production Infrastructure | Verify daily backup cron job configured. Test restore from backup. Verify backup retention policy (30 days minimum) |

## Sources

**Codebase Analysis:**
- C:\CLAUDE\ra-tips\ra-tracker\ra_tracker\main.py - Scheduler startup logic, signal handlers
- C:\CLAUDE\ra-tips\ra-tracker\ra_tracker\scheduler\jobs.py - APScheduler configuration
- C:\CLAUDE\ra-tips\ra-tracker\ra_tracker\database.py - Raw SQL queries, SQLite-specific patterns
- C:\CLAUDE\ra-tips\ra-tracker\ra_tracker\api\ra_client.py - GraphQL client, rate limiting
- C:\CLAUDE\ra-tips\ra-tracker\config.yaml - Hardcoded secrets, configuration patterns

**Training Data Knowledge (no web search available):**
- FastAPI production deployment best practices
- PostgreSQL migration patterns from SQLite
- APScheduler multi-worker deployment patterns
- Web scraping detection and blocking techniques
- Cloud provider IP reputation and rate limiting
- Python secret management patterns
- Kubernetes health check configurations
- Graceful shutdown patterns for ASGI applications

**Confidence Assessment:**
- HIGH confidence: APScheduler multi-worker issue (clear from codebase architecture)
- HIGH confidence: SQLite locking limitations (well-documented constraint)
- HIGH confidence: Secret exposure (observed in config.yaml)
- MEDIUM confidence: SQL syntax migration issues (common pattern but not verified against specific PostgreSQL version)
- MEDIUM confidence: Cloud IP blocking severity (depends on ra.co's specific policies, not publicly documented)
- MEDIUM confidence: Performance thresholds (estimated based on typical SQLite performance, not load tested)

---

*Pitfalls research for: Production deployment of FastAPI GraphQL scraper with APScheduler*
*Researched: 2026-02-11*
*Confidence: MEDIUM (web search unavailable, analysis based on codebase + training data)*
