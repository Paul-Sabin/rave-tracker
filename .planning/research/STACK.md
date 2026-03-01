# Technology Stack

**Project:** RA Tips — Multi-Step Onboarding Welcome Wizard
**Researched:** 2026-03-01
**Scope:** Wizard-specific additions only. Core stack (FastAPI, Jinja2, Tailwind CSS v4 CDN, PostgreSQL/SQLite, AJAX) is already validated and excluded.

---

## Executive Recommendation

No new libraries. No new frameworks. The existing stack handles everything the wizard needs. The work is technique selection — choosing the right CSS and JS patterns that work inside Jinja2 templates with a CDN-delivered Tailwind v4.

---

## Recommended Stack Additions

### 1. Step Transitions — CSS Keyframe Animations via `@keyframes` in `<style type="text/tailwindcss">`

**Technology:** Native CSS `@keyframes` + Tailwind v4 `@theme` custom animation tokens
**Version:** Browser-native, Tailwind v4.x (current)
**Purpose:** Animate step entry and exit (slide-in from right on advance, slide-in from left on back)
**Why:** Tailwind v4 CDN supports a `<style type="text/tailwindcss">` block that is processed by the browser-side engine. Custom `@keyframes` can be declared there and registered under `@theme` as `--animate-*` tokens, which Tailwind then exposes as `animate-*` utility classes. This keeps animation authoring inside the Tailwind mental model, requires no build step changes, and produces zero external dependencies.

**Implementation pattern:**

```html
<style type="text/tailwindcss">
  @theme {
    --animate-slide-in-right: slide-in-right 300ms cubic-bezier(0.25, 0.46, 0.45, 0.94) both;
    --animate-slide-in-left:  slide-in-left  300ms cubic-bezier(0.25, 0.46, 0.45, 0.94) both;
    --animate-slide-out-right: slide-out-right 300ms cubic-bezier(0.55, 0, 0.1, 1) both;
    --animate-slide-out-left:  slide-out-left  300ms cubic-bezier(0.55, 0, 0.1, 1) both;
  }

  @keyframes slide-in-right  { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
  @keyframes slide-in-left   { from { transform: translateX(-100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
  @keyframes slide-out-right { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }
  @keyframes slide-out-left  { from { transform: translateX(0); opacity: 1; } to { transform: translateX(-100%); opacity: 0; } }
</style>
```

JS sets a `data-direction="forward"` or `data-direction="back"` attribute on a wrapper element. CSS selects which animation class to apply based on that attribute. This keeps the directionality logic entirely in JS (where it belongs) while the visual execution stays in CSS.

**Confidence:** HIGH — Tailwind v4 CDN `@theme` and `@keyframes` documented at [tailwindcss.com/blog/tailwindcss-v4](https://tailwindcss.com/blog/tailwindcss-v4) and confirmed in community discussions.

---

### 2. Step Visibility — `display` toggling with `hidden` + `aria-hidden`

**Technology:** Tailwind `hidden` utility + manual `aria-hidden` attribute toggling in JS
**Purpose:** Show/hide wizard steps without layout jank
**Why over `opacity`/`visibility`:** `display: none` fully removes the element from layout and focus order, preventing tab-stop leaking into invisible steps. It also avoids the common pitfall of users accidentally tabbing into a hidden step's inputs. JS re-applies the slide animation class after toggling display, forcing a fresh animation frame.

**Why NOT `@starting-style`:** Browser support is incomplete as of 2026-03. Firefox added `@starting-style` in v129 (released August 2024) but `transition-behavior: allow-discrete` on `display` property is not yet consistently supported across Firefox versions. Since this app targets mobile users broadly, falling back to JS-driven class toggling with `@keyframes` is safer and more predictable. Revisit `@starting-style` as a progressive enhancement in a future phase.

**Confidence:** MEDIUM — `@starting-style` support status from MDN ([developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@starting-style](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@starting-style)) and web.dev ([web.dev/blog/baseline-entry-animations](https://web.dev/blog/baseline-entry-animations)).

---

### 3. Wizard State Management — Vanilla JS Module Object

**Technology:** Plain JavaScript object + `sessionStorage`
**Purpose:** Track current step index, visited steps, collected answers, and navigation direction across the wizard session
**Why NOT `localStorage`:** Wizard state should not persist across browser sessions. `sessionStorage` clears on tab close, matching user expectations for an onboarding flow.
**Why NOT URL hash routing:** Hash-based step routing adds URL complexity and back-button entanglement. The wizard is a contained modal-like experience that should not interact with browser history. If revisitability is needed, JS tracks which steps are "completed" and re-navigates internally without pushing to history.

**Pattern:**

```javascript
const WizardState = {
  currentStep: 0,
  totalSteps: 5,
  direction: 'forward',       // 'forward' | 'back'
  completedSteps: new Set(),
  data: {},                   // collected preferences

  save() {
    sessionStorage.setItem('onboarding', JSON.stringify({
      currentStep: this.currentStep,
      completedSteps: [...this.completedSteps],
      data: this.data
    }));
  },

  restore() {
    const saved = sessionStorage.getItem('onboarding');
    if (!saved) return;
    const state = JSON.parse(saved);
    this.currentStep = state.currentStep;
    this.completedSteps = new Set(state.completedSteps);
    this.data = state.data;
  },

  goTo(index) {
    this.direction = index > this.currentStep ? 'forward' : 'back';
    this.completedSteps.add(this.currentStep);
    this.currentStep = index;
    this.save();
    renderStep(this.currentStep, this.direction);
  }
};
```

This is a single-file pattern that fits cleanly in a `<script>` block at the bottom of the Jinja2 template or in a dedicated `wizard.js` static file.

**Revisitability:** The `completedSteps` Set drives progress indicator rendering — a step dot is rendered as "clickable" when its index is in `completedSteps`. Clicking a completed step calls `WizardState.goTo(index)`, which triggers the slide-in animation in the correct direction.

**Confidence:** HIGH — established pattern, no external dependencies required.

---

### 4. Progress Indicator — Pure CSS Dots/Steps

**Technology:** HTML `<ol>` with Tailwind utility classes, driven by Jinja2 template loop
**Purpose:** Show current step position; allow clicking completed steps to revisit
**Why `<ol>` not `<div>` soup:** Ordered list semantics are read correctly by screen readers. Each `<li>` gets `aria-current="step"` when active.

**Jinja2 template approach:**

```html
<ol role="list" aria-label="Onboarding steps" class="flex items-center justify-center gap-3">
  {% for step in wizard_steps %}
  <li>
    <button
      class="w-3 h-3 rounded-full transition-all duration-200
             data-[state=active]:bg-purple-500 data-[state=active]:scale-125
             data-[state=complete]:bg-purple-300 data-[state=complete]:cursor-pointer
             data-[state=upcoming]:bg-gray-600 data-[state=upcoming]:cursor-default"
      data-step="{{ loop.index0 }}"
      aria-label="Step {{ loop.index }}: {{ step.label }}"
      aria-current="false"
      type="button">
    </button>
  </li>
  {% endfor %}
</ol>
```

JS updates `data-state` attributes and `aria-current="step"` on the active button after each navigation. Tailwind v4 data-attribute variants (`data-[state=active]:`) handle all visual states with no custom CSS needed.

**Mobile sizing:** Dots are `w-3 h-3` (12px). The containing `<button>` tap target must be padded to 44px minimum. Wrap each dot in a `p-4` button or use `min-w-[44px] min-h-[44px] flex items-center justify-center` on the button.

**Confidence:** HIGH — Tailwind v4 data attribute variant support confirmed; ARIA pattern from W3C APG ([w3.org/WAI/ARIA/apg/](https://www.w3.org/WAI/ARIA/apg/)); `aria-current="step"` documented at [aditus.io/aria/aria-current/](https://www.aditus.io/aria/aria-current/).

---

### 5. Mascot Image — WebP with SVG Fallback Strategy

**Technology:** HTML `<picture>` element, WebP primary, SVG or PNG fallback
**Purpose:** Display the Ravemonger mascot on wizard steps without degrading mobile load time
**Why WebP not SVG for a mascot:** SVG is ideal for simple geometric illustrations (icons, logos). A character mascot with shading, texture, or detail is likely a raster artwork export. SVG rendering of complex paths adds CPU overhead on every frame (especially during animation). WebP at quality 80–85 typically delivers 25–34% smaller files than PNG with no perceptible quality loss on mobile displays.
**Why NOT AVIF as primary:** AVIF offers ~20% better compression than WebP but has 93.8% browser support vs WebP's 95.3%. For this app targeting broad mobile, WebP as primary with PNG fallback is the safer default. AVIF can be layered in as a `<source>` in front of WebP when the asset pipeline supports it.

**Pattern:**

```html
<picture>
  <source srcset="/static/img/ravemonger-welcome.webp" type="image/webp">
  <img
    src="/static/img/ravemonger-welcome.png"
    alt="The Ravemonger, your rave tips guide"
    width="240"
    height="240"
    class="w-40 h-40 sm:w-48 sm:h-48 object-contain mx-auto"
    loading="eager"
    decoding="async">
</picture>
```

**Size guidance:** Export the mascot at 2x maximum display size (so 320px × 320px for a 160px display slot). Do not embed multiple densities via `srcset` for a single mascot image — the browser will choose the first WebP source regardless of DPR, and the CSS will scale it via `object-contain`. This avoids over-engineering a single decorative asset.

**Asset placement:** `/static/img/ravemonger-welcome.webp` and `ravemonger-welcome.png`. Keep character variants (e.g., "waving", "pointing", "celebrating") as separate files rather than a sprite sheet, since only one variant displays at a time per step.

**Confidence:** MEDIUM — WebP vs AVIF support data from [speedvitals.com/blog/webp-vs-avif/](https://speedvitals.com/blog/webp-vs-avif/) and [frontendtools.tech/blog/modern-image-optimization-techniques-2025](https://www.frontendtools.tech/blog/modern-image-optimization-techniques-2025).

---

### 6. Accessibility Layer — Announcements for Step Changes

**Technology:** `aria-live="polite"` region + `aria-current="step"` on progress indicator
**Purpose:** Screen reader users hear step transitions without focus being forcibly moved
**Why mandatory:** WCAG 2.2 SC 4.1.3 (Status Messages) requires dynamic content updates to be communicated to assistive technology without requiring focus change.

**Pattern:**

```html
<!-- Invisible live region, always present in DOM -->
<div aria-live="polite" aria-atomic="true" class="sr-only" id="wizard-announcement"></div>
```

```javascript
function announceStep(stepLabel) {
  const el = document.getElementById('wizard-announcement');
  el.textContent = '';                // Clear first to force re-announcement
  requestAnimationFrame(() => {
    el.textContent = `Step ${WizardState.currentStep + 1} of ${WizardState.totalSteps}: ${stepLabel}`;
  });
}
```

The `requestAnimationFrame` flush-and-set pattern is required because setting the same text twice in succession is ignored by some screen readers — clearing first then resetting in the next frame reliably triggers a new announcement.

**Confidence:** HIGH — ARIA live region pattern from MDN ([developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live)) and WCAG 2.2 SC 4.1.3.

---

## What NOT to Add

| Candidate | Decision | Rationale |
|-----------|----------|-----------|
| Alpine.js | Do not add | Adds 14KB+ dependency for patterns achievable with 50–80 lines of vanilla JS. Introduces a second mental model for future maintainers unfamiliar with Alpine directives. The wizard's JS surface is small and bounded. |
| HTMX | Do not add | HTMX excels at replacing content via server round-trips. Wizard step navigation is purely client-side state — no server data needed between steps until final submission. Adding HTMX here is architectural mismatch, not simplification. |
| React / any SPA framework | Do not add | Incompatible with existing Jinja2 server-rendering model. Rewrite cost unjustifiable. |
| Animate.css | Do not add | Full library for one animation use case. The `@keyframes` pattern above is 20 lines and zero bytes of library overhead. |
| View Transition API | Defer | Became Baseline Newly Available in October 2025 (Firefox 144). Good progressive enhancement candidate in a later phase. Not the primary technique for this milestone due to recency. |
| `@starting-style` | Defer | Baseline support incomplete for `transition-behavior: allow-discrete` on `display` in Firefox as of research date. Revisit as enhancement after core wizard ships. |
| Lottie / JSON animations | Do not add | Character mascot does not require motion beyond CSS-driven transitions. Lottie adds ~40KB library overhead for a decorative feature. |

---

## Tailwind CSS v4 CDN Constraints to Respect

The app uses the CDN (`@tailwindcss/browser@4`) rather than a build pipeline. This means:

1. `@apply` is NOT available — write utility classes directly in HTML, not via `@apply` in style blocks.
2. Custom `@keyframes` and `@theme` tokens work via `<style type="text/tailwindcss">` — confirmed working in CDN mode.
3. All wizard-specific styles must live in that `<style type="text/tailwindcss">` block or as inline Tailwind utilities — no PostCSS plugins, no `tailwind.config.js`.
4. The CDN is development-appropriate for this app's deployment model. If a build pipeline is introduced in future, migration of `@theme` declarations to a CSS file is trivial.

**Confidence:** HIGH — CDN constraints documented at [tailwindcss.com/docs/installation/play-cdn](https://tailwindcss.com/docs/installation/play-cdn) and confirmed via GitHub discussions ([#16041](https://github.com/tailwindlabs/tailwindcss/discussions/16041), [#16482](https://github.com/tailwindlabs/tailwindcss/discussions/16482)).

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Step transitions | CSS `@keyframes` + JS class toggling | CSS `@starting-style` + `transition-behavior` | Incomplete Firefox support for `allow-discrete` on `display` |
| Step transitions | CSS `@keyframes` + JS class toggling | View Transition API | Too new (Baseline Oct 2025), adds complexity for this milestone |
| State management | Vanilla JS object + `sessionStorage` | URL hash routing | Entangles wizard with browser history; breaks back-button UX |
| State management | Vanilla JS object + `sessionStorage` | Alpine.js reactive state | External dependency for bounded problem |
| Image format | WebP + PNG fallback | SVG | Mascot is likely raster art; complex SVG renders slower than pre-rasterized WebP |
| Image format | WebP + PNG fallback | AVIF primary | 93.8% support vs WebP's 95.3%; mobile safety margin favors WebP |
| Progress indicator | Tailwind utility dots on `<ol>` | Third-party stepper component | Zero-dep solution covers all requirements; external component adds CSS conflicts |

---

## No Installation Required

All techniques are browser-native CSS and JavaScript. The only authoring concern is adding the `<style type="text/tailwindcss">` block with `@keyframes` declarations to the wizard template, and creating a `wizard.js` static file (or `<script>` block).

No new `pip install`, no new `npm install`.

---

## Sources

- Tailwind CSS v4 announcement and CDN docs: [tailwindcss.com/blog/tailwindcss-v4](https://tailwindcss.com/blog/tailwindcss-v4)
- Tailwind CSS Play CDN: [tailwindcss.com/docs/installation/play-cdn](https://tailwindcss.com/docs/installation/play-cdn)
- Tailwind v4 transition utilities: [tailwindcss.com/docs/transition-property](https://tailwindcss.com/docs/transition-property)
- Tailwind v4 animation utilities: [tailwindcss.com/docs/animation](https://tailwindcss.com/docs/animation)
- `@starting-style` MDN reference: [developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@starting-style](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@starting-style)
- Entry/exit animations now Baseline: [web.dev/blog/baseline-entry-animations](https://web.dev/blog/baseline-entry-animations)
- Chrome Dev entry/exit animations: [developer.chrome.com/blog/entry-exit-animations](https://developer.chrome.com/blog/entry-exit-animations)
- View Transition API MDN: [developer.mozilla.org/en-US/docs/Web/API/View_Transition_API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API)
- View Transitions 2025 update: [developer.chrome.com/blog/view-transitions-in-2025](https://developer.chrome.com/blog/view-transitions-in-2025)
- ARIA live regions MDN: [developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live)
- `aria-current` step pattern: [aditus.io/aria/aria-current/](https://www.aditus.io/aria/aria-current/)
- ARIA Authoring Practices Guide: [w3.org/WAI/ARIA/apg/](https://www.w3.org/WAI/ARIA/apg/)
- WebP vs AVIF 2025: [speedvitals.com/blog/webp-vs-avif/](https://speedvitals.com/blog/webp-vs-avif/)
- Image optimization 2025: [frontendtools.tech/blog/modern-image-optimization-techniques-2025](https://www.frontendtools.tech/blog/modern-image-optimization-techniques-2025)
- SVG vs PNG performance: [dev.to/ugurkellecioglu/optimizing-web-performance-the-benefits-of-using-svgs-over-pngs-385c](https://dev.to/ugurkellecioglu/optimizing-web-performance-the-benefits-of-using-svgs-over-pngs-385c)
- Multi-step forms without frameworks: [dev.to/hexshift/multi-step-html-forms-without-frameworks-a-practical-walkthrough-chf](https://dev.to/hexshift/multi-step-html-forms-without-frameworks-a-practical-walkthrough-chf)
- Vanilla JS state management: [medium.com/@asierr/back-to-basics-mastering-state-management-in-vanilla-javascript-e3be7377ac46](https://medium.com/@asierr/back-to-basics-mastering-state-management-in-vanilla-javascript-e3be7377ac46)
- HyperUI Tailwind step components: [hyperui.dev/components/application/steps](https://www.hyperui.dev/components/application/steps)
- Tailwind multi-step form example: [tailwindflex.com/@wavy-kits/multi-step-form-with-progress-tracker](https://tailwindflex.com/@wavy-kits/multi-step-form-with-progress-tracker)
