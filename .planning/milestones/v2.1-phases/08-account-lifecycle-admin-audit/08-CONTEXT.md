# Phase 8: Account Lifecycle & Admin Audit UI - Context

**Gathered:** 2026-02-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can delete their accounts with a 30-day recovery period, and admins can view complete audit history with filtering. This phase delivers soft-delete with grace period, account recovery during grace, hard purge after grace, and admin audit log viewing.

</domain>

<decisions>
## Implementation Decisions

### Deletion Flow
- Delete account option lives in Settings page, in a "Danger Zone" section at the bottom
- Confirmation requires password only (no additional typing or checkbox)
- After deletion request: logout immediately, redirect to login, send confirmation email with recovery info
- No reminder emails during grace period — single email at deletion time only

### Recovery Experience
- Recovery initiated via normal login attempt (shows recovery prompt)
- Recovery prompt is an interstitial page: "Account scheduled for deletion on [date]. Recover account?" with Yes/No buttons
- If user declines recovery ("No, continue deletion"), logout immediately
- After successful recovery: send confirmation email AND show flash message on dashboard

### Audit Log UI
- Layout: table with filters in horizontal bar above
- Filter options: User (email/username search), Event type dropdown, Date range picker, IP address
- Table columns: Timestamp, User, Event, IP — with expandable row for JSON details
- Traditional pagination with prev/next buttons, 50 entries per page

### Data Purge Handling
- Daily cron job runs once per day to purge accounts past 30-day grace period
- Purge all user data: user record, rules, notifications, settings
- Audit log entries for purged users are anonymized (replace user_id with 'deleted_user' or hash), event data retained
- Admins see pending deletions by filtering audit log for 'account.delete_request' events

### Claude's Discretion
- Exact "Danger Zone" styling and button treatment
- Recovery page layout and wording details
- Audit log table styling, sort behavior, empty state
- Cron job implementation details and logging

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-account-lifecycle-admin-audit*
*Context gathered: 2026-02-08*
