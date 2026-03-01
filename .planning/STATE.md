# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Users never miss events from artists, venues, or promoters they care about
**Current focus:** v3.4 Onboarding & Welcome — Phase 19 ready to plan

## Current Position

Phase: 19 of 23 (Database Foundation)
Plan: 0 of 1 in current phase
Status: Ready to plan
Last activity: 2026-03-01 — v3.4 roadmap created, phases 19-23 defined

Progress: [░░░░░░░░░░] 0/7 plans (v3.4)

## Performance Metrics

**Velocity:**
- Total plans completed: 47 (phases 1-18)
- Average duration (v3.x): ~15m per plan

**By Phase:**

| Phase | Plans | Milestone |
|-------|-------|-----------|
| 1-14 | 34/34 | v2.0-v3.1 |
| 15. Tracking Page UX | 1/1 | v3.2 |
| 16. Settings Page Split | 2/2 | v3.3 |
| 17. Notification Dispatch Modes | 2/2 | v3.3 |
| 18. Endpoint Hardening | 1/1 | v3.3 |

## Accumulated Context

### Decisions

All decisions logged in PROJECT.md Key Decisions table.

Recent decisions affecting v3.4:
- URL-based step state (no per-step DB persistence) — only onboarding_completed boolean needed
- GDPR: notification toggles must be unchecked for new users regardless of DB default
- Existing-user backfill: UPDATE WHERE local_area_id IS NOT NULL OR telegram_chat_id IS NOT NULL
- Wizard gates on BOTH email_verified AND NOT onboarding_completed
- No new dependencies — vanilla JS + Tailwind v4 CDN + @keyframes handles all wizard UI

### Pending Todos

None.

### Blockers/Concerns

- Phase 21 dependency: Ravemonger image asset (WebP + PNG) is pending from user. Template can be built with placeholder img first.
- Phase 21 dependency: Confirm base.html has a {% block nav %} override point before step 1 template work.

## Session Continuity

Last session: 2026-03-01
Stopped at: v3.4 roadmap created
Resume file: None
Next: /gsd:plan-phase 19
