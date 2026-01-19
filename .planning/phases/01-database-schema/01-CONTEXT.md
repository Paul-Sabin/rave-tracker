# Phase 1: Database Schema - Context

**Gathered:** 2026-01-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Add users table and establish foreign key relationships for multi-tenancy. Rules and notifications become user-scoped. Events remain shared globally. This phase is schema-only — authentication and route protection are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Migration Strategy
- Existing rules and notifications assigned to first registered user
- User controls deployment, will register first to claim legacy data
- Create database backup before migration (copy .db file)
- Assignment timing: Claude's discretion (on registration or first login)

### User Table Fields
- Core fields: id, email, password_hash, created_at
- Additional fields:
  - display_name (required at registration)
  - is_admin (boolean, first user gets true)
  - email_verified (boolean, for future verification feature)
- email must be unique (login identifier)
- telegram_chat_id: Claude's discretion whether to add now or in Phase 4

### Foreign Key Behavior
- user_id nullable vs required: Claude's discretion based on migration approach
- On user deletion behavior: Claude's discretion (cascade, prevent, or NULL)
- Foreign key constraint enforcement: Claude's discretion

### Default User Handling
- First registered user automatically marked as admin (is_admin=true)
- App works in anonymous mode until first user registers (backward compatible)
- Show registration banner in anonymous mode to encourage signup

### Claude's Discretion
- Exact migration timing (on registration vs first login)
- Whether to add telegram_chat_id column now or defer to Phase 4
- Foreign key nullability strategy
- User deletion cascade behavior
- SQLite PRAGMA foreign_keys enforcement

</decisions>

<specifics>
## Specific Ideas

- Backup database before migration — user wants safety net
- Anonymous mode preserves current single-user experience until someone registers
- First user is both admin and owner of legacy data

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-database-schema*
*Context gathered: 2026-01-19*
