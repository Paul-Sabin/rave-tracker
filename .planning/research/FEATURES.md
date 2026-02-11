# Feature Research: Production Deployment & Hosting

**Domain:** FastAPI application deployment with GraphQL API scraping
**Researched:** 2026-02-11
**Confidence:** MEDIUM

*Note: Research based on established FastAPI deployment patterns and production best practices. WebSearch unavailable - recommendations based on training data through January 2025.*

## Feature Landscape

### Table Stakes (Users Expect These)

Features that production deployments must have. Missing these = application is not production-ready.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Multi-worker ASGI server** | Single uvicorn process crashes = downtime; can't utilize multiple CPU cores | LOW | Use gunicorn + uvicorn workers or uvicorn with --workers flag |
| **Environment-based configuration** | Secrets must not be in code/version control; different settings per environment | LOW | Already using python-dotenv; needs DATABASE_URL, SMTP credentials, CSRF secrets, Telegram token |
| **HTTPS/SSL termination** | Modern web requirement; browsers block mixed content; SEO penalty without HTTPS | LOW-MEDIUM | Let's Encrypt via Certbot (self-managed) or provider-managed certificates (easier) |
| **Database connection pooling** | SQLite → PostgreSQL migration requires connection management; prevent connection exhaustion | MEDIUM | Use SQLAlchemy or psycopg2 pooling; configure min/max pool size based on worker count |
| **Health check endpoint** | Load balancers, monitoring tools, orchestrators all expect /health or /healthz | LOW | Return 200 OK with basic status; optionally check DB connectivity |
| **Graceful shutdown** | Prevent data loss and connection leaks when restarting/deploying | LOW | Already has SIGTERM handler; ensure in-progress requests complete |
| **Basic request logging** | Troubleshooting production issues impossible without request logs | LOW | Structured logging (JSON) with request IDs, status codes, latency |
| **Error tracking** | Need visibility into production exceptions; logs alone insufficient for aggregation | MEDIUM | Sentry integration or similar (CloudWatch, Datadog APM) |
| **Static file serving** | CSS/JS/images must be served efficiently | LOW | Nginx/Caddy reverse proxy handles this; FastAPI StaticFiles for development |
| **Custom domain + DNS** | Can't use IP addresses or provider subdomains in production | LOW | A/AAAA records pointing to server; CNAME for www |
| **Database backups** | PostgreSQL data must be backed up; disaster recovery requirement | LOW-MEDIUM | Automated daily backups; provider-managed (easiest) or pg_dump cron jobs |
| **Process supervision** | Application must restart on crash; start on boot | LOW | systemd service file or provider-managed process supervision |

### Differentiators (Competitive Advantage)

Features that enhance reliability and operational excellence. Not required for MVP, but valuable for mature deployments.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Structured logging with correlation IDs** | Trace requests across services; debug complex flows | MEDIUM | Use structlog or python-json-logger; add request_id middleware |
| **Automatic database migrations** | Zero-downtime deploys; version control for schema | MEDIUM | Alembic migrations on startup or via deployment pipeline |
| **Rate limiting per API endpoint** | Protect specific expensive operations beyond global rate limit | LOW | Already has slowapi; extend to /api/fetch-now or admin endpoints |
| **APM (Application Performance Monitoring)** | Identify slow queries, N+1 problems, bottlenecks | MEDIUM-HIGH | Datadog APM, New Relic, or self-hosted Grafana + Prometheus |
| **Exponential backoff for API failures** | GraphQL API temporary failures don't fail entire fetch job | MEDIUM | Retry with backoff on 429/503; circuit breaker for extended outages |
| **Separate scheduler process** | Isolate background jobs from web traffic; independent scaling | MEDIUM | Run APScheduler in separate container/process; shared database |
| **Blue-green or rolling deployments** | Zero-downtime deploys; instant rollback capability | MEDIUM-HIGH | Requires load balancer; provider-managed or manual setup |
| **Canary releases** | Test changes with subset of traffic before full rollout | HIGH | Advanced; requires traffic splitting and metrics |
| **Dead letter queue for failed notifications** | Don't lose notification attempts; manual retry for persistent failures | MEDIUM | Store failed Telegram/email sends; admin dashboard to retry |
| **Metrics endpoint** | Expose Prometheus-compatible metrics for monitoring | MEDIUM | /metrics endpoint with request counts, latency percentiles, queue depth |
| **Request/response compression** | Reduce bandwidth; faster page loads | LOW | Gzip middleware in FastAPI or reverse proxy compression |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems for this application type.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **User-Agent rotation for every request** | "Avoid detection" mindset from HTML scraping | GraphQL APIs don't care about User-Agent like scrapers do; adds complexity for no benefit | Single realistic User-Agent; rely on rate limiting and respectful scraping |
| **Proxy rotation** | Common in aggressive scraping | ra.co GraphQL API is public; IP blocking unlikely with respectful rate limits (1s between requests) | Direct requests with proper rate limiting; only add proxies if actually blocked |
| **Containerization (Docker) for single-server deployment** | "Modern best practice" | Adds deployment complexity (image builds, registry, orchestration) without multi-server benefits | Direct deployment with systemd; Docker makes sense for multi-service or multi-server |
| **Kubernetes for small-scale app** | Resume-driven development | Massive operational overhead for single-server app; over-engineering | VPS with systemd or managed app platform (Render, Railway) |
| **Real-time scraping (websockets/SSE to frontend)** | "Show live updates" | Adds complexity; scheduler already runs every 6 hours; no user demand for live scraping | Keep existing polling model; use SSE only if users actively request it |
| **Multiple database replicas** | High availability | Single server → single database sufficient; replication adds complexity and cost | Start with single PostgreSQL; add read replicas only at scale |
| **Auto-scaling** | Handle traffic spikes | Event tracker has predictable load (scheduled scraping + occasional dashboard views); auto-scaling overkill | Fixed-size deployment; scale manually if actually needed |

## Feature Dependencies

```
[HTTPS/SSL]
    └──requires──> [Custom Domain]
                       └──requires──> [DNS Configuration]

[Multi-worker Server]
    └──requires──> [Database Connection Pooling]  (avoid connection exhaustion)

[PostgreSQL Migration]
    └──requires──> [Environment Variables]
    └──requires──> [Connection Pooling]
    └──enables──> [Database Backups]

[Health Checks]
    └──enhances──> [Process Supervision]  (systemd can restart on health check failure)
    └──enables──> [Load Balancing]  (if multi-server in future)

[Structured Logging]
    └──enhances──> [Error Tracking]  (richer context for exceptions)
    └──enhances──> [APM]  (better trace correlation)

[Exponential Backoff]
    └──requires──> [Error Handling in Scraper]
    └──conflicts──> [Fixed Retry Counts]  (can't do both)

[Separate Scheduler Process]
    └──requires──> [Shared Database]
    └──conflicts──> [In-memory Scheduler State]  (must use persistent job store)
```

### Dependency Notes

- **Multi-worker Server requires Connection Pooling:** Each uvicorn worker maintains its own database connections. Without pooling, 4 workers × 100 concurrent requests = 400 connections, exceeding typical PostgreSQL limits.
- **PostgreSQL Migration enables Backups:** SQLite file backups are simple (copy file). PostgreSQL requires pg_dump or provider-managed backups. Can't defer backup strategy.
- **HTTPS requires Custom Domain:** Let's Encrypt certificates require a domain name (not IP address). Must set up DNS before SSL.
- **Separate Scheduler Process conflicts with In-memory State:** APScheduler by default uses in-memory job store. Separate process requires database-backed job store (SQLAlchemy) or accept duplicate jobs.

## Scraper Resilience: GraphQL API-Specific Features

GraphQL APIs differ from HTML scraping. The ra.co GraphQL endpoint is:
- **Public API** (not anti-bot protected)
- **Structured responses** (no parsing brittleness)
- **Rate-limited** (but predictable, not hostile)

### Table Stakes for GraphQL Scraping

| Feature | Why Essential | Complexity | Implementation Notes |
|---------|--------------|------------|---------------------|
| **Request spacing** | Respectful scraping; avoid rate limits | LOW | Already implemented (MIN_REQUEST_INTERVAL = 1.0s in ra_client.py) |
| **Timeout configuration** | Prevent hung requests from blocking scheduler | LOW | Already set (timeout=30s in ra_client.py) |
| **HTTP error handling** | 4xx/5xx responses must not crash fetch job | LOW | Handle 429 (rate limit), 503 (service down), 403 (forbidden) |
| **Partial success handling** | One failed artist/venue shouldn't fail entire job | MEDIUM | Wrap each entity fetch in try/except; log failures; continue |
| **Retry with exponential backoff** | Temporary failures (503, network errors) should retry | MEDIUM | 3 retries with exponential backoff (1s, 2s, 4s); log persistent failures |

### Nice-to-Have for GraphQL Scraping

| Feature | Value | Complexity | When to Add |
|---------|-------|------------|-------------|
| **Circuit breaker** | Stop hammering API if it's down; fast-fail during outages | MEDIUM | Add if seeing extended API outages (> 5 minutes) |
| **Response validation** | Detect schema changes early | MEDIUM | Add if API responses start changing unexpectedly |
| **Request deduplication** | Skip re-fetching same entity within time window | MEDIUM | Add if tracking many overlapping entities (same artist in multiple rules) |
| **GraphQL query optimization** | Request only needed fields | LOW | Already well-structured; optimize if payload size becomes issue |

### Overkill for GraphQL Scraping

| Feature | Why Not Needed |
|---------|---------------|
| **User-Agent rotation** | GraphQL APIs don't fingerprint User-Agents like anti-bot systems do |
| **Proxy rotation** | No evidence of IP-based blocking; adds cost and complexity |
| **Browser automation (Selenium/Playwright)** | GraphQL API doesn't require JavaScript rendering |
| **CAPTCHA solving** | No CAPTCHA on GraphQL endpoint |
| **Aggressive retries (10+ attempts)** | If API is down that long, exponential backoff would delay job for hours |

## MVP Definition

### Launch With (Production v1)

Minimum viable production deployment. Without these, application is not production-ready.

- [x] **Multi-worker ASGI server** — Utilize multiple cores; automatic worker restarts
  - Implementation: Gunicorn with 4 uvicorn workers: `gunicorn ra_tracker.web.app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker`
  - Or: `uvicorn ra_tracker.web.app:app --workers 4 --host 0.0.0.0 --port 8080`

- [x] **Environment variable management** — Secrets outside version control
  - Implementation: .env file with DATABASE_URL, SMTP_*, TELEGRAM_BOT_TOKEN, CSRF_SECRET_KEY, SECRET_KEY
  - Already using python-dotenv; extend config.yaml to read all secrets from env

- [x] **PostgreSQL with connection pooling** — Production-grade database
  - Implementation: SQLAlchemy with pool_size=10, max_overflow=20
  - Or: psycopg2.pool.SimpleConnectionPool if not using ORM

- [x] **Health check endpoint** — Monitoring and load balancer support
  - Implementation: `GET /health` returns `{"status": "ok", "database": "connected"}` with 200 OK

- [x] **HTTPS with custom domain** — Security and credibility
  - Implementation: Let's Encrypt with Certbot (if self-managed) or provider-managed SSL
  - Nginx/Caddy reverse proxy for SSL termination

- [x] **Basic structured logging** — Troubleshooting production issues
  - Implementation: JSON logs with timestamp, level, logger, message, request_id (if in request context)

- [x] **Process supervision** — Auto-restart on crash; start on boot
  - Implementation: systemd service file or provider-managed process

- [x] **GraphQL API retry logic** — Handle temporary failures
  - Implementation: Retry 429/503 responses 3 times with exponential backoff (1s, 2s, 4s)
  - Wrap each entity fetch in try/except; continue on individual failures

- [x] **Database backups** — Disaster recovery
  - Implementation: Provider-managed automated backups (daily) or cron job running pg_dump

### Add After Validation (v1.x)

Features to add once core deployment is stable and usage patterns are known.

- [ ] **Error tracking (Sentry)** — Trigger: First production exception that's hard to debug from logs
  - Sentry free tier sufficient for low-traffic app; integrate with FastAPI middleware

- [ ] **APM (Application Performance Monitoring)** — Trigger: Slow page loads or unclear performance bottleneck
  - Start with built-in logging of request latency; add Datadog/New Relic if needed

- [ ] **Separate scheduler process** — Trigger: Scheduler jobs interfering with web request latency
  - Run APScheduler in separate systemd service; share PostgreSQL database

- [ ] **Circuit breaker for API failures** — Trigger: ra.co API has extended outage (> 10 minutes)
  - Implement circuit breaker pattern to stop retrying during known outages

- [ ] **Metrics endpoint** — Trigger: Need quantitative data for optimization decisions
  - Expose Prometheus-compatible /metrics with request counts, latency, job success/failure counts

- [ ] **Dead letter queue for notifications** — Trigger: Missing notifications due to transient failures
  - Store failed notification attempts; admin UI to manually retry

### Future Consideration (v2+)

Features to defer until application scales or specific problems emerge.

- [ ] **Blue-green deployments** — Defer until: Downtime during deploys becomes user complaint
  - Requires load balancer and second server/container instance

- [ ] **Read replicas** — Defer until: Database read queries slow down under load
  - Current usage pattern (scheduled writes, occasional dashboard reads) doesn't warrant replicas

- [ ] **Multi-region deployment** — Defer until: International users or redundancy requirement
  - Single region sufficient for event tracking application

- [ ] **Request/response caching** — Defer until: Repeated queries to dashboard causing performance issues
  - Use Redis for dashboard query caching if needed

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Multi-worker server | HIGH | LOW | P1 |
| Environment variables | HIGH | LOW | P1 |
| PostgreSQL migration | HIGH | MEDIUM | P1 |
| Connection pooling | HIGH | MEDIUM | P1 |
| Health check endpoint | MEDIUM | LOW | P1 |
| HTTPS/SSL | HIGH | LOW | P1 |
| Custom domain | HIGH | LOW | P1 |
| Process supervision | HIGH | LOW | P1 |
| GraphQL retry logic | HIGH | MEDIUM | P1 |
| Database backups | HIGH | LOW | P1 |
| Structured logging | MEDIUM | LOW | P1 |
| Error tracking (Sentry) | MEDIUM | MEDIUM | P2 |
| APM | MEDIUM | HIGH | P2 |
| Circuit breaker | LOW | MEDIUM | P2 |
| Separate scheduler | MEDIUM | MEDIUM | P2 |
| Metrics endpoint | MEDIUM | MEDIUM | P2 |
| Dead letter queue | LOW | MEDIUM | P2 |
| Blue-green deploys | LOW | HIGH | P3 |
| Read replicas | LOW | HIGH | P3 |
| Multi-region | LOW | HIGH | P3 |
| Caching | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for production launch
- P2: Should have, add when specific need emerges
- P3: Nice to have, future consideration

## Production Web Server Configuration Patterns

### Worker Count Recommendations

| Server CPU Cores | Recommended Workers | Rationale |
|------------------|---------------------|-----------|
| 1-2 cores | 2-3 workers | (2 × cores) + 1 formula |
| 4 cores | 5-9 workers | Balance between CPU and I/O wait |
| 8+ cores | 9-17 workers | Diminishing returns; I/O bound |

**For FastAPI + PostgreSQL (I/O bound):**
- Formula: `(2 × CPU_cores) + 1`
- Example: 4-core VPS → 9 workers
- Adjust down if hitting connection pool limits

### Timeout Configuration

| Timeout Type | Recommended Value | Rationale |
|--------------|-------------------|-----------|
| Worker timeout | 60-120 seconds | Longer than longest expected request (scraping jobs) |
| Keep-alive timeout | 5 seconds | Connection reuse without tying up workers |
| Database query timeout | 30 seconds | Prevent runaway queries |
| HTTP client timeout | 30 seconds | Already configured in ra_client.py |

### Health Check Implementation

```python
# Minimal health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Health check with database connectivity
@app.get("/health")
async def health_check():
    try:
        db.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected", "error": str(e)}
        )
```

## Environment Variable Management Patterns

### Required Environment Variables for Production

| Variable | Purpose | Example Value | Secret? |
|----------|---------|---------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` | YES (password) |
| `SECRET_KEY` | Session signing, CSRF | Random 32+ char string | YES |
| `SMTP_SERVER` | Email sending | `smtp-relay.brevo.com` | NO |
| `SMTP_PORT` | Email port | `587` | NO |
| `SMTP_USERNAME` | SMTP auth | `a1cbcc001@smtp-brevo.com` | NO |
| `SMTP_PASSWORD` | SMTP auth | API key from provider | YES |
| `TELEGRAM_BOT_TOKEN` | Notification delivery | `8200624905:AAFcNY1...` | YES |
| `BASE_URL` | Email links, webhooks | `https://ravetracker.example.com` | NO |
| `ENVIRONMENT` | Environment indicator | `production` | NO |
| `LOG_LEVEL` | Logging verbosity | `INFO` or `WARNING` | NO |

### .env File Pattern

```bash
# .env (gitignored)
DATABASE_URL=postgresql://user:password@localhost:5432/ra_tracker
SECRET_KEY=your-secret-key-here-min-32-chars
SMTP_PASSWORD=your-smtp-api-key
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
BASE_URL=https://ravetracker.example.com
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### Configuration Loading Pattern

```python
# Already using python-dotenv
from dotenv import load_dotenv
import os

load_dotenv()  # Load .env file

# Environment variables override config.yaml
DATABASE_URL = os.getenv("DATABASE_URL", config.database.path)
SECRET_KEY = os.getenv("SECRET_KEY", config.app.secret_key)
```

## SSL/HTTPS Automation Patterns

### Option 1: Provider-Managed SSL (Easiest)

**Providers offering automatic SSL:**
- Render, Railway, Fly.io, Heroku — Automatic Let's Encrypt certificates
- No configuration needed; SSL automatically provisioned on custom domain

**Pros:** Zero configuration, automatic renewal, no maintenance
**Cons:** Tied to provider, no control over certificate

### Option 2: Reverse Proxy with Let's Encrypt (Self-Managed VPS)

**Caddy (Recommended for Simplicity):**

```
ravetracker.example.com {
    reverse_proxy localhost:8080
}
```

Caddy automatically obtains and renews Let's Encrypt certificates.

**Nginx + Certbot:**

```nginx
# /etc/nginx/sites-available/ravetracker
server {
    listen 80;
    server_name ravetracker.example.com;

    # Certbot challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name ravetracker.example.com;

    ssl_certificate /etc/letsencrypt/live/ravetracker.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ravetracker.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Certificate renewal:** `certbot renew` (automatic via cron job)

### Option 3: Cloudflare Proxy (Free SSL + CDN)

- Point domain to Cloudflare nameservers
- Enable "Proxied" on A record
- Free SSL certificate (Cloudflare to browser)
- Optional: Full SSL mode (Cloudflare to origin with self-signed cert)

**Pros:** Free, includes DDoS protection, CDN
**Cons:** Traffic proxied through Cloudflare, privacy considerations

## Custom Domain Setup Patterns

### DNS Configuration (Typical Setup)

**For VPS with static IP:**
```
Type    Name    Value                    TTL
A       @       203.0.113.42             3600
A       www     203.0.113.42             3600
```

**For platform hosting (Render, Railway, etc.):**
```
Type    Name    Value                           TTL
CNAME   @       your-app.onrender.com          3600
CNAME   www     your-app.onrender.com          3600
```

Note: Some DNS providers don't allow CNAME on apex domain (@). Use ALIAS or ANAME record if available, or use A record pointing to provider's IP.

### Domain Provider Recommendations

| Provider | Pros | Cons |
|----------|------|------|
| Cloudflare Registrar | Cheapest, built-in DNS, fast propagation | Limited TLD selection |
| Namecheap | Affordable, good UI | DNS can be slow |
| Google Domains (now Squarespace) | Reliable, clean interface | More expensive |
| Porkbun | Very affordable, good features | Smaller provider |

**DNS propagation:** 5 minutes to 48 hours (typically < 1 hour with low TTL)

## Database Connection Pooling for PostgreSQL

### Why Pooling is Required

**Problem:** Each worker spawns connections on demand
- 4 workers × 25 concurrent requests = 100 simultaneous connections
- PostgreSQL default max_connections = 100
- Adding 5th worker or traffic spike → connection exhaustion

**Solution:** Connection pooling limits and reuses connections

### SQLAlchemy Pooling (Recommended for FastAPI)

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,          # Connections maintained in pool
    max_overflow=20,       # Additional connections on demand
    pool_pre_ping=True,    # Verify connection before use
    pool_recycle=3600,     # Recycle connections after 1 hour
)

# Total max connections per worker: pool_size + max_overflow = 30
# With 4 workers: 4 × 30 = 120 connections (set PostgreSQL max_connections > 120)
```

**Recommended Settings:**

| Workers | pool_size | max_overflow | Total Max Connections | PostgreSQL max_connections |
|---------|-----------|--------------|----------------------|---------------------------|
| 2 | 5 | 10 | 30 | 50+ |
| 4 | 10 | 20 | 120 | 150+ |
| 8 | 10 | 20 | 240 | 300+ |

### psycopg2 Pooling (Without SQLAlchemy)

```python
from psycopg2 import pool

connection_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=DATABASE_URL
)

def get_connection():
    return connection_pool.getconn()

def release_connection(conn):
    connection_pool.putconn(conn)
```

### PostgreSQL Configuration

```conf
# /etc/postgresql/14/main/postgresql.conf
max_connections = 150           # Must be > (workers × max pool size)
shared_buffers = 256MB          # 25% of RAM for databases < 1GB
effective_cache_size = 1GB      # 50-75% of total RAM
```

## Logging and Monitoring Patterns

### Structured Logging (JSON Format)

**Why:** Machine-readable logs for aggregation, searching, alerting

```python
# Using python-json-logger
import logging
from pythonjsonlogger import jsonlogger

logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    "%(timestamp)s %(level)s %(name)s %(message)s %(request_id)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Log with context
logger.info("User login", extra={
    "user_id": 123,
    "ip_address": request.client.host,
    "request_id": request.state.request_id
})
```

**Output:**
```json
{"timestamp": "2026-02-11T10:30:45", "level": "INFO", "name": "ra_tracker.auth", "message": "User login", "user_id": 123, "ip_address": "203.0.113.42", "request_id": "abc-123"}
```

### Request ID Middleware

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestIDMiddleware)
```

### Production Logging Levels

| Environment | Level | Rationale |
|-------------|-------|-----------|
| Development | DEBUG | Full visibility during development |
| Staging | INFO | Reasonable detail for testing |
| Production | WARNING | Reduce log volume; focus on issues |

**Exception:** Set libraries to WARNING even in development:
```python
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
```

### Error Tracking Integration (Sentry)

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("ENVIRONMENT", "production"),
    traces_sample_rate=0.1,  # Sample 10% of transactions for performance monitoring
    integrations=[FastApiIntegration()],
)
```

**Value:** Aggregated error reports with stack traces, context, and user impact data

### Key Metrics to Log

| Metric | What to Track | Why |
|--------|---------------|-----|
| **Request latency** | p50, p95, p99 response times | Identify slow endpoints |
| **Error rate** | 4xx and 5xx responses per minute | Detect issues early |
| **Scraper success rate** | Successful vs failed API fetches | Monitor ra.co API reliability |
| **Database query time** | Slow query log (> 1s) | Identify optimization opportunities |
| **Queue depth** | APScheduler pending jobs | Detect scheduler backlog |
| **Notification delivery** | Sent vs failed Telegram/email | Ensure users get alerts |

### Log Aggregation Options

**Self-Hosted:**
- ELK Stack (Elasticsearch, Logstash, Kibana) — Powerful but complex
- Grafana Loki — Lighter weight, integrates with Grafana

**Managed Services:**
- CloudWatch Logs (AWS) — Built-in if using AWS
- Datadog — Full observability platform
- Logtail — Simple, affordable log aggregation
- Better Stack (formerly Logtail) — Developer-friendly logging

**For small-scale deployment:** Start with systemd journal logs (`journalctl -u ravetracker -f`) + Sentry for errors. Add log aggregation when managing multiple servers or need advanced search.

## Deployment Architecture Patterns

### Single-Server Architecture (Recommended for MVP)

```
Internet
    ↓
[Cloudflare or DNS]
    ↓
[Nginx/Caddy - SSL Termination]
    ↓
[Gunicorn + Uvicorn Workers] (Port 8080)
    ↓
[PostgreSQL] (Port 5432)
```

**Single VPS running:**
- Nginx or Caddy (reverse proxy, SSL termination)
- Gunicorn with 4-9 uvicorn workers
- PostgreSQL database
- APScheduler (embedded in workers or separate process)

**Pros:** Simple, cost-effective, sufficient for < 10K users
**Cons:** Single point of failure, limited scaling

### Managed Platform Architecture (Easiest for MVP)

**Platforms:** Render, Railway, Fly.io, Heroku

```
Internet
    ↓
[Platform Load Balancer + SSL]
    ↓
[Platform-Managed App Instance]
    ↓
[Platform-Managed PostgreSQL]
```

**Pros:** Zero infrastructure management, automatic SSL, built-in monitoring, easy scaling
**Cons:** Higher cost at scale, less control, potential vendor lock-in

**Cost Comparison (Example for 1GB RAM, PostgreSQL):**
- VPS (DigitalOcean): $12/month (droplet) + $15/month (managed PostgreSQL) = $27/month
- Render: $25/month (web service) + $15/month (PostgreSQL) = $40/month
- Railway: $20/month (usage-based, includes database)

### When to Move to Multi-Server

**Triggers:**
- Traffic exceeds single server capacity (CPU > 80% sustained)
- Need geographic distribution (multi-region)
- Regulatory requirement for redundancy
- Can afford increased operational complexity

**Don't scale prematurely:** Vertical scaling (bigger VPS) is simpler than horizontal scaling (load balancing, session management, database replication).

## Sources

- FastAPI official documentation (deployment patterns, production best practices)
- Uvicorn documentation (worker configuration, production deployment)
- Gunicorn documentation (worker class integration with uvicorn)
- PostgreSQL documentation (connection pooling, max_connections configuration)
- SQLAlchemy documentation (connection pool configuration)
- Let's Encrypt documentation (certificate automation)
- Caddy documentation (automatic HTTPS)
- Nginx documentation (reverse proxy configuration)
- Sentry documentation (FastAPI integration)
- Established industry practices for Python web application deployment (2024-2025)

**Confidence Level:** MEDIUM
- Core recommendations (multi-worker, pooling, SSL, environment variables) are well-established industry standards (HIGH confidence)
- Specific tool versions and configurations based on training data through January 2025 (MEDIUM confidence)
- Unable to verify current 2026 ecosystem changes without web search; patterns unlikely to change significantly in 1 year
- GraphQL scraping recommendations based on general API consumption best practices (MEDIUM-HIGH confidence)

---
*Feature research for: Production Deployment & Hosting (FastAPI + GraphQL Scraping)*
*Researched: 2026-02-11*
*Researcher: GSD Research Agent*
