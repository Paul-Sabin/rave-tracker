# Roadmap: Rave Tracker

## Milestones

- ✅ **v1.0 MVP** - Single-user event tracker (shipped 2026-01-19)
- ✅ **v2.0 Multi-User Support** - Phases 1-4 (shipped 2026-02-01)
- ✅ **v2.1 Security Hardening** - Phases 5-8 (shipped 2026-02-08)
- ✅ **v2.2 UX Polish & Branding** - Phase 9 (shipped 2026-02-10)
- 🚧 **v3.0 Production Deployment & Hosting** - Phases 10-14 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP - SHIPPED 2026-01-19</summary>

Single-user event tracker with fetching, rules, and notifications.

</details>

<details>
<summary>✅ v2.0 Multi-User Support (Phases 1-4) - SHIPPED 2026-02-01</summary>

### Phase 1: Database Foundation
**Goal**: Multi-user database schema ready
**Plans**: 2 plans

Plans:
- [x] 01-01: Database schema and models
- [x] 01-02: Migration and data seeding

### Phase 2: Authentication System
**Goal**: Users can securely access their accounts
**Plans**: 3 plans

Plans:
- [x] 02-01: Password infrastructure (Argon2id hashing)
- [x] 02-02: Login and registration routes
- [x] 02-03: Authentication UI (login, register, logout)

### Phase 3: Multi-Tenant Access Control
**Goal**: Users access only their own data
**Plans**: 4 plans

Plans:
- [x] 03-01: Session management and middleware
- [x] 03-02: User-scoped rules and events
- [x] 03-03: Privacy policy with explicit consent
- [x] 03-04: UI updates for multi-user mode

### Phase 4: User Notification Delivery
**Goal**: Users receive notifications via their chosen channels
**Plans**: 3 plans

Plans:
- [x] 04-01: Telegram bot linking and notifications
- [x] 04-02: Email notifications infrastructure
- [x] 04-03: Notification preferences and delivery logic

</details>

<details>
<summary>✅ v2.1 Security Hardening (Phases 5-8) - SHIPPED 2026-02-08</summary>

### Phase 5: Audit Foundation & CSRF Protection
**Goal**: Security events are logged and CSRF attacks are prevented
**Plans**: 2 plans

Plans:
- [x] 05-01: Audit logging infrastructure
- [x] 05-02: CSRF protection (Double Submit Cookie)

### Phase 6: Email Verification & Login Hardening
**Goal**: Only verified email addresses can receive notifications, login attempts are rate-limited
**Plans**: 3 plans

Plans:
- [x] 06-01: Login rate limiting and auth audit logging
- [x] 06-02: Verification token infrastructure
- [x] 06-03: Email verification flow UI

### Phase 7: Password Management
**Goal**: Users can reset forgotten passwords and change existing passwords
**Plans**: 3 plans

Plans:
- [x] 07-01: Password reset infrastructure
- [x] 07-02: Password reset flow (forgot password, reset email)
- [x] 07-03: Password change (settings, strength meter)

### Phase 8: Account Lifecycle & Admin Audit UI
**Goal**: Users can delete accounts with recovery grace period, admins can review audit logs
**Plans**: 3 plans

Plans:
- [x] 08-01: Soft delete and purge infrastructure
- [x] 08-02: Admin audit log UI
- [x] 08-03: Account deletion and recovery flows

</details>

<details>
<summary>✅ v2.2 UX Polish & Branding (Phase 9) - SHIPPED 2026-02-10</summary>

### Phase 9: UX Polish & Branding
**Goal**: Application presents as "Rave Tracker" with improved region selection UX
**Plans**: 3 plans

Plans:
- [x] 09-01: Rebrand all user-facing text to "Rave Tracker"
- [x] 09-02: UX improvements (toggle labels, region prompt, banner removal)
- [x] 09-03: Fix per-user local area storage (gap closure)

</details>

### 🚧 v3.0 Production Deployment & Hosting (In Progress)

**Milestone Goal:** Transition the app from local development to a live, publicly accessible host with PostgreSQL and scraper resilience.

#### Phase 10: Environment & Secrets Cleanup
**Goal**: All secrets externalized from config files to environment variables before cloud deployment
**Depends on**: Nothing (first phase of milestone)
**Requirements**: ENV-01, ENV-02, ENV-03
**Success Criteria** (what must be TRUE):
  1. Application starts successfully using only environment variables for all secrets (DATABASE_URL, SMTP credentials, CSRF secret, Telegram bot token, SECRET_KEY)
  2. config.yaml contains no hardcoded secrets (uses placeholders or omits secret fields entirely)
  3. .env.example file documents all required environment variables with example values
  4. All previously exposed secrets have been rotated (new Telegram bot token, new SMTP password, new SECRET_KEY generated)
**Plans**: 1 plan

Plans:
- [x] 10-01-PLAN.md — Externalize secrets, add startup validation, rotate credentials

#### Phase 11: PostgreSQL Migration & Production Server
**Goal**: Application runs on PostgreSQL with multi-worker ASGI server and separated scheduler process
**Depends on**: Phase 10 (requires environment variable configuration)
**Requirements**: DB-01, DB-02, DB-03, DB-04, DB-05, SRV-01, SRV-02, SRV-03, SRV-04
**Success Criteria** (what must be TRUE):
  1. Application connects to PostgreSQL via DATABASE_URL and handles both postgres:// and postgresql:// prefixes correctly
  2. All database queries execute successfully against PostgreSQL (parameter placeholders, boolean types, serial IDs work correctly)
  3. Application runs under gunicorn with uvicorn workers (multi-process web server)
  4. Scheduler runs as a single separate process (not duplicated across web workers)
  5. /health endpoint returns 200 with database connectivity status and returns 503 if database unavailable
  6. Application handles graceful shutdown (in-flight requests complete before process exit)
  7. Connection pooling configured appropriately for worker count (prevents connection exhaustion)
**Plans**: 3 plans

Plans:
- [x] 11-01-PLAN.md — PostgreSQL database layer with dual-mode SQLite/PostgreSQL and query conversion
- [x] 11-02-PLAN.md — Production server infrastructure (gunicorn, scheduler separation, health endpoint)
- [x] 11-03-PLAN.md — Data migration tooling and environment documentation

#### Phase 12: Hosting & SSL Deployment
**Goal**: Application deployed to managed hosting provider with HTTPS, custom domain, and automated backups
**Depends on**: Phase 11 (requires production-ready infrastructure)
**Requirements**: HOST-01, HOST-02, HOST-03, HOST-04, HOST-05
**Success Criteria** (what must be TRUE):
  1. Application is accessible via HTTPS with valid SSL certificate (no browser warnings)
  2. Application is accessible via custom domain (DNS configured correctly)
  3. PostgreSQL database has automated backups configured (daily or provider-managed)
  4. Git push triggers automatic deployment to hosting provider
  5. Application runs stably in production environment (web workers and scheduler process both running)
**Plans**: TBD

Plans:
- [ ] 12-01: TBD

#### Phase 13: Scraper Resilience
**Goal**: RA.co scraper handles cloud IP blocking, API failures, and transient errors gracefully
**Depends on**: Phase 12 (requires live deployment to test cloud IP behavior)
**Requirements**: SCRAPE-01, SCRAPE-02, SCRAPE-03, SCRAPE-04
**Success Criteria** (what must be TRUE):
  1. Scraper implements exponential backoff on 403/429/5xx responses (retries with increasing delays: 1s, 2s, 4s)
  2. Scraper rotates User-Agent strings across requests (reduces fingerprinting risk)
  3. Scraper handles extended API outages without crashing (circuit breaker prevents infinite retries)
  4. Scraper logs all response status codes (enables monitoring of blocking patterns)
  5. Application continues serving existing events even when scraper is blocked or API is down
**Plans**: TBD

Plans:
- [ ] 13-01: TBD

#### Phase 14: Observability & Monitoring
**Goal**: Production issues are detected and debuggable via structured logging, error tracking, and scraper health monitoring
**Depends on**: Phase 13 (requires stable scraper to monitor)
**Requirements**: OBS-01, OBS-02, OBS-03, OBS-04
**Success Criteria** (what must be TRUE):
  1. Application emits structured JSON logs with request IDs and HTTP status codes
  2. Errors are tracked in external system (Sentry or equivalent) with stack traces and context
  3. Scraper health is visible (success/failure rate, last successful fetch time, current status)
  4. Alerts trigger on 3+ consecutive scraper fetch failures (email or Telegram notification to admin)
  5. Admin can diagnose production issues using logs and error tracking without SSH access
**Plans**: TBD

Plans:
- [ ] 14-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Database Foundation | v2.0 | 2/2 | Complete | 2026-01-23 |
| 2. Authentication System | v2.0 | 3/3 | Complete | 2026-01-27 |
| 3. Multi-Tenant Access Control | v2.0 | 4/4 | Complete | 2026-01-29 |
| 4. User Notification Delivery | v2.0 | 3/3 | Complete | 2026-01-31 |
| 5. Audit Foundation & CSRF Protection | v2.1 | 2/2 | Complete | 2026-02-02 |
| 6. Email Verification & Login Hardening | v2.1 | 3/3 | Complete | 2026-02-06 |
| 7. Password Management | v2.1 | 3/3 | Complete | 2026-02-07 |
| 8. Account Lifecycle & Admin Audit UI | v2.1 | 3/3 | Complete | 2026-02-08 |
| 9. UX Polish & Branding | v2.2 | 3/3 | Complete | 2026-02-10 |
| 10. Environment & Secrets | v3.0 | 1/1 | Complete | 2026-02-12 |
| 11. PostgreSQL & Server | v3.0 | 3/3 | Complete | 2026-02-16 |
| 12. Hosting & SSL | v3.0 | 0/0 | Not started | - |
| 13. Scraper Resilience | v3.0 | 0/0 | Not started | - |
| 14. Observability | v3.0 | 0/0 | Not started | - |

---
*Roadmap created: 2026-02-11*
*Last updated: 2026-02-16*
