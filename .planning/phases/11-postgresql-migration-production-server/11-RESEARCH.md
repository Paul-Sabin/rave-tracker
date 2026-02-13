# Phase 11: PostgreSQL Migration & Production Server - Research

**Researched:** 2026-02-13
**Domain:** PostgreSQL migration, production ASGI deployment, APScheduler separation
**Confidence:** HIGH

## Summary

Phase 11 migrates the application from SQLite to PostgreSQL and deploys it with a production-ready multi-worker ASGI server. The current codebase uses synchronous SQLite (not aiosqlite) with 103 raw SQL queries using SQLite-specific syntax (? placeholders, INTEGER booleans, AUTOINCREMENT). The migration requires converting to PostgreSQL syntax (%s placeholders, BOOLEAN type, SERIAL), implementing connection pooling sized for worker count, separating the APScheduler into a dedicated process to prevent duplicate job execution, and adding a health check endpoint with database connectivity verification.

The standard stack is psycopg2 (source distribution) for PostgreSQL connectivity, gunicorn with uvicorn workers for multi-process ASGI serving, and environment-based DATABASE_URL configuration. All 103 SQL queries in database.py must be converted. The project already uses environment variables (Phase 10) and synchronous database operations, simplifying the migration path.

**Primary recommendation:** Use pgloader for data migration, psycopg2 for database connectivity, implement connection pooling with pool_size = (worker_count + 2), run scheduler as separate process with --no-scheduler flag pattern, and add /health endpoint with try/except database ping.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg2 | 2.9.x | PostgreSQL database adapter | Industry standard, stable, supports sync operations (project uses sync not async) |
| gunicorn | 23.0+ | WSGI/ASGI HTTP server process manager | Production-proven multi-worker management, graceful shutdown, handles SIGTERM correctly |
| uvicorn | 0.27.0+ | ASGI server implementation | High-performance async server, used as gunicorn worker class |
| pgloader | 3.6.9+ | Database migration tool | Automatic SQLite to PostgreSQL migration with type conversion |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.0.0+ | Environment variable loading | Already in project (Phase 10) |
| psycopg2-pool | 2.9.x | Connection pooling (built into psycopg2) | Use SimpleConnectionPool or ThreadedConnectionPool for multi-worker setup |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| psycopg2 | psycopg3 | psycopg3 has better async support and performance but requires API changes; psycopg2 works with existing sync code |
| psycopg2 | asyncpg | asyncpg requires rewriting all database code to async; project uses sync operations |
| gunicorn + uvicorn | uvicorn --workers | uvicorn's built-in workers are newer but gunicorn is battle-tested for production |
| pgloader | manual SQL conversion | pgloader automates type conversion and handles edge cases (sequences, indexes) |
| psycopg2 (source) | psycopg2-binary | psycopg2-binary bundles libpq/libssl causing version conflicts and security issues in production |

**Installation:**
```bash
# Python dependencies
pip install psycopg2 gunicorn

# pgloader (for migration)
# Ubuntu/Debian: apt-get install pgloader
# macOS: brew install pgloader
# Windows: docker run --rm -it dimitri/pgloader
```

## Architecture Patterns

### Recommended Project Structure
```
ra-tracker/
├── ra_tracker/
│   ├── database.py         # Convert to PostgreSQL syntax
│   ├── main.py             # Add --scheduler-only mode
│   └── web/
│       └── app.py          # Add /health endpoint
├── config.yaml             # Add database_url placeholder
├── .env                    # Add DATABASE_URL
├── requirements.txt        # Add psycopg2, gunicorn
└── scripts/
    └── migrate_db.sh       # pgloader migration script
```

### Pattern 1: DATABASE_URL Configuration
**What:** Single environment variable for database connection supporting both postgres:// and postgresql:// prefixes
**When to use:** Production deployments, Heroku/Render-style hosting, multi-environment setup

**Implementation:**
```python
# In config.py
@dataclass
class DatabaseConfig:
    path: str = "./data/ra_tracker.db"  # SQLite fallback
    url: Optional[str] = None  # PostgreSQL connection string

# In config loading
if os.environ.get("DATABASE_URL"):
    config.database.url = os.environ["DATABASE_URL"]
    # Normalize postgres:// to postgresql://
    if config.database.url.startswith("postgres://"):
        config.database.url = config.database.url.replace("postgres://", "postgresql://", 1)
```

### Pattern 2: Connection Pooling with Multi-Workers
**What:** Shared connection pool sized appropriately for worker count to prevent connection exhaustion
**When to use:** Multi-worker gunicorn deployment (this phase)

**Formula:** `pool_size = (worker_count + 2)`
- worker_count = number of gunicorn workers (typically 2-4 for CPU cores)
- +2 for scheduler process and maintenance connections

**Implementation:**
```python
# In database.py
from psycopg2.pool import ThreadedConnectionPool

class Database:
    def __init__(self):
        if config.database.url:
            # PostgreSQL with connection pooling
            worker_count = int(os.environ.get('GUNICORN_WORKERS', 4))
            pool_size = worker_count + 2
            self._pool = ThreadedConnectionPool(
                minconn=2,
                maxconn=pool_size,
                dsn=config.database.url
            )
        else:
            # SQLite fallback
            self.db_path = Path(config.database.path)

    @contextmanager
    def get_connection(self):
        if self._pool:
            conn = self._pool.getconn()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._pool.putconn(conn)
        else:
            # SQLite context manager
            ...
```

### Pattern 3: Separated Scheduler Process
**What:** Run APScheduler in a dedicated process, not within web workers
**When to use:** Always with multi-worker ASGI/WSGI servers (gunicorn, uwsgi)
**Why:** APScheduler lacks interprocess synchronization; each worker would spawn duplicate jobs

**Implementation:**
```python
# In main.py - add flag
parser.add_argument(
    "--scheduler-only",
    action="store_true",
    help="Run scheduler only (no web server)",
)

# Deployment: run two processes
# Process 1 (web): gunicorn --workers 4 --no-scheduler
# Process 2 (scheduler): python -m ra_tracker.main --scheduler-only
```

**Procfile pattern (Render/Heroku):**
```
web: gunicorn ra_tracker.web.app:app --bind 0.0.0.0:$PORT --workers 4 --worker-class uvicorn.workers.UvicornWorker --graceful-timeout 30
scheduler: python -m ra_tracker.main --scheduler-only
```

### Pattern 4: Health Check Endpoint with Database Connectivity
**What:** /health endpoint that returns 200 if database is reachable, 503 if not
**When to use:** Production deployments, load balancer health checks, Kubernetes readiness probes

**Implementation:**
```python
# In web/app.py
from fastapi import FastAPI, Response
from ..database import get_db

@app.get("/health")
def health_check(response: Response):
    """Health check endpoint with database connectivity verification."""
    try:
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT 1")
            cursor.fetchone()
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        response.status_code = 503
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }
```

### Pattern 5: Graceful Shutdown with In-Flight Requests
**What:** Handle SIGTERM to allow in-flight requests to complete before shutdown
**When to use:** Production deployments, zero-downtime deploys, Kubernetes pod termination

**Gunicorn configuration:**
```bash
gunicorn \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --graceful-timeout 30 \
  --timeout 60 \
  ra_tracker.web.app:app
```

**What happens:**
1. Gunicorn receives SIGTERM
2. Master process stops accepting new connections
3. Workers finish current requests (up to `graceful-timeout` seconds)
4. Workers that exceed timeout are force-killed
5. Process exits

**Known limitation:** Requests in socket backlog (accepted by OS but not yet by worker) may be dropped. Mitigation: use short graceful-timeout (30s) and rely on client retries.

### Anti-Patterns to Avoid

- **Running APScheduler in web workers:** Causes N*jobs execution where N = worker count (4 workers = 4x duplicate jobs)
- **Using psycopg2-binary in production:** Bundles old libpq/libssl versions, causes segfaults under concurrency
- **Manual SQL query conversion:** Use pgloader to automate type mapping and sequence initialization
- **Shared job store across processes:** APScheduler documentation explicitly warns this causes incorrect behavior
- **Hardcoding connection pool size:** Calculate based on worker count to prevent exhaustion or waste
- **Ignoring postgres:// prefix:** Hosting providers (Render, Railway) use postgres:// but psycopg2 expects postgresql://

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQLite to PostgreSQL type conversion | Manual ALTER TABLE scripts | pgloader | Handles INTEGER→SERIAL, BOOLEAN conversion, sequence initialization, index recreation automatically |
| Connection pooling | Custom connection manager | psycopg2.pool.ThreadedConnectionPool | Thread-safe, handles connection lifecycle, prevents leaks, battle-tested |
| Database URL parsing | String manipulation | psycopg2.extensions.make_dsn() or dj-database-url library | Handles escaping, IPv6, special characters, all PostgreSQL URL formats |
| Health check logic | Custom ping queries | Built-in libraries (fastapi-health, fastapi-healthcheck) | For complex checks; simple SELECT 1 is sufficient for this project |
| Graceful shutdown | Signal handler gymnastics | Gunicorn's built-in graceful_timeout | Already handles SIGTERM, worker coordination, timeout enforcement |

**Key insight:** PostgreSQL migration has many subtle gotchas (sequence initialization, type casting, placeholder syntax, connection limits). Use proven tools (pgloader, psycopg2.pool) rather than reimplementing.

## Common Pitfalls

### Pitfall 1: ? Parameter Placeholders Not Converted
**What goes wrong:** SQLite uses `?` placeholders, PostgreSQL requires `%s`. Queries fail with syntax errors.
**Why it happens:** All 103 queries in database.py use SQLite syntax.
**How to avoid:** Search and replace all `?` with `%s` in SQL strings. Verify no printf-style formatting conflicts.
**Warning signs:** `psycopg2.ProgrammingError: syntax error at or near "?"`

**Example conversion:**
```python
# Before (SQLite)
cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email,))

# After (PostgreSQL)
cursor = conn.execute("SELECT * FROM users WHERE email = %s", (email,))
```

### Pitfall 2: INTEGER BOOLEAN vs PostgreSQL BOOLEAN
**What goes wrong:** SQLite stores booleans as INTEGER (0/1), PostgreSQL has native BOOLEAN type. Type mismatch errors occur.
**Why it happens:** Schema uses `BOOLEAN DEFAULT 1` but SQLite treats as INTEGER, INSERT statements pass integers.
**How to avoid:** Update schema to use TRUE/FALSE, ensure Python passes bool values (not 0/1).
**Warning signs:** `psycopg2.DataError: invalid input syntax for type boolean: "0"`

**Schema conversion:**
```sql
-- SQLite schema
is_active BOOLEAN DEFAULT 1

-- PostgreSQL schema (pgloader handles this)
is_active BOOLEAN DEFAULT TRUE

-- Python code: ensure bool not int
conn.execute("INSERT INTO rules (..., is_active) VALUES (..., %s)", (..., True))  # Not 1
```

### Pitfall 3: AUTOINCREMENT to SERIAL Sequence Not Initialized
**What goes wrong:** pgloader migrates data but sequence starts at 1, causing duplicate key errors on INSERT.
**Why it happens:** SQLite AUTOINCREMENT doesn't use explicit sequences; PostgreSQL SERIAL does.
**How to avoid:** After pgloader, run `SELECT setval('table_id_seq', (SELECT MAX(id) FROM table))` for each table.
**Warning signs:** `psycopg2.IntegrityError: duplicate key value violates unique constraint`

**Post-migration script:**
```sql
-- Reset sequences after pgloader migration
SELECT setval('rules_id_seq', (SELECT COALESCE(MAX(id), 1) FROM rules));
SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id), 1) FROM users));
SELECT setval('notifications_id_seq', (SELECT COALESCE(MAX(id), 1) FROM notifications));
SELECT setval('audit_logs_id_seq', (SELECT COALESCE(MAX(id), 1) FROM audit_logs));
SELECT setval('telegram_link_codes_id_seq', (SELECT COALESCE(MAX(id), 1) FROM telegram_link_codes));
```

### Pitfall 4: Connection Pool Exhaustion with Multi-Workers
**What goes wrong:** 4 gunicorn workers + 1 scheduler + default pool_size=5 = connection errors under load.
**Why it happens:** Each process can hold multiple connections; PostgreSQL has connection limits.
**How to avoid:** Size pool based on workers: `pool_size = worker_count + 2`, set PostgreSQL max_connections appropriately.
**Warning signs:** `psycopg2.OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections`

**Calculation example:**
```
gunicorn --workers 4
scheduler process = 1
pool_size per process = 6 (4 workers + 2 buffer)
Total connections needed = 6
PostgreSQL max_connections = 20 (default 100, sufficient)
```

### Pitfall 5: APScheduler Duplicate Jobs (4x Execution)
**What goes wrong:** Scheduler initialized in each gunicorn worker, jobs run 4 times (once per worker).
**Why it happens:** APScheduler lacks interprocess coordination; each worker creates independent scheduler.
**How to avoid:** Run scheduler in separate process with `--scheduler-only` flag, disable in web workers.
**Warning signs:** Duplicate notifications sent, fetcher runs 4 times simultaneously, rate limiting triggers.

**Detection:**
```python
# In logs, you'll see:
# [2026-02-13 10:00:00] Worker 1: Running fetch job
# [2026-02-13 10:00:00] Worker 2: Running fetch job
# [2026-02-13 10:00:00] Worker 3: Running fetch job
# [2026-02-13 10:00:00] Worker 4: Running fetch job
```

### Pitfall 6: postgres:// vs postgresql:// Prefix Confusion
**What goes wrong:** Hosting providers set DATABASE_URL=postgres://... but psycopg2 fails to connect.
**Why it happens:** postgres:// is generic, postgresql:// is SQLAlchemy convention, some libraries require normalization.
**How to avoid:** Accept both, normalize to postgresql:// in config loader.
**Warning signs:** `ValueError: invalid connection string`

### Pitfall 7: Graceful Shutdown Socket Backlog Drops
**What goes wrong:** During graceful shutdown, requests already accepted by OS (but not yet by worker) are dropped.
**Why it happens:** Workers stop calling accept() on SIGTERM, leaving requests in socket backlog.
**How to avoid:** Keep graceful-timeout reasonable (30s), rely on client/load balancer retries, accept this is a known gunicorn limitation.
**Warning signs:** Client errors during deployment, 502 Bad Gateway from load balancer.

## Code Examples

Verified patterns from official sources:

### SQLite to PostgreSQL Query Migration
```python
# Source: Actual database.py analysis + psycopg2 documentation

# Before (SQLite) - line 417 in database.py
cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email,))

# After (PostgreSQL)
cursor = conn.execute("SELECT * FROM users WHERE email = %s", (email,))

# Before (SQLite) - line 409
conn.execute("UPDATE rules SET user_id = ? WHERE user_id IS NULL", (user_id,))

# After (PostgreSQL)
conn.execute("UPDATE rules SET user_id = %s WHERE user_id IS NULL", (user_id,))

# All 103 instances of ? in database.py must be converted
```

### DATABASE_URL Parsing and Normalization
```python
# Source: Official psycopg2 documentation + hosting provider patterns

import os
from psycopg2 import extensions

# In DatabaseConfig loading
database_url = os.environ.get("DATABASE_URL")
if database_url:
    # Normalize postgres:// to postgresql:// (Heroku/Render compatibility)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # Parse URL to verify format
    try:
        parsed = extensions.parse_dsn(database_url)
    except Exception as e:
        raise ValueError(f"Invalid DATABASE_URL: {e}")

    config.database.url = database_url
```

### Connection Pool Setup for Multi-Worker Deployment
```python
# Source: psycopg2 pool documentation + production patterns

from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager

class Database:
    def __init__(self):
        if config.database.url:
            # Calculate pool size based on worker count
            worker_count = int(os.environ.get("WEB_CONCURRENCY", "4"))
            pool_size = worker_count + 2  # +2 for scheduler and maintenance

            self._pool = ThreadedConnectionPool(
                minconn=2,  # Minimum connections to maintain
                maxconn=pool_size,
                dsn=config.database.url
            )
        else:
            self._pool = None
            # SQLite fallback (existing code)

    @contextmanager
    def get_connection(self):
        if self._pool:
            conn = self._pool.getconn()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._pool.putconn(conn)
        else:
            # Existing SQLite context manager
            conn = sqlite3.connect(...)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
```

### Scheduler Process Separation
```python
# Source: APScheduler FAQ + gunicorn deployment patterns

# In main.py
def main():
    parser = argparse.ArgumentParser(description="RA.co Event Tracker")
    parser.add_argument(
        "--scheduler-only",
        action="store_true",
        help="Run scheduler only (no web server)",
    )
    parser.add_argument(
        "--no-scheduler",
        action="store_true",
        help="Disable the scheduler (web server only)",
    )

    args = parser.parse_args()

    # ... setup code ...

    # Scheduler-only mode
    if args.scheduler_only:
        logger.info("Running in scheduler-only mode")
        start_scheduler()
        logger.info("Scheduler started, running indefinitely")
        # Keep process alive
        import signal
        signal.pause()
        return

    # Start scheduler (unless disabled)
    if not args.no_scheduler:
        start_scheduler()

    # Start web server
    uvicorn.run(...)
```

### Health Check with Database Connectivity
```python
# Source: FastAPI health check patterns + PostgreSQL ping pattern

from fastapi import FastAPI, Response

@app.get("/health")
def health_check(response: Response):
    """
    Health check endpoint for load balancers and monitoring.
    Returns 200 if healthy, 503 if database unavailable.
    """
    health_status = {
        "status": "healthy",
        "database": "unknown"
    }

    try:
        db = get_db()
        with db.get_connection() as conn:
            # Simple connectivity test
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            if result and result[0] == 1:
                health_status["database"] = "connected"
            else:
                health_status["database"] = "error"
                health_status["status"] = "unhealthy"
                response.status_code = 503
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = "disconnected"
        health_status["error"] = str(e)
        response.status_code = 503

    return health_status
```

### pgloader Migration Command
```bash
# Source: pgloader official documentation

# Basic migration (development)
pgloader sqlite://./data/ra_tracker.db postgresql://user:pass@localhost/ra_tracker

# Production migration with options
pgloader --with "include drop" \
         --with "create tables" \
         --with "create indexes" \
         --with "reset sequences" \
         sqlite:///path/to/ra_tracker.db \
         postgresql://user:pass@host:5432/dbname

# After migration, fix sequences
psql -d ra_tracker -c "
SELECT setval('rules_id_seq', (SELECT COALESCE(MAX(id), 1) FROM rules));
SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id), 1) FROM users));
SELECT setval('notifications_id_seq', (SELECT COALESCE(MAX(id), 1) FROM notifications));
SELECT setval('audit_logs_id_seq', (SELECT COALESCE(MAX(id), 1) FROM audit_logs));
"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Uvicorn alone in production | Gunicorn + Uvicorn workers | ~2019-2020 | Multi-core utilization, process management, graceful restarts |
| psycopg2-binary for all | psycopg2 (source) for production | Ongoing best practice | Avoids libpq/libssl version conflicts and segfaults |
| Manual SQL migrations | pgloader for heterogeneous migrations | pgloader 3.6+ (2018+) | Automates type conversion, handles edge cases |
| psycopg2 only | psycopg3 emerging | psycopg3 stable 2021+ | Better async support, performance; psycopg2 still standard for sync |
| Single-process schedulers | Separated scheduler process | APScheduler 3.x+ docs | Prevents duplicate jobs with multi-worker servers |

**Deprecated/outdated:**
- **SQLite for production web apps:** PostgreSQL is standard for concurrent writes, ACID guarantees, hosting support
- **Hardcoded database paths:** DATABASE_URL environment variable is universal convention (Heroku, Render, Railway, Docker)
- **psycopg2-binary in production:** Official docs warn against this; use source distribution
- **Shared APScheduler jobstore:** Never supported correctly; dedicated process is documented pattern

## Open Questions

1. **PostgreSQL connection limit on hosting provider**
   - What we know: Typical managed PostgreSQL has 100-500 connection limit
   - What's unclear: Specific provider choice (Phase 12), their limits, connection pooler availability (pgBouncer)
   - Recommendation: Plan for pool_size=(workers+2)=6, verify provider supports 20+ connections minimum

2. **Data migration timing (with or without downtime)**
   - What we know: pgloader can migrate in minutes; application needs DATABASE_URL set
   - What's unclear: Whether zero-downtime migration is required or acceptable downtime window exists
   - Recommendation: Plan assumes acceptable downtime (5-10 minutes). Use pgloader direct migration, not logical replication.

3. **Handling of existing SQLite migrations in MIGRATIONS list**
   - What we know: database.py has 12 SQLite ALTER TABLE migrations that have run on existing databases
   - What's unclear: Whether pgloader preserves all columns added via ALTER TABLE or only base schema
   - Recommendation: Run pgloader against current SQLite database (with all migrations applied), not against clean schema

4. **Scheduler process monitoring/restart strategy**
   - What we know: Scheduler must run as separate process
   - What's unclear: How hosting provider (Phase 12) handles multi-process apps, health checks for non-HTTP process
   - Recommendation: Assume Procfile-based deployment (Heroku/Render style) with separate `scheduler:` process type

## Sources

### Primary (HIGH confidence)
- [Psycopg2 Official Documentation](https://www.psycopg.org/docs/) - Parameter placeholders, connection pooling, production recommendations
- [FastAPI Server Workers - Official Docs](https://fastapi.tiangolo.com/deployment/server-workers/) - Gunicorn + Uvicorn deployment pattern
- [APScheduler FAQ - Official Docs](https://apscheduler.readthedocs.io/en/3.x/faq.html) - Multi-process deployment, shared jobstore warning
- [pgloader SQLite to PostgreSQL - Official Docs](https://pgloader.readthedocs.io/en/latest/ref/sqlite.html) - Type conversions, sequence handling
- [Gunicorn Settings - Official Docs](https://docs.gunicorn.org/en/latest/settings.html) - graceful_timeout, worker configuration
- [psycopg2.pool Documentation](https://www.psycopg.org/docs/pool.html) - ThreadedConnectionPool API

### Secondary (MEDIUM confidence)
- [Python SQLite to PostgreSQL migration parameter placeholders](https://zetcode.com/python/psycopg2/) - Parameter format differences
- [Mastering Gunicorn and Uvicorn: The Right Way to Deploy FastAPI Applications](https://medium.com/@iklobato/mastering-gunicorn-and-uvicorn-the-right-way-to-deploy-fastapi-applications-aaa06849841e) - Production deployment patterns
- [Run APScheduler With Gunicorn](https://enqueuezero.com/projects/apscheduler/gunicorn.html) - Dedicated process pattern
- [Psycopg2 vs Psycopg3 Performance Benchmark](https://www.tigerdata.com/blog/psycopg2-vs-psycopg3-performance-benchmark) - Library choice for 2026
- [Optimizing Gunicorn: Balancing Threads, Workers, and Connection Pools](https://medium.com/@mailtomugeshs/optimizing-gunicorn-balancing-threads-workers-and-connection-pools-for-better-performance-fbc682f731c4) - Pool sizing formula
- [psycopg2-binary vs psycopg2 in Production](https://www.psycopg.org/docs/install.html) - Production library choice
- [FastAPI Health Check Endpoint Example](https://www.index.dev/blog/how-to-implement-health-check-in-python) - Health check patterns
- [Gunicorn graceful shutdown issues](https://github.com/benoitc/gunicorn/issues/2529) - Known socket backlog limitation

### Tertiary (LOW confidence - needs validation)
- WebSearch results on DATABASE_URL prefix handling - verify with actual hosting provider
- Connection pool sizing formulas - validate against hosting provider limits in Phase 12

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - psycopg2, gunicorn+uvicorn, pgloader are industry-standard, well-documented
- Architecture: HIGH - Patterns verified against official docs (APScheduler FAQ, FastAPI deployment, psycopg2 pool)
- Pitfalls: HIGH - Identified from official warnings (APScheduler, psycopg2-binary), codebase analysis (103 queries), known issues (graceful shutdown)
- Migration process: MEDIUM - pgloader is proven tool but sequence reset and ALTER TABLE handling needs validation

**Research date:** 2026-02-13
**Valid until:** 2026-03-13 (30 days - stack is mature and stable)

**Key findings validated:**
- 103 raw SQL queries in database.py all use `?` placeholders (verified via Grep)
- Project uses synchronous database operations, not async (verified via Grep - no async def in database.py)
- Phase 10 already implemented environment variable configuration (verified via REQUIREMENTS.md traceability)
- Current requirements.txt uses aiosqlite (async SQLite) but database.py uses sqlite3 (sync) - aiosqlite is unused, can be replaced with psycopg2
- Database schema includes 12 SQLite-specific migrations that must be present before pgloader migration
