# Requirements: Rave Tracker v3.0

**Defined:** 2026-02-10
**Core Value:** Users never miss events from artists, venues, or promoters they care about

## v3.0 Requirements

Requirements for Production Deployment & Hosting milestone.

### Database & Infrastructure

- [ ] **DB-01**: Application connects to PostgreSQL via DATABASE_URL environment variable
- [ ] **DB-02**: DATABASE_URL parsing handles both postgres:// and postgresql:// prefixes interchangeably
- [ ] **DB-03**: All raw SQL queries work against PostgreSQL (parameter placeholders, boolean types, serial IDs)
- [ ] **DB-04**: Connection pooling configured for production load (pool_size appropriate for worker count)
- [ ] **DB-05**: Database schema migrations run successfully against PostgreSQL

### Production Server

- [ ] **SRV-01**: Application runs under gunicorn with uvicorn workers (multi-process)
- [ ] **SRV-02**: Scheduler runs as a separate process (not duplicated per worker)
- [ ] **SRV-03**: Health check endpoint (/health) returns database connectivity status
- [ ] **SRV-04**: Application handles graceful shutdown (in-flight requests complete before exit)

### Environment & Secrets

- [ ] **ENV-01**: All secrets configured via environment variables (DATABASE_URL, SMTP credentials, CSRF secret, Telegram bot token, SECRET_KEY)
- [ ] **ENV-02**: No hardcoded secrets remain in config.yaml or committed files
- [ ] **ENV-03**: .env.example documents all required environment variables

### Scraper Resilience

- [ ] **SCRAPE-01**: Scraper implements exponential backoff on 403/429/5xx responses
- [ ] **SCRAPE-02**: Scraper rotates User-Agent strings across requests
- [ ] **SCRAPE-03**: Scraper handles extended API outages gracefully (circuit breaker, no crash)
- [ ] **SCRAPE-04**: Scraper logs response status codes for monitoring (detect blocking patterns)

### Hosting & SSL

- [ ] **HOST-01**: Application deployed to evaluated and selected hosting provider
- [ ] **HOST-02**: Provider-managed PostgreSQL with automated backups
- [ ] **HOST-03**: Automated HTTPS/SSL (Let's Encrypt or provider-managed)
- [ ] **HOST-04**: Custom domain configured with DNS records
- [ ] **HOST-05**: Git-push deployment pipeline configured

### Observability

- [ ] **OBS-01**: Structured JSON logging with request IDs and status codes
- [ ] **OBS-02**: Error tracking integrated (Sentry or equivalent)
- [ ] **OBS-03**: Scraper health visible (success/failure rate, last fetch time)
- [ ] **OBS-04**: Alert on 3+ consecutive scraper fetch failures

## v3.1+ Candidates

Deferred to future milestones.

- **SCRAPE-05**: Proxy service integration (if cloud IP blocking becomes persistent)
- **OBS-05**: APM/performance monitoring (p50/p95/p99 latency tracking)
- **OBS-06**: Prometheus metrics endpoint (/metrics)
- **DEPLOY-01**: Blue-green deployments (zero-downtime deploys)
- **SEC-08**: Login attempt notifications to user
- **SEC-09**: Two-factor authentication (TOTP)
- **ACCT-09**: Account export (GDPR data portability)

## Out of Scope

Explicitly excluded from this milestone.

| Feature | Reason |
|---------|--------|
| Docker/Kubernetes | Over-engineering for single-server deployment with predictable load |
| Auto-scaling | Event tracker has predictable load; fixed-size deployment sufficient |
| Read replicas | Not needed at current scale |
| Proxy rotation | ra.co API is public; start conservative, add only if blocked |
| Real-time WebSocket updates | Scheduler runs every 6h; no user demand for live updates |
| SQLAlchemy ORM migration | Raw SQL works; ORM migration is high-effort with low payoff for this codebase |
| Internal module renaming | Keep ra-tracker/ra_tracker internally (decided v2.2) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DB-01 | TBD | Pending |
| DB-02 | TBD | Pending |
| DB-03 | TBD | Pending |
| DB-04 | TBD | Pending |
| DB-05 | TBD | Pending |
| SRV-01 | TBD | Pending |
| SRV-02 | TBD | Pending |
| SRV-03 | TBD | Pending |
| SRV-04 | TBD | Pending |
| ENV-01 | TBD | Pending |
| ENV-02 | TBD | Pending |
| ENV-03 | TBD | Pending |
| SCRAPE-01 | TBD | Pending |
| SCRAPE-02 | TBD | Pending |
| SCRAPE-03 | TBD | Pending |
| SCRAPE-04 | TBD | Pending |
| HOST-01 | TBD | Pending |
| HOST-02 | TBD | Pending |
| HOST-03 | TBD | Pending |
| HOST-04 | TBD | Pending |
| HOST-05 | TBD | Pending |
| OBS-01 | TBD | Pending |
| OBS-02 | TBD | Pending |
| OBS-03 | TBD | Pending |
| OBS-04 | TBD | Pending |

**Coverage:**
- v3.0 requirements: 25 total
- Mapped to phases: 0
- Unmapped: 25

---
*Requirements defined: 2026-02-10*
*Last updated: 2026-02-10 after initial definition*
