# Phase 2: Authentication - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement user authentication (registration, login, logout, sessions), Privacy Policy with explicit consent, AND migrate the UI to Tailwind CSS with mobile-first responsive design. This phase combines backend auth with frontend modernization because the new auth pages should be built mobile-first from the start, and existing pages need responsive updates to support the multi-user experience.

</domain>

<audit>
## Mobile & Multi-User Audit

### Mobile Readiness Issues Found

| File | Line(s) | Issue | Severity |
|------|---------|-------|----------|
| base.html | 58-62 | Navigation has no mobile breakpoint, will overflow | High |
| base.html | - | No hamburger menu pattern | High |
| dashboard.html | 83-84, 549-576 | Context menu uses right-click only, no mobile equivalent | Medium |
| dashboard.html | 232-240 | Filter buttons have small tap targets (0.25rem padding) | Medium |
| rules.html | 201-226 | Rule items may overflow on narrow screens | Medium |
| rules.html | 237-254 | Notify toggle buttons very small | Medium |
| All templates | - | No media queries or responsive breakpoints | High |

### Single-User Assumptions Found

| File | Line(s) | Issue | Fix Required |
|------|---------|-------|--------------|
| routes.py | 33-35 | get_upcoming_events/get_all_rules return all data | Scope to user (Phase 3) |
| routes.py | 68 | get_all_rules returns ALL rules | Scope to user (Phase 3) |
| routes.py | 96-113 | add_rule creates without user_id | Assign user_id (Phase 3) |
| routes.py | 117-152 | toggle/delete rule has no ownership check | Add ownership check (Phase 3) |
| routes.py | 302-329 | api_add_rule no user_id | Assign user_id (Phase 3) |

Note: Most single-user fixes belong in Phase 3 (Multi-Tenant Access). Phase 2 focuses on creating the authentication infrastructure that Phase 3 will use.

### CSS Architecture

**Current state:**
- ~340 lines inline CSS in base.html
- CSS custom properties for theming (good foundation)
- No responsive breakpoints
- No media queries
- Inconsistent component styling across templates

**Migration approach:**
- Add Tailwind CSS via CDN (simple, no build step)
- Keep CSS custom properties for dark theme colors
- Replace utility classes incrementally
- Add responsive navigation component

</audit>

<decisions>
## Implementation Decisions

### Tailwind CSS Integration
- Use CDN for simplicity (no build pipeline required)
- Keep existing CSS custom properties for theme colors (--bg-dark, --accent, etc.)
- Migrate templates incrementally during Phase 2
- Add Tailwind config via script tag for custom colors

### Mobile Navigation
- Hamburger menu icon on mobile (< 768px)
- Slide-out panel or dropdown for nav links
- User menu (when logged in) with logout button

### Authentication Flow
- Session-based auth with secure cookies (not JWT)
- Passwords hashed with Argon2id (already implemented in Phase 1)
- Session stored server-side (database or in-memory)
- Cookie: httponly, secure (when HTTPS), samesite=lax

### New Templates Required
- login.html - Email/password form, "Register" link
- register.html - Email/password/display_name form (all required), consent checkbox, "Login" link
- privacy.html - Privacy Policy page (static content)
- All pages must be mobile-first responsive using Tailwind

### Privacy & Consent
- Privacy Policy page at /privacy explaining:
  - Data collected: email address, display name, password (hashed), session cookies, Telegram chat ID (optional)
  - How data is stored: SQLite database, Argon2id password hashing, httponly session cookies
  - Data retention: sessions expire after 30 days of inactivity
  - No third-party sharing (except Telegram API for notifications)
- Registration form includes:
  - Unticked checkbox: "I have read and agree to the Privacy Policy"
  - Link to /privacy opens in new tab
  - Form cannot submit without checkbox being ticked
- GDPR/privacy-conscious approach: explicit, informed consent

### Session Storage
- Database table (sessions) with columns: id, user_id, token, created_at, expires_at
- Persistent across server restarts
- Allows session revocation and audit trail

### Session Timeout
- Configurable in config.yaml
- Default: 30 days
- Sliding expiration: timeout resets on each authenticated request
- Active users stay logged in; 30 days of inactivity triggers logout

### Anonymous Mode Transition
- If no users exist, show registration page as landing
- After first user registers, they become admin
- Subsequent visitors see login page

### Route Protection Strategy
- FastAPI dependency injection for auth check
- Protected routes: /, /rules, /settings, /actions/*, /api/*
- Public routes: /login, /register, /privacy, /static/*

</decisions>

<specifics>
## Specific Implementation Notes

### Tailwind CDN Setup
```html
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {
    theme: {
      extend: {
        colors: {
          'bg-dark': '#1a1a2e',
          'bg-card': '#16213e',
          'accent': '#e94560',
          'accent-hover': '#ff6b6b',
        }
      }
    }
  }
</script>
```

### Mobile Navigation Pattern
- Logo on left, hamburger on right (mobile)
- Logo on left, nav links on right (desktop)
- Logged-in state shows user display name + logout

### Registration Form
- Required fields: Email, Password, Display Name
- Display name shown in nav bar when logged in
- Password: Minimum 8 characters, no complexity requirements (NIST 2024 guidance)
- Show password toggle for usability
- Consent checkbox (unticked by default): "I have read and agree to the Privacy Policy"
- Privacy Policy link opens in new tab
- Submit button disabled until consent checkbox is ticked

### Context Menu Mobile Fix
- Tap artist row to expand, revealing "Track Artist" button
- Clean UI: button hidden until user taps to expand
- Consistent with existing expand pattern for event details
- Desktop: Keep right-click context menu as power-user shortcut

</specifics>

<resolved>
## Resolved Gray Areas

| Area | Decision | Rationale |
|------|----------|-----------|
| Session storage | Database table | Persistent across restarts, more reliable |
| Session expiration | Sliding | Reset timeout on activity, active users stay logged in |
| Default timeout | 30 days | Convenience for personal tracker, minimal re-logins |
| Mobile track artist | Tap to expand + button | Clean UI, tap artist row to see Track button |
| Registration fields | Email + Password + Display name (all required) | Collect display name upfront for nav bar |
| Privacy consent | Explicit unticked checkbox | GDPR-compliant, informed consent required |
| Notification channels | Telegram and/or Email (Phase 4) | Users choose preferred channel(s) |
| Email for notifications | Login email only (v1) | Prevents spam to others; separate email deferred to v2 with verification |
| Channel ownership | Telegram: bot code proves ownership; Email: uses login email | No unverified third-party notifications |
| Email unsubscribe | One-click token link in every email | No login required, CAN-SPAM compliant |
| Telegram unsubscribe | /stop bot command | Simple, no inline buttons needed |

</resolved>

<deferred>
## Deferred to Later Phases

- Ownership checks on rules (Phase 3)
- User-scoped queries (Phase 3)
- Notification channel config - Telegram and/or Email (Phase 4)
- Email notification SMTP setup (Phase 4)
- Email one-click unsubscribe with signed tokens (Phase 4)
- Telegram /stop command handler (Phase 4)
- Rate limiting on login (v2)
- Password reset flow (v2)
- Email verification on registration (v2)
- Separate notification email with verification (v2)

</deferred>

---

*Phase: 02-authentication*
*Context gathered: 2026-01-24*
*Updated: 2026-01-24 - Added privacy policy, consent requirements, notification channel decisions*
