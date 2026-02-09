# Requirements: Rave Tracker v2.2

**Defined:** 2026-02-08
**Core Value:** Users never miss events from artists, venues, or promoters they care about

## v2.2 Requirements

Requirements for UX Polish & Branding milestone.

### Branding

- [ ] **BRAND-01**: All user-facing instances of "RA Tracker" display as "Rave Tracker" (page titles, nav, login, emails, footer)
- [ ] **BRAND-02**: Email "from" name displays as "Rave Tracker" instead of "RA Tracker"

### UX

- [ ] **UX-01**: User is prompted to select a local region (suggesting Berlin) before creating their first rule, if no region is set
- [ ] **UX-02**: Dashboard area toggle labels read "Global events" and "Local only" instead of "All Areas" and "{region} only"
- [ ] **UX-03**: Legacy admin welcome banner removed from dashboard

## v2.3+ Candidates

Deferred to future milestones.

- **SEC-08**: Login attempt notifications to user
- **SEC-09**: Two-factor authentication (TOTP)
- **ACCT-09**: Account export (GDPR data portability)
- **AUDIT-11**: Audit log export (CSV/JSON)

## Out of Scope

Explicitly excluded from this milestone.

| Feature | Reason |
|---------|--------|
| Internal folder/module renaming | User-facing rebrand only, keep ra-tracker/ra_tracker internally |
| RA API references in code | Must retain for functionality — only user-facing text changes |
| Region auto-detection | Simple prompt with Berlin suggestion sufficient |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BRAND-01 | Phase 9 | Pending |
| BRAND-02 | Phase 9 | Pending |
| UX-01 | Phase 9 | Pending |
| UX-02 | Phase 9 | Pending |
| UX-03 | Phase 9 | Pending |

**Coverage:**
- v2.2 requirements: 5 total
- Mapped to phases: 5
- Unmapped: 0

---
*Requirements defined: 2026-02-08*
*Last updated: 2026-02-08 after roadmap creation*
