# Phase 3: Multi-Tenant Access - Context

**Gathered:** 2026-01-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Scope data access to the logged-in user. Rules and notifications become user-specific while events remain shared. Admin capabilities for viewing (not modifying) all rules.

</domain>

<decisions>
## Implementation Decisions

### Legacy data migration
- Assign all existing rules and notifications to the first registered user (admin)
- Migration happens automatically on first user registration
- Show dashboard message: "X rules and Y notifications from previous setup have been assigned to your account"

### Data visibility boundaries
- Users are completely isolated — no indication other users exist
- Users only see events that match their OWN rules (not other users' matches)
- Event fetching is shared (one scheduler fetches all tracked areas efficiently)
- Areas are user-scoped — each user configures their own cities to track

### Rule ownership
- Rules are strictly isolated — no sharing mechanism (deferred to future)
- No admin transfer of rules between users
- No rule duplication feature
- If user account is deleted, cascade delete their rules and notifications

### Admin capabilities
- Admin can view all users' rules (read-only, no edit/delete)
- Minimal user management: admin can see list of registered users but no management actions
- Admin pages under separate /admin/* path, not in regular navigation

### Claude's Discretion
- Exact dashboard message wording for legacy migration
- How to display user list in admin section
- Navigation pattern for admin section access

</decisions>

<specifics>
## Specific Ideas

- Keep the experience feeling like single-user to each person — complete isolation
- Admin oversight is for monitoring, not control — view-only access to rules
- Efficient shared event fetching despite user-scoped visibility

</specifics>

<deferred>
## Deferred Ideas

- Rule sharing between users — future phase
- Admin ability to transfer rule ownership — future phase
- Admin ability to edit/delete other users' rules — may never need this

</deferred>

---

*Phase: 03-multi-tenant-access*
*Context gathered: 2026-01-27*
