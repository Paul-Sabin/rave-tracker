# Phase 18: Endpoint Hardening - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Server-side admin-only access control for all `/admin/*` routes. Non-admin requests are rejected at the handler level, regardless of UI state or client-side checks. Covers POST /settings/save and POST /settings/test-telegram (explicitly named in roadmap), plus any other `/admin/*` routes discovered during research audit.

</domain>

<decisions>
## Implementation Decisions

### Rejection response — form POSTs
- Non-admin hitting `POST /settings/save` (form submission): redirect to `/settings` with flash message
- Flash message text: **"The ravemonger will handle system settings."**
- Flash style: same as existing info/success flashes (no special warning/error color)

### Rejection response — AJAX endpoints
- Non-admin hitting `POST /settings/test-telegram` (AJAX): Claude picks appropriate JSON 403 response

### Guard breadth
- All `/admin/*` routes require admin at the server level — not just the two named POSTs
- `GET /admin/settings` for non-admin: redirect to `/settings`
- Guard mechanism: inline check per route (no decorator abstraction needed)
- Unauthenticated user hitting `/admin/*`: Claude decides based on existing auth patterns in the codebase

### Unauthorized attempt logging
- Log blocked attempts to server log only (no audit DB table)
- Include: user ID + endpoint path + timestamp in the log entry
- Log level: Claude decides the appropriate level

### Partial-submit and endpoint audit
- Researcher should check the actual state of `POST /settings/save` — whether Phase 16 fully separated it from system config fields or if crafted requests can still smuggle system fields
- If system fields can be submitted by non-admins via `/settings/save`: Claude decides the cleanest approach based on endpoint structure found
- Full audit of all `/admin/*` routes in the codebase — harden any admin-prefixed route that lacks a guard, not just the two roadmap-named endpoints

### Claude's Discretion
- JSON response body format for AJAX 403 rejections
- Log level for blocked access attempts
- Handling of unauthenticated (vs non-admin) requests to `/admin/*` routes
- Approach to partial-field filtering if mixed submissions are found

</decisions>

<specifics>
## Specific Ideas

- Flash message is intentionally playful/project-specific: "The ravemonger will handle system settings." — use this exact wording
- No special visual treatment for the access-denied flash — keep it consistent with normal informational messages

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 18-endpoint-hardening*
*Context gathered: 2026-02-28*
