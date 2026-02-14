---
phase: 12-hosting-ssl-deployment
plan: 01
subsystem: deployment
tags: [infrastructure, docker, railway, configuration]
dependency_graph:
  requires:
    - "11-02: Production server infrastructure (Procfile, health check)"
    - "10-01: Environment variable externalization"
  provides:
    - "Railway deployment configuration (Dockerfile, railway.json)"
    - "Docker build setup with psycopg2 source compilation"
    - "Deployment documentation with backup template requirements"
  affects:
    - "12-02: SSL/Domain Setup (will use Railway's auto-SSL)"
tech_stack:
  added:
    - Docker (python:3.11-slim base image)
    - Railway deployment platform
  patterns:
    - Multi-service deployment via Procfile (web + scheduler)
    - Docker layer caching for pip dependencies
    - Force-add deployment configs to override .gitignore
key_files:
  created:
    - ra-tracker/Dockerfile
    - ra-tracker/.dockerignore
    - ra-tracker/railway.json
    - ra-tracker/runtime.txt
    - ra-tracker/RAILWAY.md
  modified: []
decisions:
  - decision: "Railway selected as hosting provider (over Render and Fly.io)"
    rationale: "Usage-based pricing for low-traffic apps, simple multi-service support from same repo"
    alternatives: "Render (higher base cost but native backups), Fly.io (higher PG cost, steeper learning curve)"
  - decision: "Use Docker builder instead of Railway's Nixpacks"
    rationale: "Explicit control over psycopg2 compilation with libpq-dev + gcc"
    alternatives: "Nixpacks auto-detection (may fail on psycopg2 source build)"
  - decision: "Force-add railway.json and runtime.txt despite .gitignore"
    rationale: "Required for Railway deployment, *.json and *.txt are globally ignored"
    alternatives: "Update .gitignore with exceptions (rejected to avoid global config churn)"
metrics:
  duration: "4h 3m"
  completed: "2026-02-14"
  tasks_completed: 2
  commits: 1
---

# Phase 12 Plan 01: Hosting Provider Selection & Configuration Summary

**One-liner:** Railway deployment configuration with Docker build, multi-service Procfile support, and comprehensive documentation including backup template requirement.

## Overview

Selected Railway as the hosting provider and created all platform-specific deployment configuration files. The application uses Docker for consistent builds with psycopg2 source compilation, and leverages the existing Procfile from Phase 11 for multi-service orchestration (web + scheduler).

## Tasks Completed

### Task 1: Select hosting provider (checkpoint:decision)
**Status:** ✅ Complete
**Decision:** Railway selected

**Options evaluated:**
- **Render:** $21/mo flat, native backups, native worker service (recommended in research)
- **Fly.io:** $38+/mo (high PG cost), CLI-first, complex networking
- **Railway:** Usage-based pricing (~$15-30/mo), simple UI, NO native PG backups

**Selection rationale:** Usage-based pricing for low-traffic startup, simple multi-service deployment, good UI/UX.

**Trade-off accepted:** No native PostgreSQL backups (requires third-party template) vs Render's automated backups.

### Task 2: Create platform deployment configuration files
**Status:** ✅ Complete
**Commit:** `48a5338`

**Files created:**
1. **Dockerfile** - Production container image
   - Base: `python:3.11-slim`
   - Installs `libpq-dev` + `gcc` for psycopg2 source compilation (NOT psycopg2-binary)
   - Layer caching: requirements.txt copied before app code
   - Default CMD: gunicorn with uvicorn workers

2. **.dockerignore** - Build exclusions
   - Excludes: venv/, .env, data/, .planning/, scripts/
   - Keeps: .env.example, README.md

3. **railway.json** - Railway build configuration
   - Builder: DOCKERFILE (explicit, not Nixpacks)
   - Deploy: 1 replica, restart on failure

4. **runtime.txt** - Python version pinning
   - Specifies: python-3.11.11
   - Used as fallback if Railway switches to Nixpacks

5. **RAILWAY.md** - Comprehensive deployment guide
   - Multi-service setup instructions (web + scheduler)
   - Environment variable configuration
   - **CRITICAL:** Documents backup template requirement
   - Health check configuration (/health endpoint)
   - Cost estimation, troubleshooting, security notes

**Verification passed:**
- ✅ All 5 files exist
- ✅ Dockerfile includes libpq-dev (psycopg2 requirement)
- ✅ Dockerfile does NOT use psycopg2-binary
- ✅ .dockerignore excludes dev artifacts (venv, .env, data)
- ✅ Procfile (from Phase 11) defines web + scheduler processes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Force-add gitignored deployment files**
- **Found during:** Task 2 file creation
- **Issue:** railway.json and runtime.txt were created but not staged by git (blocked by `.gitignore` rules: `*.json` and `*.txt`)
- **Fix:** Used `git add -f` to force-add railway.json and runtime.txt
- **Files modified:** None (workaround at staging time)
- **Commit:** Same as Task 2 (48a5338)
- **Rationale:** These files are required for Railway deployment. Alternative would be updating .gitignore with exceptions (!ra-tracker/railway.json, !ra-tracker/runtime.txt), but this adds global config churn for deployment-specific needs. Force-add is cleaner.

## Key Decisions

1. **Railway over Render/Fly.io:** Usage-based pricing, simple multi-service support, but requires third-party backup template
2. **Docker builder (not Nixpacks):** Explicit control over psycopg2 compilation requirements
3. **Force-add deployment configs:** Avoids updating global .gitignore rules for deployment-specific files

## Integration Points

**Inputs (dependencies):**
- Procfile from Phase 11-02 (web + scheduler process definitions)
- Health check endpoint (/health) from Phase 11-02
- Environment variables from Phase 10-01 (.env.example)

**Outputs (provides):**
- Dockerfile ready for Railway deployment
- railway.json configuring Docker builder
- RAILWAY.md with complete deployment instructions
- Backup template requirement documented

**Next phase:**
- Plan 12-02 will handle actual deployment to Railway
- Plan 12-03 will configure custom domain + SSL (Railway provides auto-SSL)

## Technical Notes

**psycopg2 source vs binary:**
- Dockerfile installs libpq-dev + gcc for psycopg2 source compilation
- Avoids psycopg2-binary to prevent libpq/libssl version conflicts (Phase 11 decision)
- Ensures compatibility with Railway's managed PostgreSQL

**Multi-service architecture:**
- Web service: gunicorn + uvicorn workers (async FastAPI)
- Scheduler service: APScheduler in --scheduler-only mode
- Both share DATABASE_URL and env vars
- Railway deploys from same repo using different Procfile entries

**Backup blind spot:**
- Railway does NOT provide native PostgreSQL backups
- RAILWAY.md documents requirement for third-party template
- User must deploy backup solution separately (pgbackups, postgres-backup-s3, etc.)
- This is a known trade-off vs Render's automated daily backups

## Verification

**Plan success criteria:**
- ✅ Platform configuration files created (Dockerfile, railway.json, .dockerignore, runtime.txt)
- ✅ Provider selected (Railway)
- ✅ Subsequent plan can deploy using these files without further configuration decisions
- ✅ Procfile (existing) defines both web and scheduler processes
- ✅ Dockerfile builds with psycopg2 (not binary)
- ✅ Health check endpoint (/health) documented in RAILWAY.md
- ✅ Environment variables declared in RAILWAY.md (not hardcoded)
- ✅ DATABASE_URL auto-injection documented

**Must-haves verification:**
- ✅ Platform configuration files exist (Dockerfile, railway.json, .dockerignore, runtime.txt)
- ✅ Dockerfile builds Python 3.11 image with psycopg2 (not psycopg2-binary)
- ✅ Health check path documented for Railway
- ✅ Environment variables declared in RAILWAY.md guide

## Self-Check: PASSED

**Created files verification:**
```
✅ FOUND: ra-tracker/Dockerfile
✅ FOUND: ra-tracker/.dockerignore
✅ FOUND: ra-tracker/railway.json
✅ FOUND: ra-tracker/runtime.txt
✅ FOUND: ra-tracker/RAILWAY.md
```

**Commits verification:**
```
✅ FOUND: 48a5338 (feat(12-01): create Railway deployment configuration)
```

**Procfile verification:**
```
✅ FOUND: ra-tracker/Procfile (2 processes: web, scheduler)
```

All files exist, commit is in git history, and Procfile defines required processes.
