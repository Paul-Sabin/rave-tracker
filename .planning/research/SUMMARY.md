# Project Research Summary

**Project:** Rave Tracker v3.0 - Production Deployment & Hosting
**Domain:** FastAPI application deployment with GraphQL API scraping
**Researched:** 2026-02-11
**Confidence:** MEDIUM

## Executive Summary

This research synthesizes deployment requirements for transitioning a multi-user FastAPI event tracker from local development (SQLite, single-process) to production hosting (PostgreSQL, multi-worker). The application scrapes ra.co's GraphQL API every 6 hours and serves a mobile-friendly dashboard to multiple users with per-user notification preferences.

**Recommended approach:** Managed platform deployment (Railway, Render, or Fly.io) with provider-managed PostgreSQL and automatic SSL. This approach minimizes infrastructure complexity while addressing critical production requirements: database connection pooling, multi-worker ASGI server configuration, graceful shutdown, health checks, and environment-based secret management. The primary technical risk is APScheduler running in multiple worker processes, causing 4x duplicate scraping jobs and notification spam - this must be resolved before multi-worker deployment.

**Key mitigation strategy:** Deploy scheduler and web server as separate processes (scheduler runs once, web server scales to N workers), implement exponential backoff for GraphQL API failures to prevent cloud IP blocking, and migrate all secrets from config.yaml to environment variables before any cloud deployment. The production stack (Python/FastAPI/PostgreSQL) is well-established with documented patterns, giving this migration high success probability if critical pitfalls are addressed in correct order.

## Key Findings

### Current Stack (from .planning/codebase/STACK.md)

**Production-ready components:**
- Python 3.11+ with FastAPI 0.109.0+ and Uvicorn 0.27.0+
- Argon2id password hashing, CSRF protection, rate limiting (slowapi)
- APScheduler 3.10.0+ for background jobs
- Jinja2 templates, Tailwind CSS v4 CDN
- Email (fastapi-mail + SMTP) and Telegram (python-telegram-bot 20.0+) notifications
- Configuration via YAML with .env overrides (python-dotenv)

**Components requiring production upgrades:**
- Database: SQLite → PostgreSQL (with connection pooling)
- Server: Single uvicorn process → Gunicorn with 4-9 uvicorn workers
- Secrets: config.yaml hardcoded → environment variables
- Architecture: Scheduler embedded in web workers → separate scheduler process

### Expected Features (from FEATURES.md)

**Must have (table stakes for production v1):**
- Multi-worker ASGI server (gunicorn + uvicorn workers) - utilize multiple cores, automatic restarts
- Environment-based configuration - DATABASE_URL, SMTP credentials, Telegram token, CSRF secrets
- PostgreSQL with connection pooling - prevent connection exhaustion (pool_size=10, max_overflow=20)
- HTTPS/SSL with custom domain - Let's Encrypt via Certbot or provider-managed
- Health check endpoint - `/health` returns database connectivity status
- Process supervision - systemd or provider-managed auto-restart
- GraphQL retry logic - exponential backoff for 429/503 responses
- Database backups - automated daily backups (provider-managed or pg_dump cron)
- Basic structured logging - JSON logs with request IDs, status codes, latency

**Should have (add after validation):**
- Error tracking (Sentry) - trigger when first production exception is hard to debug
- APM - trigger when slow page loads or unclear bottlenecks
- Separate scheduler process - trigger when scheduler jobs interfere with web latency
- Circuit breaker for API failures - trigger if ra.co API has extended outage (>10 min)
- Metrics endpoint - Prometheus-compatible `/metrics` for request counts, latency, job status

**Defer (v2+ or when specific problems emerge):**
- Blue-green deployments - defer until downtime during deploys becomes user complaint
- Read replicas - defer until database reads slow under load
- Request/response caching - defer until repeated dashboard queries cause performance issues

**Anti-features (commonly requested, problematic for this domain):**
- User-Agent rotation for every request - GraphQL APIs don't fingerprint like anti-bot systems
- Proxy rotation - ra.co API is public; IP blocking unlikely with 1s rate limiting
- Docker/Kubernetes for single-server - over-engineering for predictable load
- Real-time scraping via WebSockets - scheduler runs every 6 hours, no user demand for live updates
- Auto-scaling - event tracker has predictable load, fixed-size deployment sufficient

### Architecture Approach (from .planning/codebase/ARCHITECTURE.md)

**Current architecture (layered service pattern):**
- API Layer: GraphQL client for ra.co with rate limiting (1s between requests)
- Services Layer: Fetcher (event retrieval), Matcher (rule evaluation), Notifier (Telegram/email)
- Web Layer: FastAPI routes + Jinja2 templates for dashboard
- Scheduler Layer: APScheduler background jobs (fetch every 6 hours)
- Database Layer: SQLite with domain models (Rule, Event, User, Session, Notification)

**Production architecture changes required:**
1. **Scheduler separation:** Move APScheduler from web worker to dedicated process
   - Problem: Currently starts in every worker (4 workers = 4x duplicate jobs)
   - Solution: Run scheduler as separate systemd service, share PostgreSQL database

2. **Database migration:** SQLite → PostgreSQL
   - Schema changes: INTEGER AUTOINCREMENT → SERIAL, boolean 0/1 → TRUE/FALSE
   - Query syntax: `?` placeholders → `%s`, add connection pooling
   - Impact: All 15 Python modules using database.py need verification

3. **Multi-worker web server:** Single uvicorn → gunicorn with uvicorn workers
   - Formula: (2 × CPU_cores) + 1 workers (e.g., 4-core VPS → 9 workers)
   - Requires: PostgreSQL connection pool sized for workers × concurrent requests

4. **Reverse proxy:** Add Nginx/Caddy for SSL termination and static file serving

### Critical Pitfalls (from PITFALLS.md)

**1. APScheduler runs in every worker process (CRITICAL)**
- Impact: 4 workers = 4x duplicate scraping jobs, 4x notifications, database race conditions
- Phase: Must fix in Phase 1 (Production Infrastructure Setup)
- Solution: Deploy scheduler and web as separate processes OR use worker ID detection
- Warning signs: Logs show "Scheduled fetch job" 4x at startup, users receive 4x duplicate Telegram messages

**2. SQLite database locking under multi-worker load (CRITICAL)**
- Impact: "database is locked" errors, 5-second timeouts, failed user actions during fetch operations
- Phase: Must fix in Phase 1 (Production Infrastructure Setup)
- Solution: Migrate to PostgreSQL with connection pooling before multi-worker deployment
- Warning signs: OperationalError timeouts, 500 errors when scheduler runs

**3. Silent SQL syntax failures after PostgreSQL migration (CRITICAL)**
- Impact: Queries work in SQLite dev, fail in PostgreSQL production (parameter placeholders, boolean types, AUTOINCREMENT)
- Phase: Must verify in Phase 1 (Production Infrastructure Setup)
- Solution: Test ALL queries against PostgreSQL, consider SQLAlchemy ORM, update schema with SERIAL/BOOLEAN types
- Warning signs: Type errors on `is_active` column, INSERT returns no ID, foreign key constraint failures

**4. Scraper blocked by cloud provider IP reputation (HIGH)**
- Impact: Cloud IP addresses (AWS, GCP, DigitalOcean) hit stricter rate limits, return 403/429/CAPTCHA
- Phase: Monitor in Phase 1, mitigate in Phase 2 (Scraper Resilience)
- Solution: Conservative rate limiting (2-5s between requests), exponential backoff, monitoring for 403/429 responses
- Warning signs: Sudden GraphQL errors after cloud deployment, 403/429 status codes, empty responses with 200 status

**5. Secrets exposed in version control (CRITICAL - SECURITY)**
- Impact: config.yaml contains production secrets (bot token, SMTP password, secret_key) in plaintext, committed to git
- Phase: Must fix in Phase 0 (Pre-deployment) before ANY cloud hosting
- Solution: Move ALL secrets to .env, add to .gitignore, rotate ALL exposed secrets, use cloud secret management
- Warning signs: Secrets visible in GitHub history, container images contain .env files, unexpected API usage

**6. No health check endpoint (HIGH)**
- Impact: Load balancers can't detect failures, send traffic to crashed instances, no automated recovery
- Phase: Must add in Phase 1 (Production Infrastructure Setup)
- Solution: Add `/health` endpoint that tests database connectivity, return 503 on failure
- Warning signs: Traffic sent before app ready, degraded instances stay in rotation, manual restarts required

**7. No graceful shutdown (MEDIUM)**
- Impact: SIGTERM exits immediately via sys.exit(0), aborting in-flight HTTP requests mid-processing
- Phase: Must fix in Phase 1 (Production Infrastructure Setup)
- Solution: Remove manual signal handlers, use FastAPI lifespan events, configure uvicorn timeout_graceful_shutdown=30
- Warning signs: "Connection reset by peer" during deployments, partial data in database after restarts

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 0: Pre-Deployment Security (MANDATORY - DO NOT SKIP)
**Rationale:** Secrets currently hardcoded in config.yaml (bot token, SMTP password, secret_key). MUST be externalized before ANY cloud deployment to prevent security breach.

**Delivers:**
- All secrets moved to .env file (.gitignored)
- config.yaml uses ${VAR} placeholders or removes secrets entirely
- ALL exposed secrets rotated (new bot token, new SMTP password, new secret_key)
- .env.example created for documentation

**Blocks:** All subsequent phases - cannot proceed to cloud deployment until secrets are secure

**Verification:**
- [ ] Git history scan shows no secrets in config.yaml
- [ ] Application starts using environment variables only
- [ ] Old secrets invalidated and regenerated

---

### Phase 1: Production Infrastructure Setup
**Rationale:** Core production requirements must be in place before multi-worker deployment. SQLite → PostgreSQL migration is prerequisite for multi-worker server. APScheduler separation prevents 4x duplicate jobs. Health checks enable load balancer integration.

**Delivers:**
- PostgreSQL migration with connection pooling
- Multi-worker ASGI server (gunicorn + uvicorn workers)
- Separate scheduler process (web workers use --no-scheduler flag)
- Health check endpoint (/health with DB connectivity test)
- Graceful shutdown (lifespan events, timeout_graceful_shutdown=30)
- Process supervision (systemd or provider-managed)
- Environment variable management (DATABASE_URL, all secrets)

**Addresses (from FEATURES.md):**
- Multi-worker ASGI server (table stakes)
- PostgreSQL with connection pooling (table stakes)
- Health check endpoint (table stakes)
- Environment-based configuration (table stakes)
- Process supervision (table stakes)

**Avoids (from PITFALLS.md):**
- Pitfall 1: APScheduler duplicates (separate scheduler process)
- Pitfall 2: SQLite locking (PostgreSQL migration)
- Pitfall 3: SQL syntax failures (query verification against PostgreSQL)
- Pitfall 6: No health checks (add /health endpoint)
- Pitfall 7: No graceful shutdown (lifespan events)

**Complexity:** HIGH - Database migration touches all 15 modules, multi-worker config requires scheduler redesign

**Research flags:**
- STANDARD PATTERNS: PostgreSQL migration, gunicorn+uvicorn, health checks are well-documented
- VERIFY: All raw SQL queries tested against PostgreSQL (parameter placeholders, boolean types, AUTOINCREMENT)

---

### Phase 2: Hosting & SSL Deployment
**Rationale:** Once infrastructure components are production-ready, deploy to managed platform (Railway, Render, or Fly.io) with provider-managed PostgreSQL and automatic SSL. Managed platforms handle certificate renewal, load balancing, and process supervision with minimal configuration.

**Delivers:**
- Hosting provider evaluation and selection (Railway vs Render vs Fly.io)
- Provider-managed PostgreSQL database (automated backups included)
- Automatic HTTPS/SSL (Let's Encrypt via provider)
- Custom domain configuration (DNS A/CNAME records)
- Production deployment pipeline (git push to deploy)
- Basic structured logging (JSON format, request IDs)

**Addresses (from FEATURES.md):**
- HTTPS/SSL with custom domain (table stakes)
- Database backups (table stakes)
- Basic structured logging (table stakes)

**Avoids (from PITFALLS.md):**
- Pitfall 5: Secrets exposed (environment variables via provider UI)

**Complexity:** LOW-MEDIUM - Managed platforms abstract infrastructure complexity

**Research flags:**
- STANDARD PATTERNS: Managed platform deployment is well-documented
- DECISION NEEDED: Choose hosting provider based on cost, PostgreSQL pricing, deployment UX

---

### Phase 3: Scraper Resilience
**Rationale:** Cloud deployment introduces new risk (IP reputation). ra.co may rate-limit or block data center IPs more aggressively than residential IPs. Add monitoring, retry logic, and exponential backoff to handle transient failures gracefully.

**Delivers:**
- Response status monitoring (detect 403/429 from ra.co)
- Exponential backoff for GraphQL errors (3 retries: 1s, 2s, 4s)
- Circuit breaker for extended API outages (stop retrying if API down >10 min)
- Scraper health dashboard (/status page for users)
- Error alerting for 3+ consecutive fetch failures

**Addresses (from FEATURES.md):**
- GraphQL retry logic (table stakes)
- Circuit breaker for API failures (should have)

**Avoids (from PITFALLS.md):**
- Pitfall 4: Cloud IP blocking (conservative rate limiting, exponential backoff)

**Complexity:** MEDIUM - Retry logic and circuit breaker require careful state management

**Research flags:**
- STANDARD PATTERNS: Exponential backoff is well-documented
- MONITOR: Cloud IP blocking severity depends on ra.co's specific policies (unknown)

---

### Phase 4: Observability & Monitoring
**Rationale:** After core deployment is stable, add observability to detect issues early and debug production problems. Sentry for error tracking, metrics for performance visibility, structured logging for troubleshooting.

**Delivers:**
- Error tracking integration (Sentry free tier)
- Metrics endpoint (Prometheus-compatible /metrics)
- Request latency tracking (p50, p95, p99)
- Scraper success rate monitoring
- Alert configuration (error spikes, fetch failures)

**Addresses (from FEATURES.md):**
- Error tracking (should have - trigger when first exception is hard to debug)
- Metrics endpoint (should have - quantitative data for optimization)

**Avoids (from PITFALLS.md):**
- Fetch errors fail silently (email/Telegram alert when 3+ consecutive failures)

**Complexity:** LOW-MEDIUM - Sentry integration is straightforward, metrics require instrumentation

**Research flags:**
- STANDARD PATTERNS: Sentry + FastAPI integration is well-documented

---

### Phase Ordering Rationale

- **Phase 0 must come first:** Security breach risk if secrets deployed to cloud in config.yaml
- **Phase 1 before Phase 2:** Can't deploy to production until database, multi-worker, and scheduler are production-ready
- **Phase 2 before Phase 3:** Need live deployment to detect cloud IP blocking (can't test with residential dev environment)
- **Phase 3 before Phase 4:** Scraper resilience prevents cascading failures; observability helps detect remaining issues
- **Phase 4 is iterative:** Monitoring reveals what additional observability is needed

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 1:** PostgreSQL migration query syntax - needs comprehensive testing against PostgreSQL to catch type coercion, placeholder syntax, AUTOINCREMENT differences
- **Phase 3:** Cloud IP blocking severity - unknown how aggressively ra.co rate-limits data center IPs; may need research during implementation if blocking occurs

**Phases with standard patterns (skip research-phase):**
- **Phase 0:** Secret management - established .env + .gitignore pattern
- **Phase 2:** Managed platform deployment - Railway/Render/Fly.io have comprehensive docs
- **Phase 4:** Sentry integration - official FastAPI integration documented

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (deployment) | MEDIUM | Core recommendations (multi-worker, pooling, SSL, env vars) are industry-standard (HIGH confidence). Specific tool versions based on training data through Jan 2025; ecosystem unlikely to change significantly in 1 year. |
| Features (production requirements) | HIGH | FastAPI production deployment features are well-established. Table stakes (health checks, connection pooling, HTTPS) are universal requirements. Should-have features (Sentry, APM) are de facto standards. |
| Architecture (migration approach) | MEDIUM-HIGH | SQLite → PostgreSQL migration pattern is well-documented (HIGH confidence). Scheduler separation strategy is clear from codebase analysis (HIGH confidence). Multi-worker uvicorn patterns established (HIGH confidence). Uncertainty around query syntax compatibility requires testing (MEDIUM confidence). |
| Pitfalls (deployment risks) | HIGH | APScheduler multi-worker issue is evident from code (HIGH confidence). SQLite locking is well-documented constraint (HIGH confidence). Secret exposure confirmed in config.yaml (HIGH confidence). Cloud IP blocking severity is estimated (MEDIUM confidence - depends on ra.co's undocumented policies). |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

**1. PostgreSQL query compatibility:**
- Gap: Current code uses raw SQL with SQLite-specific syntax (? placeholders, INTEGER booleans, AUTOINCREMENT). Unknown how many queries will break.
- Handle during planning: Create comprehensive test suite that runs all database operations against PostgreSQL. Identify breaking queries before migration.
- Mitigation: Consider SQLAlchemy ORM to abstract database differences (higher upfront cost, eliminates query compatibility issues).

**2. Cloud IP blocking severity:**
- Gap: Unknown how aggressively ra.co rate-limits or blocks data center IPs (AWS, GCP, DigitalOcean ASNs). No public documentation of their policies.
- Handle during planning: Deploy Phase 2, monitor for 7 days with existing 1s rate limiting. If 403/429 responses occur, implement Phase 3 resilience immediately.
- Mitigation: Start conservative (2-5s rate limiting, exponential backoff). Only escalate to proxy services if actually blocked.

**3. Hosting provider selection:**
- Gap: Cost/benefit tradeoff between Railway ($20/mo usage-based), Render ($40/mo fixed), Fly.io (variable), self-managed VPS ($27/mo but more operational work).
- Handle during planning: Evaluate based on PostgreSQL pricing, deployment UX, SSL management, backup automation. Prototype deployment on 2-3 providers before committing.
- Mitigation: All providers support DATABASE_URL pattern; switching later is feasible but requires DNS changes.

**4. Scheduler process supervision:**
- Gap: Unclear whether to use systemd (self-managed VPS), provider-managed process (Railway/Render), or celery beat (external scheduler).
- Handle during planning: Choose based on hosting provider. Managed platforms (Railway/Render) can run scheduler as separate service. VPS requires systemd service file.
- Mitigation: Start with simplest approach (separate process with --scheduler-only flag), add celery beat only if scheduler process crashes become issue.

## Sources

### Primary (HIGH confidence)

**Codebase analysis:**
- `C:\CLAUDE\ra-tips\.planning\codebase\STACK.md` - Current technology stack (Python 3.11, FastAPI 0.109.0, APScheduler, SQLite)
- `C:\CLAUDE\ra-tips\.planning\codebase\ARCHITECTURE.md` - Layered service architecture, APScheduler integration pattern, database schema
- `C:\CLAUDE\ra-tips\ra-tracker\config.yaml` - Configuration with hardcoded secrets (confirmed security issue)
- `C:\CLAUDE\ra-tips\ra-tracker\ra_tracker\main.py` - Scheduler startup logic (line 114-116), signal handlers (line 35-39)
- `C:\CLAUDE\ra-tips\ra-tracker\ra_tracker\database.py` - Raw SQL queries with SQLite-specific syntax
- `C:\CLAUDE\ra-tips\ra-tracker\ra_tracker\api\ra_client.py` - GraphQL client with rate limiting (MIN_REQUEST_INTERVAL = 1.0s)

**Research outputs:**
- `.planning/research/FEATURES.md` - Production deployment features (table stakes, differentiators, anti-features)
- `.planning/research/PITFALLS.md` - Critical pitfalls (APScheduler duplicates, SQLite locking, SQL syntax, secrets exposure)

### Secondary (MEDIUM confidence)

**Training data knowledge (no web search available):**
- FastAPI official documentation - Production deployment patterns, uvicorn worker configuration
- Gunicorn documentation - Worker class integration with uvicorn workers
- PostgreSQL documentation - Connection pooling, max_connections configuration
- SQLAlchemy documentation - Connection pool configuration patterns
- APScheduler documentation - Multi-worker deployment considerations
- Let's Encrypt documentation - Certificate automation patterns
- Industry best practices - Python web application deployment (2024-2025 standards)

**Confidence limitations:**
- Web search unavailable: Unable to verify 2026 ecosystem changes, current managed platform pricing, or ra.co's current rate limiting policies
- Specific tool versions based on training data through January 2025 (patterns unlikely to change significantly)
- Cloud IP blocking severity is estimated based on general scraping practices (no ra.co-specific verification)

---
*Research completed: 2026-02-11*
*Ready for roadmap: yes*
