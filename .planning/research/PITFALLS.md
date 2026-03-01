# Domain Pitfalls: Onboarding Welcome Wizard

**Domain:** Adding a multi-step onboarding wizard to an existing FastAPI/Jinja2/Tailwind CSS v4 web app (Rave Tracker)
**Researched:** 2026-03-01
**Confidence:** HIGH (codebase confirmed, supplemented by current web research)

---

## Critical Pitfalls

Mistakes that cause rewrites, broken UX for existing users, or require emergency rollbacks.

---

### Pitfall 1: Showing the Wizard Retroactively to Existing Users

**What goes wrong:**
Existing users log in after deployment and are forced through a wizard covering preferences they already set months ago.

**Why it happens:**
The wizard trigger is typically implemented as: "show wizard if `onboarding_completed = False`". Without migration logic, all existing users have this flag as `NULL` or `False` and are treated as new users.

**Codebase-specific risk:**
The `users` table currently has no `onboarding_completed` column. When the migration adds it with `DEFAULT FALSE`, every existing user gets `False`.

**Prevention:**
Add the migration column with a conditional backfill:

```sql
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE;
UPDATE users SET onboarding_completed = TRUE
  WHERE local_area_id IS NOT NULL
     OR telegram_chat_id IS NOT NULL;
```

**Phase:** Address in the very first implementation phase before any wizard UI is built.

---

### Pitfall 2: Wizard State Corruption on Browser Refresh

**What goes wrong:**
A user is on Step 2, selects their local area via AJAX, then refreshes the page. The server-rendered page returns to Step 1 because the wizard step is tracked in JavaScript state, not in the database.

**Prevention:**
Use server-persisted step tracking. Each wizard step that collects data saves immediately. The `onboarding_completed` flag is only set `TRUE` on the final "Done" action. Step tracking uses an `onboarding_step` column (INT) updated on each step submission. On page load, the server reads this column and renders the correct step.

**Phase:** Address in wizard state management phase. Requires DB migration for `onboarding_step` column alongside `onboarding_completed`.

---

### Pitfall 3: Duplicate Preference Paths Creating Divergent State

**What goes wrong:**
The wizard collects the same data as the settings page. The two paths can get out of sync if "skip" writes defaults rather than leaving existing values alone.

**Prevention:**
- Seed wizard fields from current DB values, not hardcoded defaults
- "Skip" must be truly non-destructive: skipping a step writes nothing
- Reuse existing endpoints: wizard POSTs go to same API endpoints as settings

**Phase:** Address during wizard step implementation.

---

## Moderate Pitfalls

---

### Pitfall 4: The Clippy Effect — Mascot Fatigue

**What goes wrong:**
The Ravemonger character appears persistently, becoming associated with nagging rather than help.

**Prevention:**
- One appearance per session max outside wizard context
- No autoplay character animations on the main dashboard
- Revisit path opens directly without re-triggering intro animations
- Provide a permanent dismiss option

**Phase:** Address during mascot integration phase.

---

### Pitfall 5: Over-Long Wizard Causing Drop-Off

**What goes wrong:**
Research shows 40% abandonment for complex multi-step flows. Telegram linking requires leaving the app, creating a strong drop-off point.

**Prevention:**
- Maximum 3-4 wizard steps for required setup
- Defer Telegram linking to a post-wizard contextual prompt
- Each step completable in under 30 seconds
- Show step count: "Step 2 of 3"

**Phase:** Address during wizard design/structure phase.

---

### Pitfall 6: Notification Opt-In Dark Patterns

**What goes wrong:**
Pre-checked consent boxes violate GDPR Article 7. `email_enabled` defaults to `TRUE` in the database.

**Prevention:**
- Notification channels must start unchecked in the wizard
- Frame opt-in positively: affirmative action required
- Skip must not enable any channel

**Phase:** Address during wizard notification step implementation.

---

### Pitfall 7: Inaccessible Step UI

**What goes wrong:**
Focus remains on the previous step's button when advancing. Screen reader users hear nothing change.

**Prevention:**
- On step transition, move focus to the step heading using `element.focus()`
- Apply `role="dialog"` and `aria-modal="true"` to wizard container
- Trap focus inside the wizard overlay
- Test with `prefers-reduced-motion`
- 44px minimum touch targets (existing convention)

**Phase:** Address during wizard implementation phase.

---

### Pitfall 8: Revisit Tour Showing Stale State

**What goes wrong:**
User accesses "Revisit setup" months later. Wizard shows old values rather than current DB state.

**Prevention:**
- Always seed wizard field values from the live DB on each step render
- Revisit path renders in "revisit mode" — saves are optional
- Title the revisit differently: "Review your setup"

**Phase:** Address during revisit implementation.

---

## Minor Pitfalls

---

### Pitfall 9: Mobile Layout — CTA Button Off-Screen at 375px

**Prevention:** Sticky/fixed CTA button. Ravemonger illustration resizes or hides on small viewports. Test at 375x667.

### Pitfall 10: "Skip All" Creates Permanently Degraded Experience

**Prevention:** Per-step skip only (no "skip all"). Post-skip dashboard banner for missing local area.

### Pitfall 11: CSRF Token Missing on Wizard POST Endpoints

**Prevention:** Include `csrf_token` from Jinja2 context in every wizard POST. Test all POSTs with DevTools.

### Pitfall 12: Wizard Shown Before Email Verification

**Prevention:** Wizard trigger: `if user.email_verified and not user.onboarding_completed` — both conditions required.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| DB migration | Retroactive trigger (P1) | Backfill `onboarding_completed = TRUE` for configured users |
| Wizard state | State corruption on refresh (P2) | Use `onboarding_step` DB column as source of truth |
| Step implementations | Overwriting preferences on skip (P3) | Seed from current DB value; skip writes nothing |
| Notification step | Dark pattern opt-in (P6) | All toggles unchecked; affirmative action required |
| Mascot integration | Clippy effect (P4) | Define appearance rules: once per session max |
| Mobile layout | CTA off-screen (P9) | Sticky CTA; test at 375x667 |
| Auth integration | Wizard before verification (P12) | Gate behind `email_verified AND NOT onboarding_completed` |
