# Feature Landscape: Onboarding Welcome Wizard

**Domain:** First-login onboarding wizard with mascot character (Rave Tracker v3.4)
**Researched:** 2026-03-01
**Confidence:** HIGH (web search verified against multiple UX research sources)

---

## Table Stakes

Features users expect. Missing any of these makes the wizard feel broken or hostile.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Visible skip / dismiss at all times** | Users who already know what to do feel trapped without it; forced tours are the #1 cited anti-pattern | LOW | Always-visible "Skip tour" link in top-right or footer of each step. Research: skippable flows have 25% higher completion rates than forced flows. |
| **Step progress indicator** | Without it, users don't know if they're 2 steps from done or 10; anxiety causes abandonment | LOW | Dot-row (e.g. 4 dots, current filled) is the standard for 3-5 step flows. Users 40% more likely to complete when progress is visible. |
| **3-5 step limit** | Almost 80% of users abandon tours with more than 5 steps. More than 5 = chore, not welcome | LOW | Rave Tracker scope (welcome + area + feature tour + notifications) is exactly 4 — ideal. |
| **Mobile-first layout** | App is already mobile-first; wizard that breaks on 375px undermines trust | MEDIUM | Full-screen overlay pattern on mobile (not centered-box). 44px touch targets on all nav buttons. Match existing Tailwind v4 design tokens. |
| **Persistent state (survives refresh)** | If a user accidentally refreshes mid-wizard, losing progress is jarring | LOW | Store `onboarding_step` in the existing session or a DB column. A session variable is simplest. |
| **Revisitable from settings** | Users who skipped will want to re-run it; users who want a refresher expect to find it | LOW | "Retake the tour" link on `/settings`. Store a `has_completed_onboarding` boolean on the `users` table (new migration). |
| **Functional CTA per step** | Each step must do something real, not just be a slide. Area selection must actually save; notification preference must actually set flags | MEDIUM | Reuse existing `/api/area/save` and notification toggle endpoints behind AJAX calls inside the wizard. |
| **Works without JavaScript for nav** | Core navigation (Next/Back/Skip) must degrade gracefully or be POST-form-based | LOW | Use standard form POST for step transitions; layer JS enhancements on top. Consistent with existing app pattern. |

---

## Differentiators

Features that make this wizard feel crafted rather than bolted on. Not table stakes, but high value for the tone of the product.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Ravemonger mascot with step-aware dialogue** | Character-guided onboarding reduces cognitive load; mascot gives the app personality and is memorable. Adobe UX research: 25% reduction in drop-off when mascot used. | LOW-MEDIUM | Image asset provided by user. Each step shows the same Ravemonger image with different speech bubble copy. No animation required — static image with changing text is sufficient. Duolingo's Duo is the gold-standard reference. |
| **Short, punchy copy per step (< 30 words)** | Rave Tracker tone is "fun, not a chore." Wall-of-text onboarding is the #1 reason users dismiss it immediately. | LOW | Treat each step like a tweet. Mailchimp and Duolingo both use playful, brief copy. Example: "Here's your area. Berlin? Nice. Change it anytime." |
| **Partial completion handling** | User closes wizard on step 2, comes back tomorrow — resume where they left off, don't restart. | LOW | Store `onboarding_step` (integer 1-4) in DB. On first login after registration, redirect to `/onboarding?step=N`. |
| **Completion micro-celebration** | A small moment of delight at the end anchors a positive first memory. Headspace, Duolingo both do this. | LOW | Simple CSS confetti burst or a Ravemonger "thumbs up" speech bubble variant ("You're in. Let's find some events.") — no heavy JS library needed. |
| **Inline area search on step 3 (not redirect)** | Area selection that redirects away breaks wizard flow. User should be able to search and confirm without leaving. | MEDIUM | Reuse existing inline area search widget from `/tracking` page (already has AJAX save). Embed it inside the wizard step template. |
| **Notification opt-in with value context** | Asking for notification permission in a vacuum gets ignored. Showing "We'll tell you when Objekt drops a Berlin date" primes the user to say yes. | LOW | One sentence of value context before the toggle. Pattern: permission priming before the ask. Basecamp and Appcues research both confirm this improves opt-in rates. |
| **"You can change this any time" reassurance** | Every step where the user makes a choice (area, notifications) should confirm it's reversible. Reduces choice anxiety. | LOW | Single line of reassurance text under each choice. Removes "what if I get this wrong" friction. |

---

## Anti-Features

Features to explicitly avoid. These seem reasonable but damage the experience.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Forced tour (no skip)** | 80% of users who are power users or explorers will rage-quit or never return. Being trapped is the worst first impression. | Always show "Skip tour" — even on step 1. Trust the user. |
| **More than 5 steps** | Each additional step after 4 roughly doubles abandonment probability. Rave Tracker has exactly 4 meaningful steps — do not pad to 6 with "did you know?" slides. | Keep the 4 steps: welcome, area, feature tour, notifications. Everything else is deferred to contextual tooltips later. |
| **Collecting information not yet actionable** | Asking users to set digest time, import rules, or configure SMTP before they've seen the dashboard is premature. | Defer advanced settings to `/settings`. Wizard only handles: area and notification channel toggle. |
| **Auto-playing video or audio** | Jarring on mobile, especially if user is in public. Rave tracker users are in clubs. | Use static image + text only. |
| **Modal that can't be dismissed by clicking backdrop** | Trapping users who misclick creates frustration. | Either dismiss on backdrop click (with confirmation if mid-way), or keep the overlay non-trapping but clearly show the skip button. |
| **Tour triggered by a timer delay** | Click-triggered product tours complete at 67%; delay-triggered tours complete at only 31%. Timer-delayed modals feel like ads. | Trigger immediately on first post-verification login (redirect to `/onboarding`, not a floating modal overlay). |
| **Gamification points/badges for onboarding** | Rave Tracker has no gamification system. Adding badges only for onboarding creates a dangling feature with no follow-through. | Use micro-celebration (single confetti moment) at completion only. No points system. |
| **Confetti on every step** | Robinhood removed their confetti (2021) after criticism that it over-gamified serious actions. Confetti loses impact fast if overused. | Reserve celebration for final completion only. |
| **Email collection or social prompts during onboarding** | User just gave their email to register. Asking again, or asking to share on social, is tone-deaf. | Skip entirely. |
| **Onboarding checklist (persistent task list)** | Checklist pattern (like Notion, Linear) requires a partially-configured product state to be meaningful. Rave Tracker is simple enough that a linear wizard is better. | Linear wizard only. No persistent checklist UI after wizard completes. |

---

## Feature Dependencies

```
[Wizard trigger on first login]
    └──requires──> [has_completed_onboarding column on users table] (new DB migration)
    └──requires──> [First-login detection in login route] (check flag, redirect to /onboarding)
    └──conflicts──> [Email verification redirect] (verify email → must go to onboarding, not dashboard)

[Step 3: Area selection inside wizard]
    └──reuses──> [Inline area search widget from /tracking] (already AJAX-capable)
    └──requires──> [local_area_id already on users table] (already exists in migration 11)

[Step 4: Notification preference inside wizard]
    └──reuses──> [telegram_enabled / email_enabled toggles from /settings]
    └──requires──> [CSRF token available in wizard template] (already in base.html context)

[Revisitable tour from /settings]
    └──requires──> [has_completed_onboarding can be reset to False, or separate flag]
    └──requires──> [/onboarding route accessible when onboarding already completed]

[Ravemonger mascot display]
    └──requires──> [User-provided image asset added to static files]
    └──no external library dependency] (static <img> tag per step)

[Completion celebration]
    └──low dependency] (pure CSS or Tailwind animation on final step)
    └──no library required] (avoid canvas-confetti or similar if possible)
```

---

## MVP Recommendation

**The 4-step wizard that ships v3.4:**

1. **Step 1 — Welcome** (complexity: LOW)
   Ravemonger introduces Rave Tracker in 2-3 sentences. "You've got events to catch. I'm the Ravemonger. Let me show you around." No user action required.

2. **Step 2 — Local Area** (complexity: LOW-MEDIUM)
   Inline area search. Default already set to Berlin. User can confirm or change. "Your local area is Berlin. Is that right? Change it if not — this is how we filter events for you." AJAX save, no redirect.

3. **Step 3 — Feature Tour** (complexity: LOW)
   Three-panel mini-tour: (a) Tracking page — "Add artists, venues, promoters you follow." (b) Dashboard — "Your upcoming events, grouped by date." (c) Settings — "Notifications and your account live here." Static panels, no tooltips or overlays needed. This replaces a full interactive product tour.

4. **Step 4 — Notifications** (complexity: MEDIUM)
   Notification channel preference. Show current state (email is on by default, Telegram is off). Show value context: "Want alerts when a new event drops? Enable Telegram or keep email on." Toggle controls. "You can change this in Settings any time."

**Final screen: Completion** (complexity: LOW)
Ravemonger signs off. Micro-celebration. CTA: "Let's go to your dashboard."

**Defer:**
- Interactive tooltip overlays on actual app pages (high implementation cost, low signal for a small user base)
- Per-step progress persistence in DB (use session for step state; only DB flag needed is `has_completed_onboarding`)
- Advanced notification configuration (digest time, etc.) — `/settings` handles this

---

## Implementation Dependencies on Existing Rave Tracker Features

| Wizard Feature | Existing Feature It Depends On | Status |
|----------------|-------------------------------|--------|
| First-login trigger | Login route (`/login` POST), session handling | Exists — needs has_completed_onboarding check added |
| Area selection step | `local_area_id` on users table, inline area AJAX widget | Exists (migration 11 + tracking widget) — embed in wizard |
| Notification step | `telegram_enabled`, `email_enabled` on users table | Exists — reuse toggle POST endpoints |
| CSRF on wizard forms | CSRF middleware, csrf_token in templates | Exists — available via base.html context |
| Settings revisit link | `/settings` template | Exists — add "Retake the tour" link |
| Mobile layout | Tailwind v4 CDN, 44px targets, base.html styles | Exists — wizard templates extend base.html |
| **New: DB flag** | `has_completed_onboarding BOOLEAN DEFAULT FALSE` on users table | Does not exist — requires new migration (migration 14 or next) |
| **New: /onboarding route** | New route + 4 step templates | Does not exist — primary build work for this milestone |
| **New: Ravemonger static asset** | `/static/` directory | Static dir exists — image asset pending from user |

---

## Sources

- [UserGuiding: Onboarding Wizard Examples and Best Practices](https://userguiding.com/blog/what-is-an-onboarding-wizard-with-examples) — MEDIUM confidence (WebSearch verified)
- [UXDesignInstitute: UX Onboarding Best Practices 2025](https://www.uxdesigninstitute.com/blog/ux-onboarding-best-practices-guide/) — MEDIUM confidence
- [Appcues: The 11 Best User Onboarding Examples](https://www.appcues.com/blog/the-10-best-user-onboarding-experiences) — MEDIUM confidence
- [Appcues: Duolingo User Onboarding Breakdown](https://goodux.appcues.com/blog/duolingo-user-onboarding) — MEDIUM confidence
- [Appcues: Mobile Permission Priming](https://www.appcues.com/blog/mobile-permission-priming) — MEDIUM confidence
- [Chameleon: Onboarding Gamification](https://www.chameleon.io/blog/gamify-user-onboarding) — MEDIUM confidence
- [Chameleon: Product Tour Completion Rate Data (550M data points)](https://www.chameleon.io/blog/mastering-product-tours) — HIGH confidence (large dataset)
- [UserGuiding: Onboarding Statistics 2026](https://userguiding.com/blog/user-onboarding-statistics) — MEDIUM confidence
- [Eleken: Wizard UI Pattern](https://www.eleken.co/blog-posts/wizard-ui-pattern-explained) — MEDIUM confidence
- [Raw Studio: How Mascots Improve UX](https://raw.studio/blog/how-mascots-improve-user-experience/) — MEDIUM confidence
- [Userpilot: Onboarding Checklist Completion Rate Benchmarks](https://userpilot.com/blog/onboarding-checklist-completion-rate-benchmarks/) — MEDIUM confidence
- [Smashing Magazine: Onboarding UX Smart Patterns](https://smart-interface-design-patterns.com/articles/onboarding-ux/) — MEDIUM confidence
- [NNGroup: Bottom Sheets UX Guidelines](https://www.nngroup.com/articles/bottom-sheet/) — HIGH confidence (NNGroup)
- [DesignerUp: I Studied 200 Onboarding Flows](https://designerup.co/blog/i-studied-the-ux-ui-of-over-200-onboarding-flows-heres-everything-i-learned/) — MEDIUM confidence

---

*Feature research for: Onboarding Welcome Wizard (Rave Tracker v3.4)*
*Researched: 2026-03-01*
*Researcher: GSD Research Agent*
