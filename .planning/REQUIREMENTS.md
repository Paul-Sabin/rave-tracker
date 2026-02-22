# Requirements: Rave Tracker

**Defined:** 2026-02-22
**Core Value:** Users never miss events from artists, venues, or promoters they care about

## v3.3 Requirements

### Settings Page — Personal (All Users)

- [ ] **SETT-01**: `/settings` shows only Notification Preferences, Account Security, and Delete Account for all users
- [ ] **SETT-02**: Local Area section removed from `/settings` entirely (moved to /tracking)
- [ ] **SETT-03**: Admin users see a link to `/admin/settings` on `/settings`

### Admin Settings Page

- [ ] **SETT-04**: `/admin/settings` page created, accessible to admins only (non-admins get 403)
- [ ] **SETT-05**: Telegram bot token and admin chat ID editable on `/admin/settings`
- [ ] **SETT-06**: Fetch schedule configurable as specific times of day (e.g. 08:00, 20:00), replacing current interval field
- [ ] **SETT-07**: Event horizon (days) editable on `/admin/settings`
- [ ] **SETT-08**: Database info displayed (read-only) on `/admin/settings`
- [ ] **SETT-09**: Test Admin Telegram button on `/admin/settings`
- [ ] **SETT-10**: Notification mode toggle: "Upon fetch completion" (default) vs "Daily digest"
- [ ] **SETT-11**: Daily digest time field shown and required when digest mode is selected

### Notification Dispatch

- [ ] **SETT-12**: "Upon fetch" mode sends notifications immediately after successful fetch (preserves current behaviour)
- [ ] **SETT-13**: "Daily digest" mode queues found events rather than sending immediately
- [ ] **SETT-14**: Daily digest job sends batched notifications per user at the configured time

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
| SETT-01 | — | Pending |
| SETT-02 | — | Pending |
| SETT-03 | — | Pending |
| SETT-04 | — | Pending |
| SETT-05 | — | Pending |
| SETT-06 | — | Pending |
| SETT-07 | — | Pending |
| SETT-08 | — | Pending |
| SETT-09 | — | Pending |
| SETT-10 | — | Pending |
| SETT-11 | — | Pending |
| SETT-12 | — | Pending |
| SETT-13 | — | Pending |
| SETT-14 | — | Pending |
| SETT-15 | — | Pending |
| SETT-16 | — | Pending |

**Coverage:**
- v3.3 requirements: 16 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 16 ⚠️

---
*Requirements defined: 2026-02-22*
*Last updated: 2026-02-22 after initial definition*
