# Phase 6: Email Verification & Login Hardening - Context

**Gathered:** 2026-02-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Users must verify email ownership before using the application, with protection against brute-force login attempts. This phase covers: email verification flow for new users, forcing existing users to verify on login, verification email sending/resending, and login rate limiting. Password reset is Phase 7.

</domain>

<decisions>
## Implementation Decisions

### Verification Flow UX
- Hard block after signup — user sees "Check your email" page, cannot access dashboard until verified
- Verification links valid for 24 hours
- Expired link auto-sends new verification email with message: "Link expired. We've sent a new one to your inbox."
- Resend verification rate-limited to 3 per hour per email

### Email Content & Branding
- Plain text email, minimal branding — just mentions "RA Tracker" in text
- Friendly but brief tone — warm greeting, clear CTA, brief explanation
- Subject line: "Welcome to RA Tracker - verify your email"
- Explicitly mention 24-hour expiry in email body

### Rate Limit Behavior
- 5 failed login attempts in 15 minutes triggers block
- Track by both IP address AND email address (prevents distributed attacks and single-target attacks)
- Auto-expire after 15 minutes — no unlock mechanism needed, just wait
- Successful login clears failed attempt counter for that IP/email
- Claude's discretion on exact error message shown to blocked users (balance security vs UX)

### Existing User Migration
- Force verification on next login — same flow as new users, no grandfather clause
- No special messaging explaining the change — just standard verify screen
- Auto-send verification email when unverified user logs in
- Admin users (is_admin=true) are auto-marked as verified in migration to prevent lockout

### Claude's Discretion
- Exact error message when rate limit triggered (generic vs explicit)
- Loading states and micro-interactions during verification
- Email HTML formatting details (if any beyond plain text)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Key behaviors are captured above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-email-verification-login-hardening*
*Context gathered: 2026-02-02*
