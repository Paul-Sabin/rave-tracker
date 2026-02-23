# Requirements: Rave Tracker

**Defined:** 2026-02-22
**Core Value:** Users never miss events from artists, venues, or promoters they care about

## v3.3 Requirements

### Settings Page — Personal (All Users)

- [x] **SETT-01**: `/settings` shows only Notification Preferences, Account Security, and Delete Account for all users
- [x] **SETT-02**: Local Area section removed from `/settings` entirely (moved to /tracking)
- [x] **SETT-03**: Admin users see a link to `/admin/settings` on `/settings`

### Admin Settings Page

- [x] **SETT-04**: `/admin/settings` page created, accessible to admins only (non-admins get 403)
- [x] **SETT-05**: Telegram bot token and admin chat ID editable on `/admin/settings`
- [x] **SETT-06**: Fetch schedule configurable as specific times of day (e.g. 08:00, 20:00), replacing current interval field
- [x] **SETT-07**: Event horizon (days) editable on `/admin/settings`
- [x] **SETT-08**: Database info displayed (read-only) on `/admin/settings`
- [x] **SETT-09**: Test Admin Telegram button on `/admin/settings`
- [x] **SETT-10**: Notification mode toggle: "Upon fetch completion" (default) vs "Daily digest"
- [x] **SETT-11**: Daily digest time field shown and required when digest mode is selected

### Notification Dispatch

- [x] **SETT-12**: "Upon fetch" mode sends notifications immediately after successful fetch (preserves current behaviour)
- [x] **SETT-13**: "Daily digest" mode queues found events rather than sending immediately
- [x] **SETT-14**: Daily digest job sends batched notifications per user at the configured time

### Endpoint Hardening

- [ ] **SETT-15**: POST `/settings/save` rejects non-admin requests for system config fields with 403
- [ ] **SETT-16**: POST `/settings/test-telegram` rejects non-admin requests with 403

## Future Requirements

None identified.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Per-user notification timing controls | Admin sets system-wide policy; users don't configure timing |
| Fetch interval (hours) mode | Replaced by specific fetch times; interval model removed |
| Quiet hours | Not selected; daily digest covers the main use case |
| Minimum notification gap | Not selected for this milestone |
| Scheduler Status on admin/settings | Already covered by /admin/scraper-status; no duplication |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETT-01 | Phase 16 | Complete |
| SETT-02 | Phase 16 | Complete |
| SETT-03 | Phase 16 | Complete |
| SETT-04 | Phase 16 | Complete |
| SETT-05 | Phase 16 | Complete |
| SETT-06 | Phase 16 | Complete |
| SETT-07 | Phase 16 | Complete |
| SETT-08 | Phase 16 | Complete |
| SETT-09 | Phase 16 | Complete |
| SETT-10 | Phase 16 | Complete |
| SETT-11 | Phase 16 | Complete |
| SETT-12 | Phase 17 | Complete |
| SETT-13 | Phase 17 | Complete |
| SETT-14 | Phase 17 | Complete |
| SETT-15 | Phase 18 | Pending |
| SETT-16 | Phase 18 | Pending |

**Coverage:**
- v3.3 requirements: 16 total
- Mapped to phases: 16 (100%)
- Unmapped: 0

---
*Requirements defined: 2026-02-22*
*Last updated: 2026-02-22 — traceability mapped after roadmap creation*
