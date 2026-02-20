---
phase: 12-hosting-ssl-deployment
plan: 03
subsystem: deployment
tags: [infrastructure, dns, ssl, custom-domain, verification]
dependency_graph:
  requires:
    - "12-02: Live Railway deployment with PostgreSQL"
  provides:
    - "Custom domain with HTTPS (ravetracker.whotrustswho.com)"
    - "All HOST requirements verified"
  affects: []
tech_stack:
  added:
    - Let's Encrypt SSL certificate (auto-provisioned by Railway)
    - Custom domain DNS (CNAME record)
  patterns:
    - Railway auto-SSL provisioning on custom domain verification
key_files:
  created: []
  modified: []
decisions:
  - decision: "Use 300s TTL for DNS CNAME record"
    rationale: "Fast propagation during setup; negligible overhead for low-traffic app"
    alternatives: "3600s (1 hour) after confirmed working — optional optimization"
metrics:
  duration: "~30m"
  completed: "2026-02-15"
  tasks_completed: 2
  commits: 0
---

# Phase 12 Plan 03: Custom Domain & SSL Summary

**One-liner:** Configured custom domain ravetracker.whotrustswho.com with auto-provisioned Let's Encrypt SSL and verified all HOST requirements.

## Overview

Added custom domain to Railway web service, configured CNAME DNS record at domain registrar, and verified the complete production deployment meets all Phase 12 success criteria.

## Tasks Completed

### Task 1: Configure custom domain with SSL (checkpoint:human-action)
**Status:** Complete

User actions completed:
- Added custom domain `ravetracker.whotrustswho.com` in Railway dashboard
- Created CNAME DNS record at domain registrar (TTL: 300s)
- DNS propagation confirmed via dnschecker.org (all but 2 servers resolved immediately)
- Railway auto-provisioned Let's Encrypt SSL certificate
- Updated BASE_URL environment variable to `https://ravetracker.whotrustswho.com`

### Task 2: Final production verification (checkpoint:human-verify)
**Status:** Complete

All HOST requirements verified:
- HOST-01: Application deployed and running on Railway
- HOST-02: PostgreSQL with Railway-managed database (backup via third-party template — documented in RAILWAY.md)
- HOST-03: HTTPS with valid Let's Encrypt SSL (browser padlock confirmed)
- HOST-04: Custom domain resolves and serves application
- HOST-05: Git-push auto-deploy pipeline active

Functional verification:
- Login works at custom domain
- Dashboard displays migrated events
- Rules and settings pages load correctly
- Scheduler running in Railway logs
- Auto-deploy confirmed (6 commits deployed during 12-02)

## Deviations from Plan

### Plan referenced Render, deployed on Railway
- All Render-specific instructions adapted to Railway equivalents
- Railway's domain setup is simpler (Settings → Domains → Add Domain)
- SSL auto-provisioning works identically (Let's Encrypt)

## Verification

**Phase 12 success criteria — ALL MET:**
- Application accessible at custom domain with HTTPS
- Custom domain resolves correctly to production application
- Full end-to-end flow works (login, view events, rules, settings)
- Git-push deployment pipeline active
- PostgreSQL database running with migrated data

## Self-Check: PASSED

```
Custom domain: https://ravetracker.whotrustswho.com — LIVE
SSL: Valid Let's Encrypt certificate — CONFIRMED
Login: Working at custom domain — CONFIRMED
Dashboard: Events displayed — CONFIRMED
Rules/Settings: Loading — CONFIRMED
Auto-deploy: Active — CONFIRMED
```
