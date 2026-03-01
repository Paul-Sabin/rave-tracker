# Requirements: Rave Tracker

**Defined:** 2026-03-01
**Core Value:** Users never miss events from artists, venues, or promoters they care about

## v3.4 Requirements

Requirements for the Onboarding & Welcome milestone. Each maps to roadmap phases.

### Wizard Structure

- [ ] **WIZ-01**: New user sees a 4-step welcome wizard on first login after email verification
- [ ] **WIZ-02**: Each step has a visible "Skip" button that advances without writing any data
- [ ] **WIZ-03**: Step progress indicator (dot row) shows current position across all steps
- [ ] **WIZ-04**: Final step shows a completion celebration (Ravemonger thumbs-up or confetti)
- [ ] **WIZ-05**: Wizard steps use CSS slide transitions for step changes

### Ravemonger Mascot

- [ ] **RAVE-01**: Ravemonger character displayed as static image with speech bubble on each step
- [ ] **RAVE-02**: Each wizard step has a unique Ravemonger dialogue (short, punchy, fun tone)

### Data & Settings

- [ ] **DATA-01**: Step 2 presents inline area search to pick local area (reuses existing widget)
- [ ] **DATA-02**: Step 3 presents Telegram and Email notification toggles (unchecked by default for new users, GDPR-compliant)
- [ ] **DATA-03**: User can revisit the wizard from a "Revisit Tour" link on /settings

### Technical Foundation

- [ ] **FOUND-01**: Database migration adds `onboarding_completed` column with existing-user backfill
- [ ] **FOUND-02**: Login handler redirects new users to `/welcome/step/1` after successful auth
- [ ] **FOUND-03**: Wizard only triggers for users who have verified their email
- [ ] **FOUND-04**: Step transitions manage focus correctly (aria-live, keyboard navigation, focus trap)

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Ravemonger Expansion

- **RAVE-03**: Ravemonger appears outside wizard context (dashboard tips, contextual hints)
- **RAVE-04**: Animated Ravemonger character variants (waving, pointing, dancing)

### Advanced Onboarding

- **WIZ-06**: Interactive tooltip overlays on live app pages (guided tour of actual UI)
- **WIZ-07**: Gamification elements (badges, progress tracking beyond onboarding)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Telegram linking during wizard | Requires leaving the app — high drop-off risk; defer to post-wizard contextual prompt |
| Per-step DB progress persistence | URL-based step tracking is sufficient; `onboarding_step` column adds complexity without clear value |
| Alpine.js or HTMX | Existing vanilla JS + Tailwind handles wizard; new dependency not justified for bounded UI |
| Video tutorials in wizard | High production cost, bandwidth concerns on mobile |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | — | Pending |
| FOUND-02 | — | Pending |
| FOUND-03 | — | Pending |
| FOUND-04 | — | Pending |
| WIZ-01 | — | Pending |
| WIZ-02 | — | Pending |
| WIZ-03 | — | Pending |
| WIZ-04 | — | Pending |
| WIZ-05 | — | Pending |
| RAVE-01 | — | Pending |
| RAVE-02 | — | Pending |
| DATA-01 | — | Pending |
| DATA-02 | — | Pending |
| DATA-03 | — | Pending |

**Coverage:**
- v3.4 requirements: 14 total
- Mapped to phases: 0
- Unmapped: 14

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-01 after initial definition*
