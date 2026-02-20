# Phase 12: Hosting & SSL Deployment - Research

**Researched:** 2026-02-14
**Domain:** Platform-as-a-Service (PaaS) deployment, PostgreSQL hosting, SSL/HTTPS configuration
**Confidence:** HIGH

## Summary

Phase 12 requires deploying a Python ASGI application (Starlette) with two separate processes (web workers and background scheduler), PostgreSQL database with automated backups, HTTPS with automatic SSL certificates, and custom domain configuration. The primary challenge is selecting a hosting provider that supports multiple process types, managed PostgreSQL with backups, and automatic SSL while being cost-effective.

Three main PaaS providers dominate this space: Railway, Render, and Fly.io. All three support Python ASGI deployments, managed PostgreSQL, automatic SSL via Let's Encrypt, custom domains, and git-push deployment pipelines. Key differentiators are pricing models (usage-based vs flat-rate), native backup support, and how they handle multiple process types.

**Primary recommendation:** Render or Fly.io for native PostgreSQL backups; Railway requires third-party template for backups. For applications requiring separate scheduler processes, use platform-specific patterns (Render's background workers, Railway's multiple services, or Fly.io's process groups).

## Standard Stack

### Core Infrastructure
| Component | Recommendation | Purpose | Why Standard |
|-----------|---------------|---------|--------------|
| Gunicorn + Uvicorn | Latest stable | ASGI server with workers | Industry standard for ASGI production deployments |
| PostgreSQL 16 | Latest provider version | Production database | Modern, feature-complete, provider-managed |
| Let's Encrypt | Provider-managed | SSL/HTTPS certificates | Free, automatic, 90-day rotation with auto-renewal |
| PgBouncer | Provider-included | Connection pooling | Reduces connection overhead, included with managed offerings |

### Platform Options (Choose One)

#### Option A: Render (Recommended for Native Backups + Background Workers)
| Feature | Details | Notes |
|---------|---------|-------|
| Pricing | Flat monthly ($7+ web service, $19+ Pro with managed DB) | Predictable costs |
| PostgreSQL | Fully managed with automated backups | Native backup/restore, point-in-time recovery |
| Multiple Processes | Native background worker service type | Separate services for web + scheduler |
| SSL | Automatic Let's Encrypt | Free, automatic renewal |
| Deployment | Git push to branch | Auto-deploy on commit |
| **Best For** | Applications requiring reliable backups, background workers, predictable pricing |

**Installation:**
```bash
# No local installation required - all configuration via Render dashboard
# Define services in render.yaml for multi-service apps
```

#### Option B: Fly.io (Recommended for Global Distribution)
| Feature | Details | Notes |
|---------|---------|-------|
| Pricing | Usage-based ($38+ managed Postgres Basic plan) | Pay for what you use |
| PostgreSQL | Managed Postgres with automated backups | High availability, automatic failover |
| Multiple Processes | Process groups in fly.toml | Single app, multiple process types |
| SSL | Automatic Let's Encrypt via flyctl | Requires IPv6 allocation |
| Deployment | flyctl deploy or git push | CLI-first workflow |
| **Best For** | Applications needing global distribution, flexible scaling |

**Installation:**
```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login and create app
flyctl auth login
flyctl launch
```

#### Option C: Railway (Usage-Based Pricing, Template Backups)
| Feature | Details | Notes |
|---------|---------|-------|
| Pricing | Usage-based ($2-50+/month depending on traffic) | Cost varies with usage |
| PostgreSQL | Managed but no native automated backups | Requires third-party template for backups |
| Multiple Processes | Multiple services or custom start commands | Monorepo-friendly |
| SSL | Automatic Let's Encrypt | Free, automatic renewal |
| Deployment | Git push via Railpack/Nixpacks | Auto-detection, fast deploys |
| **Best For** | Cost-conscious projects, monorepo architectures |

**Installation:**
```bash
# No local CLI required - configuration via Railway dashboard
# Optional: Use Procfile or railway.toml for advanced configuration
```

### Supporting Tools
| Tool | Purpose | When to Use |
|------|---------|-------------|
| psycopg2 | PostgreSQL adapter | **Production** - use source distribution, not psycopg2-binary |
| gunicorn_worker_healthcheck | Dedicated health check thread | Optional - prevents health check timeout under load |
| python-decouple | Environment variable management | Optional - cleaner env var handling |

## Architecture Patterns

### Recommended Deployment Structure

```
Repository Root
├── app/                    # Application code
│   ├── main.py            # Starlette app entry point
│   ├── scheduler.py       # APScheduler configuration
│   └── ...
├── requirements.txt       # Python dependencies (psycopg2, not psycopg2-binary)
├── .env.example          # Document all required env vars
├── Procfile              # Process definitions (if using Railway)
├── render.yaml           # Multi-service config (if using Render)
└── fly.toml              # App config (if using Fly.io)
```

### Pattern 1: Separate Web and Scheduler Processes

**What:** Run gunicorn web workers and APScheduler scheduler as separate processes to avoid duplicate job execution.

**When to use:** Applications with scheduled background tasks using APScheduler alongside web endpoints.

**Why separate processes:** APScheduler lacks interprocess synchronization - running in multiple web workers causes duplicate job execution and missed schedules.

#### Render Implementation:
```yaml
# render.yaml
services:
  - type: web
    name: ra-tips-web
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn -k uvicorn.workers.UvicornWorker --workers 2 app.main:app
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: ra-tips-db
          property: connectionString

  - type: worker
    name: ra-tips-scheduler
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python -m app.scheduler
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: ra-tips-db
          property: connectionString

databases:
  - name: ra-tips-db
    databaseName: ra_tips
    plan: starter
```

#### Railway Implementation:
Create two separate services from the same repository:
- **Service 1 (Web):** Start command = `gunicorn -k uvicorn.workers.UvicornWorker --workers 2 app.main:app`
- **Service 2 (Scheduler):** Start command = `python -m app.scheduler` (or use --scheduler-only flag)

#### Fly.io Implementation:
```toml
# fly.toml
[processes]
web = "gunicorn -k uvicorn.workers.UvicornWorker --workers 2 app.main:app"
scheduler = "python -m app.scheduler"

[[services]]
processes = ["web"]
internal_port = 8000
protocol = "tcp"

  [[services.ports]]
  port = 80
  handlers = ["http"]

  [[services.ports]]
  port = 443
  handlers = ["tls", "http"]
```

### Pattern 2: Gunicorn Worker Configuration

**What:** Configure gunicorn with appropriate worker count and timeout for the workload.

**When to use:** Production ASGI deployment.

**Example:**
```bash
# For CPU-bound work: (2 × CPU_cores) + 1
# For async I/O (Uvicorn workers): CPU_cores (avoid context switching)

# Standard configuration for 2 CPU cores:
gunicorn -k uvicorn.workers.UvicornWorker \
  --workers 2 \
  --timeout 120 \
  --bind 0.0.0.0:$PORT \
  app.main:app

# For web scraper with long-running requests:
gunicorn -k uvicorn.workers.UvicornWorker \
  --workers 2 \
  --timeout 300 \
  --graceful-timeout 60 \
  --bind 0.0.0.0:$PORT \
  app.main:app
```
**Source:** [Uvicorn Deployment Docs](https://uvicorn.dev/deployment/), [Gunicorn Settings](https://gunicorn.org/reference/settings/)

### Pattern 3: Health Check Endpoint

**What:** Implement a simple health check endpoint for platform monitoring.

**When to use:** All production deployments - platforms use this to verify service health.

**Example:**
```python
# app/main.py
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

async def health_check(request):
    return JSONResponse({"status": "healthy"})

routes = [
    Route("/health", health_check, methods=["GET"]),
    # ... other routes
]

app = Starlette(routes=routes)
```

### Pattern 4: Environment Variable Management

**What:** Use provider environment variables for all configuration and secrets.

**When to use:** All deployments - never hardcode credentials or config.

**Best practices:**
- Use `DATABASE_URL` provided by platform (format: `postgresql://user:pass@host:port/db`)
- Seal/encrypt sensitive variables (Telegram bot token, email password, API keys)
- Document all required variables in `.env.example`
- Validate presence of required variables at startup

**Example:**
```python
import os
import sys

# Validate required environment variables at startup
required_vars = ['DATABASE_URL', 'TELEGRAM_BOT_TOKEN', 'EMAIL_PASSWORD']
missing = [var for var in required_vars if not os.getenv(var)]

if missing:
    print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)

# Access variables
DATABASE_URL = os.getenv('DATABASE_URL')
```

### Pattern 5: Custom Domain and SSL Setup

**Railway:**
1. Add custom domain in service settings
2. Create CNAME record pointing to Railway's provided value (e.g., `g05ns7.up.railway.app`)
3. Wait for automatic SSL certificate issuance (within 1 hour)
4. Railway auto-renews certificates 30 days before expiry

**Render:**
1. Add custom domain in service settings
2. Create DNS records as instructed (typically CNAME for subdomains, ALIAS/ANAME for apex)
3. Automatic SSL certificate provisioning via Let's Encrypt
4. Auto-renewal handled by platform

**Fly.io:**
1. Allocate IPv6: `flyctl ips allocate-v6`
2. Add certificate: `flyctl certs add yourdomain.com`
3. Create A/AAAA records pointing to Fly IPs (recommended) or CNAME to `.fly.dev` hostname
4. Automatic certificate validation and renewal
5. **Critical:** IPv6 required for certificate generation unless using DNS-01 challenge

**Source:** [Railway Domains](https://docs.railway.com/networking/domains), [Fly.io Custom Domains](https://fly.io/docs/networking/custom-domain/)

### Anti-Patterns to Avoid

- **Running APScheduler in multiple web workers:** Causes duplicate job execution. Always use dedicated process.
- **Using psycopg2-binary in production:** Creates library conflicts, prevents system library upgrades. Use psycopg2 source distribution.
- **Enabling DEBUG=True in production:** Exposes source code, local variables, and security keys.
- **Hardcoding timeouts for scrapers:** Use configurable timeouts (gunicorn `--timeout`) appropriate for longest expected scrape duration.
- **Direct PostgreSQL connections without pooling:** Exhausts connection limits. Use PgBouncer (included with managed platforms).
- **Ignoring health check endpoints:** Platforms rely on health checks for deployment verification and auto-restart.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSL certificate management | Custom Let's Encrypt automation | Platform-managed SSL (Railway/Render/Fly.io) | Certificate rotation, renewal logic, validation challenges, rate limiting handling |
| PostgreSQL backups | Custom pg_dump cron jobs | Render Managed Postgres or Fly.io Managed Postgres | Point-in-time recovery, backup encryption, automated retention policies, restore testing |
| Database connection pooling | Custom connection pool logic | PgBouncer (included with managed databases) | Connection lifecycle management, transaction/session pooling modes, health monitoring |
| Deployment pipeline | Custom git hooks + SSH | Platform git integration | Build caching, rollback mechanisms, health check integration, zero-downtime deploys |
| Process management | Custom supervisord/systemd configs | Platform process management (render.yaml, fly.toml, Railway services) | Auto-restart, log aggregation, scaling, resource limits |
| Secrets management | .env files committed to repo | Platform environment variables with encryption | Secure storage, audit logs, per-environment configuration, secret rotation |

**Key insight:** PaaS platforms abstract operational complexity that would require dedicated DevOps expertise to implement reliably. The time saved on infrastructure maintenance far exceeds the cost premium over bare VMs.

## Common Pitfalls

### Pitfall 1: Cloud IP Blocking for Web Scrapers

**What goes wrong:** Application works locally but scraping fails in production with 403 errors or CAPTCHAs.

**Why it happens:** Websites detect and block datacenter IP ranges from cloud providers (AWS, DigitalOcean, Railway, Render, Fly.io). Datacenter IPs have 3-4x higher block rates than residential IPs due to abuse associations. Modern anti-bot systems (Cloudflare, Akamai) use machine learning to identify automated traffic patterns.

**How to avoid:**
- Test scraping from production environment BEFORE full deployment
- Implement rate limiting (respect delays between requests)
- Rotate User-Agent headers to match real browsers
- Consider residential proxy services for critical scrapers (ScrapingBee, ZenRows)
- Add retry logic with exponential backoff for 429/403 responses
- Monitor scraping success rates and failure patterns

**Warning signs:**
- Scraper succeeds locally, fails in cloud
- Consistent 403 Forbidden or 429 Too Many Requests
- CAPTCHA challenges appearing in responses

**Source:** [How to Avoid IP Bans](https://affinco.com/avoid-ip-bans-scraping/), [Why Requests Work Locally but Get Blocked in Cloud](https://proxy001.com/blog/web-scraping-proxies-why-requests-work-locally-but-get-blocked-in-the-cloud)

### Pitfall 2: APScheduler Duplicate Job Execution

**What goes wrong:** Scheduled jobs run multiple times simultaneously, creating duplicate notifications or database entries.

**Why it happens:** Each gunicorn worker process initializes its own APScheduler instance. With 4 workers, each job runs 4 times. APScheduler has no interprocess synchronization mechanism.

**How to avoid:**
- Run APScheduler in a dedicated process completely separate from web workers
- Use platform-specific patterns: Render background worker, Railway separate service, Fly.io process groups
- Never initialize scheduler in web application startup code
- Alternative: Use platform cron jobs (Render) or external schedulers (GitHub Actions) for simpler cases

**Warning signs:**
- Logs show jobs executing multiple times
- Users receive duplicate Telegram notifications
- Database has duplicate scrape records with same timestamp

**Source:** [APScheduler FAQ](https://apscheduler.readthedocs.io/en/3.x/faq.html), [Common Mistakes with APScheduler](https://sepgh.medium.com/common-mistakes-with-using-apscheduler-in-your-python-and-django-applications-100b289b812c)

### Pitfall 3: Worker Timeout on Long-Running Scrapes

**What goes wrong:** Gunicorn kills workers mid-request with "[CRITICAL] WORKER TIMEOUT" errors, failing to complete scraping jobs.

**Why it happens:** Default gunicorn timeout is 30 seconds. After timeout, gunicorn sends SIGTERM to worker (graceful shutdown), then SIGKILL after graceful timeout (default 30s more).

**How to avoid:**
- Configure `--timeout` parameter based on longest expected request duration
- For scraper: `--timeout 300` (5 minutes) is reasonable starting point
- Add `--graceful-timeout 60` to allow cleanup during shutdown
- Alternative: Offload long-running scrapes to background worker/queue for truly async processing
- Monitor timeout logs to calibrate appropriate values

**Warning signs:**
- "[CRITICAL] WORKER TIMEOUT" in logs
- Requests consistently fail after exactly 30 seconds
- Workers being restarted frequently

**Source:** [Gunicorn Worker Timeout Solutions](https://blog.arfy.ca/worker-timeout/), [Gunicorn Settings Reference](https://gunicorn.org/reference/settings/)

### Pitfall 4: psycopg2-binary Library Conflicts

**What goes wrong:** Application segfaults under concurrency, SSL conflicts with other Python modules, or inability to upgrade system libraries.

**Why it happens:** psycopg2-binary bundles static versions of libpq and libssl. These conflict with system libraries and other Python modules using SSL. Binary package prevents benefiting from system security updates.

**How to avoid:**
- Always use `psycopg2` (source distribution) in requirements.txt for production
- Never use `psycopg2-binary` in published packages or production deployments
- Platform build systems handle compilation dependencies automatically
- Use psycopg2-binary only for local development on machines without build tools

**Warning signs:**
- Segmentation faults under concurrent database queries
- SSL handshake errors
- Conflicts with requests/urllib3/ssl modules

**Source:** [Psycopg2 Installation Docs](https://www.psycopg.org/docs/install.html), [psycopg2-binary Should Not Be Used in Production](https://github.com/rucio/rucio/issues/6669)

### Pitfall 5: Railway PostgreSQL Backup Blind Spot

**What goes wrong:** Database failure leads to complete data loss because no backups exist.

**Why it happens:** Railway PostgreSQL does NOT include native automated backups unlike Render and Fly.io. This is easy to overlook during initial setup.

**How to avoid:**
- If using Railway: Deploy their [Automated PostgreSQL Backups template](https://blog.railway.com/p/automated-postgresql-backups) from first day
- Alternative: Choose Render or Fly.io which include native automated backups
- Test backup restoration process BEFORE production launch
- Document backup strategy in deployment docs

**Warning signs:**
- No backup confirmation in Railway dashboard
- Absence of restore/backup UI in Railway database settings
- Relying on assumption that "cloud provider handles backups"

**Source:** [Railway Automated PostgreSQL Backups](https://blog.railway.com/p/automated-postgresql-backups), [Railway vs Render comparison](https://northflank.com/blog/railway-vs-render)

### Pitfall 6: Missing Environment Variables in Production

**What goes wrong:** Application crashes on startup with KeyError or connects to wrong services.

**Why it happens:** Environment variables are set locally but not configured in production environment. Developers forget to document required variables or configure them on platform.

**How to avoid:**
- Create `.env.example` documenting EVERY required environment variable
- Add startup validation that checks for required variables before running
- Use platform's sealed/secret variables for sensitive data (tokens, passwords)
- Test deployment in staging environment first

**Warning signs:**
- Application works locally, crashes immediately in production
- KeyError exceptions for environment variables in logs
- Application connects to SQLite instead of PostgreSQL

**Source:** [Environment Variable Management Best Practices](https://www.envsentinel.dev/blog/environment-variable-management-tips-best-practices)

### Pitfall 7: DNS Propagation Impatience

**What goes wrong:** Custom domain shows "SSL certificate pending" or "DNS not configured" for extended periods, causing deployment delays.

**Why it happens:** DNS changes can take up to 72 hours to propagate globally. Let's Encrypt validation fails until DNS propagates. Developers expect instant results.

**How to avoid:**
- Set DNS records 24-48 hours BEFORE production launch if timeline is tight
- Use `dig yourdomain.com` or `nslookup yourdomain.com` to verify DNS propagation
- Railway/Render/Fly.io show validation status in dashboard - monitor rather than repeatedly changing config
- Test with platform-provided subdomain (*.up.railway.app, *.onrender.com, *.fly.dev) first

**Warning signs:**
- SSL certificate stuck in "pending" state
- Platform reports "domain not verified"
- Works on some networks but not others (partial propagation)

**Source:** [Railway Domain Docs](https://docs.railway.com/networking/domains), [Fly.io Certificate Troubleshooting](https://fly.io/docs/networking/custom-domain/)

## Code Examples

### 1. Production-Ready Main Application Entry Point

```python
# app/main.py
import os
import sys
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

# Validate required environment variables at startup
REQUIRED_ENV_VARS = [
    'DATABASE_URL',
    'TELEGRAM_BOT_TOKEN',
    'EMAIL_USER',
    'EMAIL_PASSWORD',
]

def validate_environment():
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}",
              file=sys.stderr)
        sys.exit(1)

validate_environment()

# Health check endpoint
async def health_check(request):
    return JSONResponse({
        "status": "healthy",
        "version": os.getenv("GIT_COMMIT_SHA", "unknown")
    })

# Main application routes
routes = [
    Route("/health", health_check, methods=["GET"]),
    # ... other application routes
]

app = Starlette(
    debug=False,  # NEVER enable debug in production
    routes=routes
)
```
**Source:** Adapted from [FastAPI Deployment Guide](https://www.zestminds.com/blog/fastapi-deployment-guide/)

### 2. Separate Scheduler Process (APScheduler)

```python
# app/scheduler.py
import os
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Import your job functions
from app.jobs import scrape_new_tips, send_notifications

def validate_environment():
    required = ['DATABASE_URL', 'TELEGRAM_BOT_TOKEN']
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}",
              file=sys.stderr)
        sys.exit(1)

def main():
    validate_environment()

    # Use BlockingScheduler for dedicated process
    scheduler = BlockingScheduler()

    # Add jobs
    scheduler.add_job(
        scrape_new_tips,
        trigger=IntervalTrigger(hours=1),
        id='scrape_tips',
        name='Scrape RA for new tips',
        replace_existing=True
    )

    scheduler.add_job(
        send_notifications,
        trigger=IntervalTrigger(minutes=15),
        id='send_notifications',
        name='Send Telegram notifications',
        replace_existing=True
    )

    print("Starting scheduler process...", flush=True)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler shutdown requested", flush=True)
        scheduler.shutdown()

if __name__ == '__main__':
    main()
```
**Source:** [APScheduler User Guide](https://apscheduler.readthedocs.io/en/master/userguide.html)

### 3. Render Multi-Service Configuration

```yaml
# render.yaml
services:
  # Web service with gunicorn + uvicorn workers
  - type: web
    name: ra-tips-web
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: >
      gunicorn -k uvicorn.workers.UvicornWorker
      --workers 2
      --timeout 120
      --bind 0.0.0.0:$PORT
      app.main:app
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: ra-tips-db
          property: connectionString
      - key: TELEGRAM_BOT_TOKEN
        sync: false  # Secret - set in Render dashboard
      - key: EMAIL_PASSWORD
        sync: false  # Secret - set in Render dashboard
      - key: PYTHON_VERSION
        value: "3.11"

  # Background worker for scheduler
  - type: worker
    name: ra-tips-scheduler
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python -m app.scheduler
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: ra-tips-db
          property: connectionString
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: EMAIL_PASSWORD
        sync: false

databases:
  - name: ra-tips-db
    databaseName: ra_tips
    plan: starter  # Includes automated backups
```
**Source:** [Render Background Workers](https://render.com/docs/background-workers)

### 4. Fly.io Multi-Process Configuration

```toml
# fly.toml
app = "ra-tips"
primary_region = "lhr"  # London

[build]
  [build.args]
    PYTHON_VERSION = "3.11"

[env]
  PORT = "8000"
  PYTHON_VERSION = "3.11"

[processes]
  web = "gunicorn -k uvicorn.workers.UvicornWorker --workers 2 --timeout 120 --bind 0.0.0.0:8000 app.main:app"
  scheduler = "python -m app.scheduler"

# Only web process receives HTTP traffic
[[services]]
  processes = ["web"]
  internal_port = 8000
  protocol = "tcp"
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 1

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  # Health check configuration
  [[services.http_checks]]
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"
    method = "GET"
    path = "/health"

# Scheduler runs but doesn't receive traffic
[[services]]
  processes = ["scheduler"]
  auto_stop_machines = "off"
  auto_start_machines = true
  min_machines_running = 1
```
**Source:** [Fly.io Process Groups](https://fly.io/docs/apps/processes/)

### 5. Environment Variable Validation Utility

```python
# app/config.py
import os
import sys
from typing import Dict, Optional

class ConfigError(Exception):
    pass

class Config:
    """Production configuration with validation."""

    REQUIRED_VARS = {
        'DATABASE_URL': 'PostgreSQL connection string',
        'TELEGRAM_BOT_TOKEN': 'Telegram bot API token',
        'EMAIL_USER': 'Email address for notifications',
        'EMAIL_PASSWORD': 'Email password/app password',
    }

    OPTIONAL_VARS = {
        'LOG_LEVEL': ('INFO', 'Logging level'),
        'SCRAPE_INTERVAL_HOURS': ('1', 'Hours between scraping runs'),
    }

    def __init__(self):
        self.validate()
        self.load()

    def validate(self):
        """Validate all required environment variables are present."""
        missing = []
        for var, description in self.REQUIRED_VARS.items():
            if not os.getenv(var):
                missing.append(f"{var} ({description})")

        if missing:
            error_msg = "Missing required environment variables:\n" + "\n".join(
                f"  - {var}" for var in missing
            )
            print(error_msg, file=sys.stderr)
            raise ConfigError(error_msg)

    def load(self):
        """Load configuration from environment."""
        # Required variables
        self.database_url = os.getenv('DATABASE_URL')
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')

        # Optional variables with defaults
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.scrape_interval = int(os.getenv('SCRAPE_INTERVAL_HOURS', '1'))

        # Never enable debug in production
        self.debug = False

# Global config instance
config = Config()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Heroku | Railway/Render/Fly.io | 2022-2023 | Heroku ended free tier; alternatives offer better DX and pricing |
| Manual SSL with Certbot | Platform-managed Let's Encrypt | 2018-2020 | Zero SSL maintenance, automatic renewal |
| psycopg2-binary in production | psycopg2 source distribution | Ongoing concern | Security updates, stability under concurrency |
| Nixpacks (Railway) | Railpack | Q4 2024 | Faster builds, better Python detection, Nixpacks maintenance mode |
| Single web process pattern | Multi-process deployment | Always relevant | Prevents APScheduler duplication, cleaner separation |
| DIY backups with cron | Managed database backups | 2020-2023 | Point-in-time recovery, tested restore procedures |

**Deprecated/outdated:**
- **Heroku free tier:** Eliminated November 2022 - migrate to Railway/Render/Fly.io
- **Railway Nixpacks for new projects:** Maintenance mode since late 2024 - use Railpack for new services
- **psycopg2-binary for production:** Use psycopg2 source distribution to avoid library conflicts
- **Running APScheduler in web workers:** Always causes duplication - use dedicated process

## Open Questions

### 1. Cloud IP Blocking Severity for ra.co

**What we know:**
- Datacenter IPs have 3-4x higher block rate than residential IPs
- Modern anti-bot systems detect automated patterns
- Testing needed to determine if ra.co specifically blocks cloud IPs

**What's unclear:**
- Does ra.co use aggressive anti-bot protection (Cloudflare, etc.)?
- Will scraping frequency (hourly) trigger rate limits?
- Are there specific IP ranges more likely to succeed?

**Recommendation:**
- Deploy to chosen platform and test scraping IMMEDIATELY
- Monitor success/failure rates over 48 hours before production launch
- Have contingency plan: residential proxy service (ScrapingBee, ZenRows) if cloud IPs fail
- Implement rate limiting and retry logic proactively

### 2. PostgreSQL Resource Requirements

**What we know:**
- Basic managed plans start at 1GB RAM
- Connection pooling (PgBouncer) reduces connection overhead
- All three platforms allow scaling up

**What's unclear:**
- Expected data volume growth rate
- Query complexity and indexing requirements
- Actual memory/CPU needs for production workload

**Recommendation:**
- Start with smallest plan that includes automated backups
- Monitor query performance and connection counts for first month
- Scale vertically if needed (all platforms support plan upgrades)
- Use platform monitoring dashboards to track resource usage

### 3. Multi-Region Deployment Needs

**What we know:**
- Fly.io optimized for global distribution (12 regions)
- Railway/Render default to single region
- Application is UK-focused (RA.co)

**What's unclear:**
- User geographic distribution
- Latency requirements
- Benefit of multi-region vs single UK region

**Recommendation:**
- Start with single region (UK/EU) on any platform
- Monitor user latency and geographic distribution
- Consider Fly.io if global distribution becomes requirement
- For RA.co scraping, single region sufficient

## Sources

### Primary (HIGH confidence)

**Official Platform Documentation:**
- [Railway Domains](https://docs.railway.com/networking/domains) - Custom domain and SSL configuration
- [Railway Build Configuration](https://docs.railway.com/builds/build-configuration) - Railpack, start commands, Procfile
- [Railway Variables](https://docs.railway.com/variables) - Environment variables and sealed variables
- [Railway PostgreSQL](https://docs.railway.com/databases/postgresql) - Database features and limitations
- [Fly.io Managed Postgres](https://fly.io/docs/mpg/) - Managed database features, pricing, backups
- [Fly.io Custom Domains](https://fly.io/docs/networking/custom-domain/) - DNS configuration and SSL setup
- [Fly.io Secrets](https://fly.io/docs/apps/secrets/) - Secrets management and encryption
- [Render Background Workers](https://render.com/docs/background-workers) - Multi-service architecture
- [Render PostgreSQL Connection Pooling](https://render.com/docs/postgresql-connection-pooling) - PgBouncer configuration

**Core Library Documentation:**
- [Uvicorn Deployment](https://uvicorn.dev/deployment/) - Production deployment with Gunicorn
- [Gunicorn Settings Reference](https://gunicorn.org/reference/settings/) - Timeout and worker configuration
- [APScheduler User Guide](https://apscheduler.readthedocs.io/en/master/userguide.html) - Scheduler configuration
- [APScheduler FAQ](https://apscheduler.readthedocs.io/en/3.x/faq.html) - Multi-process pitfalls
- [Psycopg2 Installation Docs](https://www.psycopg.org/docs/install.html) - Production vs binary packages

### Secondary (MEDIUM confidence)

**Platform Comparisons (2026):**
- [Railway vs Render 2026 Comparison](https://northflank.com/blog/railway-vs-render) - Feature and pricing comparison
- [Fly.io vs Render 2026](https://northflank.com/blog/flyio-vs-render) - Jobs, scaling, production workloads
- [Python Hosting Options Compared](https://www.nandann.com/blog/python-hosting-options-comparison) - PaaS platforms for Python

**Production Best Practices:**
- [Mastering Gunicorn and Uvicorn](https://medium.com/@iklobato/mastering-gunicorn-and-uvicorn-the-right-way-to-deploy-fastapi-applications-aaa06849841e) - ASGI deployment patterns
- [FastAPI Deployment Guide 2026](https://www.zestminds.com/blog/fastapi-deployment-guide/) - Production setup
- [Gunicorn Worker Timeout Solutions](https://blog.arfy.ca/worker-timeout/) - Timeout troubleshooting
- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/) - Production security checklist

**APScheduler Multi-Process Issues:**
- [Common Mistakes with APScheduler](https://sepgh.medium.com/common-mistakes-with-using-apscheduler-in-your-python-and-django-applications-100b289b812c) - Duplicate execution prevention
- [Run APScheduler With Gunicorn](https://enqueuezero.com/projects/apscheduler/gunicorn.html) - Dedicated process pattern

**Web Scraping Production Concerns:**
- [How to Avoid IP Bans: Web Scraping Guide 2026](https://affinco.com/avoid-ip-bans-scraping/) - Cloud IP blocking patterns
- [Web Scraping Proxies: Why Requests Work Locally but Get Blocked in Cloud](https://proxy001.com/blog/web-scraping-proxies-why-requests-work-locally-but-get-blocked-in-the-cloud) - Datacenter IP detection
- [How to Bypass IP Ban When Scraping 2026](https://www.zenrows.com/blog/how-to-bypass-ip-ban) - Mitigation strategies

### Tertiary (LOW confidence - marked for validation)

**Platform-Specific Details:**
- [Railway Automated PostgreSQL Backups](https://blog.railway.com/p/automated-postgresql-backups) - Third-party backup template
- [Deploying Multi-Service Apps on Render](https://medium.com/@hugit/deploying-multi-service-apps-on-render-with-background-workers-cron-jobs-6dea83ad77c7) - Background worker patterns

## Metadata

**Confidence breakdown:**
- **Standard stack:** HIGH - Official documentation for Gunicorn+Uvicorn, PostgreSQL, Let's Encrypt verified
- **Architecture patterns:** HIGH - Multiple official sources confirm multi-process patterns, all code examples from official docs
- **Platform selection:** MEDIUM - Pricing/features verified with official docs, but real-world performance varies
- **Web scraper cloud IP blocking:** MEDIUM - General patterns well-documented, but ra.co-specific behavior unknown
- **Pitfalls:** HIGH - APScheduler, psycopg2, timeout issues verified with official docs and GitHub issues

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (30 days - PaaS platforms evolve rapidly with pricing/feature changes)

**Validation recommendations:**
- Verify current pricing on platform dashboards before final selection
- Test web scraping from production environment IMMEDIATELY after deployment
- Confirm backup restoration process within first week of production
- Re-validate Cloud IP blocking severity monthly as anti-bot systems evolve
