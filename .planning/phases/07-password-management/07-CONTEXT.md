# Phase 7: Password Management - Context

**Gathered:** 2026-02-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can reset forgotten passwords via email and change passwords when logged in. Rate-limited reset requests, secure token-based flow, audit logging of all password events.

</domain>

<decisions>
## Implementation Decisions

### Password Strength Rules
- Minimum 8 characters
- No complexity requirements (no forced uppercase/numbers/symbols — NIST guidelines)
- Visual strength meter with color bar (red/yellow/green for weak/medium/strong)
- Block top 1000 common passwords (reject if matched against breached password list)

### Reset Flow Behavior
- Always show success message on reset request ("If account exists, email sent") — don't reveal whether email is registered
- Expired/invalid token: show error message with "Request new link" button inline (not redirect)
- After successful reset: redirect to login page with "Password updated, please log in" message
- Invalidate all other active sessions after password reset (security: assume password was compromised)

### Form Validation & Feedback
- Validate on blur and on submit (not real-time keystroke)
- Eye icon toggle to show/hide password
- Single new password field (no confirm field) — rely on show/hide toggle
- Error messages appear inline below the problem field

### Security Messaging
- Reset email subject: "Reset your password" (simple, not branded)
- Include brief note in email: "If you didn't request this, you can ignore this email"
- Rate limit message: "Too many requests. Try again later." (vague timing, don't reveal exact limit)
- Password change confirmation: flash message on same page ("Password updated successfully")

### Claude's Discretion
- Strength meter implementation (library vs custom)
- Common password list source/format
- Exact email template styling (consistent with verification email from Phase 6)

</decisions>

<specifics>
## Specific Ideas

- Strength meter should feel responsive — update as user types
- Follow same email template pattern established in Phase 6 (HTML with clickable link)
- Reset token should use same itsdangerous infrastructure from email verification

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-password-management*
*Context gathered: 2026-02-07*
