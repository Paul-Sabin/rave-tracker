# Phase 19: Database Foundation - Research

**Researched:** 2026-03-01
**Domain:** SQLite/PostgreSQL migration — adding a boolean column with conditional backfill, User dataclass extension, Database method
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOUND-01 | Database migration adds `onboarding_completed` column with existing-user backfill | Migration pattern documented; SQLite ADD COLUMN + UPDATE backfill; PG ADD COLUMN IF NOT EXISTS; User dataclass field; set_onboarding_completed() method |
</phase_requirements>

---

## Summary

Phase 19 adds a single boolean column `onboarding_completed` to the `users` table, backfills existing users based on whether they have a configured local area or Telegram account, and exposes a `Database.set_onboarding_completed()` method for the wizard completion handler (Phase 22). This is the lowest-risk phase in the v3.4 milestone: it touches only the database layer, no templates, no routes.

The project has a well-established migration pattern (MIGRATIONS list in database.py, numbered sequentially from 1 to 13). Migration 14 follows that same pattern exactly. The tricky part is the backfill UPDATE, which must run as a separate migration entry from the ADD COLUMN because SQLite does not allow DDL and DML in the same executescript statement sequence — each migration in MIGRATIONS is run individually with try/except for idempotency. For PostgreSQL the backfill UPDATE is safe to run in the same autocommit context.

The User dataclass is not centralized through a `_row_to_user()` helper — it is constructed inline in six separate query methods (get_user_by_email, get_user_by_id, get_unverified_user_by_email, get_user_by_telegram_chat_id, get_users_pending_purge, and get_all_users). ALL of these must have `onboarding_completed` added to their instantiation call, or the attribute will be missing when those methods are called after migration.

**Primary recommendation:** Add migration 14 as two MIGRATIONS entries (ADD COLUMN, then UPDATE backfill), add `onboarding_completed: bool = False` to the User dataclass, update all six User instantiation sites in database.py, and add `Database.set_onboarding_completed()` following the exact pattern of `Database.set_email_verified()`.

---

## Standard Stack

### Core

| Component | Version | Purpose | Notes |
|-----------|---------|---------|-------|
| Python sqlite3 | stdlib | SQLite migration execution | Used in SQLite mode; `conn.execute()` with try/except OperationalError |
| psycopg2 | >=2.9.0 (from requirements.txt) | PostgreSQL migration execution | Used in PG mode; autocommit=True context; "ADD COLUMN IF NOT EXISTS" transform |
| Python dataclasses | stdlib | User model definition | `@dataclass` with `field(default=...)` |

No new packages are required for this phase.

**Installation:** None needed.

---

## Architecture Patterns

### Recommended Project Structure

No new files are needed. All changes are within:

```
ra-tracker/
└── ra_tracker/
    └── database.py    # MIGRATIONS list, User dataclass, Database class methods
```

### Pattern 1: Adding a Migration Entry

The project uses a simple numbered list `MIGRATIONS: list[str]` in `database.py`. Each entry is a raw SQL string. SQLite runs them in sequence with `try/except sqlite3.OperationalError` (already-exists is silently skipped). PostgreSQL transforms them via string replacement and runs each under `autocommit=True`.

**What:** Append new entries to the end of the MIGRATIONS list.
**When to use:** Whenever the schema needs to change on an existing database.

```python
# Source: ra-tracker/ra_tracker/database.py — existing MIGRATIONS pattern
MIGRATIONS = [
    # ...existing migrations 1-13...

    # Migration 14: Add onboarding_completed for wizard gating (v3.4)
    """
    ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0;
    """,
    # Migration 14b: Backfill existing users who have completed implicit onboarding
    # Users with a local area set OR Telegram linked are considered already onboarded
    """
    UPDATE users SET onboarding_completed = 1
    WHERE local_area_id IS NOT NULL OR telegram_chat_id IS NOT NULL;
    """,
]
```

**Critical:** The ADD COLUMN entry MUST come before the UPDATE entry in the list. SQLite's per-entry try/except means the UPDATE can only succeed after the column exists.

### Pattern 2: PostgreSQL Transformation

The existing `init_schema()` PostgreSQL branch applies these string replacements to each MIGRATIONS entry before executing:

| Find | Replace | Effect |
|------|---------|--------|
| `"ADD COLUMN "` | `"ADD COLUMN IF NOT EXISTS "` | Idempotent re-runs |
| `"DATETIME"` | `"TIMESTAMP"` | Type compatibility |
| `"DEFAULT 0"` | `"DEFAULT FALSE"` | Boolean literal |
| `"DEFAULT 1"` | `"DEFAULT TRUE"` | Boolean literal |

The UPDATE backfill migration needs no transformation — `IS NOT NULL`, `OR`, and `SET` are identical across SQLite and PostgreSQL.

**Verify:** The backfill migration string `DEFAULT 0` does not appear in the UPDATE statement, so no accidental transformation risk.

### Pattern 3: User Dataclass Field

```python
# Source: ra-tracker/ra_tracker/database.py — existing User dataclass (lines 469-485)
@dataclass
class User:
    """User account for multi-tenant support."""
    id: Optional[int]
    email: str
    password_hash: str = field(repr=False)
    display_name: str = ""
    is_admin: bool = False
    email_verified: bool = False
    telegram_chat_id: Optional[int] = None
    telegram_enabled: bool = False
    email_enabled: bool = True
    local_area_id: Optional[int] = None
    local_area_name: str = ""
    created_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    scheduled_purge_at: Optional[datetime] = None
    # ADD THIS FIELD:
    onboarding_completed: bool = False  # True after wizard completion or backfill
```

**Position matters:** Python dataclass fields with defaults must come after fields without defaults. All existing fields already have defaults except `id` and `email`. The new field can be placed anywhere after `email_enabled`.

### Pattern 4: DB Method (follows set_email_verified exactly)

```python
# Source: ra-tracker/ra_tracker/database.py — set_email_verified at line 903
def set_onboarding_completed(self, user_id: int, completed: bool = True) -> None:
    """Set a user's onboarding completion status.

    Args:
        user_id: User ID to update
        completed: Completion status (default True)
    """
    with self.get_connection() as conn:
        conn.execute(
            f"UPDATE users SET onboarding_completed = {self.ph} WHERE id = {self.ph}",
            (completed, user_id)
        )
```

### Pattern 5: User Instantiation Sites (ALL must be updated)

There is no `_row_to_user()` helper. The User object is instantiated inline in six places. Every site needs `onboarding_completed=bool(row["onboarding_completed"]) if row["onboarding_completed"] is not None else False`.

| Method | Approx Line | Status |
|--------|-------------|--------|
| `get_user_by_email` | ~826 | Must update |
| `get_user_by_id` | ~850 | Must update |
| `get_unverified_user_by_email` | ~935 | Must update |
| `get_user_by_telegram_chat_id` | ~959 | Must update |
| `get_users_pending_purge` | ~1194 | Must update |
| `get_all_users` (admin) | ~2135 | Must update |

**Consistent pattern to use at each site:**
```python
onboarding_completed=bool(row["onboarding_completed"]) if row["onboarding_completed"] is not None else False,
```

This matches the pattern already used for `telegram_enabled` and `email_enabled` (both handle None from legacy rows that predate the column).

### Anti-Patterns to Avoid

- **Single MIGRATIONS entry combining DDL and DML:** Do NOT write `ALTER TABLE ... ADD COLUMN ...; UPDATE users SET ...` in one string. SQLite's `executescript` auto-commits between statements but `conn.execute()` (used per migration entry) does not allow multi-statement strings. Keep ADD COLUMN and UPDATE as separate list entries.
- **Using DEFAULT TRUE/FALSE in the SQLite migration directly:** SQLite does not support `TRUE`/`FALSE` literals (it uses `1`/`0`). The PG transformer handles the conversion — write `DEFAULT 0` in the SQLite-style migration string.
- **Forgetting the "if not None" guard in User instantiation:** After migration, pre-migration rows seen via SQLite or PG will have `NULL` for `onboarding_completed` if somehow the column addition ran but the backfill didn't. The `if row["onboarding_completed"] is not None else False` guard prevents `bool(None)` returning `False` silently but also prevents an attribute error if the column is truly absent (would raise KeyError, which is preferable to silent data corruption).
- **Not updating PG_SCHEMA:** The `PG_SCHEMA` string defines the schema for FRESH PostgreSQL databases (not migrated ones). It must also include `onboarding_completed BOOLEAN DEFAULT FALSE` in the `users` CREATE TABLE statement. Otherwise new Railway deployments from scratch will be missing the column.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Migration versioning | Custom migration tracker with a versions table | Existing MIGRATIONS list pattern | Project is already committed to this approach; 13 migrations work correctly today |
| Boolean column backfill | Python loop fetching all users and updating one by one | Single UPDATE ... WHERE SQL | SQL UPDATE is atomic, runs server-side, handles millions of rows; Python loop requires N round-trips |
| PG/SQLite type abstraction | New helper to generate type names | Existing string replacement in init_schema() | Already handles DATETIME→TIMESTAMP and 0/1→TRUE/FALSE; no new abstraction needed |

**Key insight:** The migration system's simplicity (list of SQL strings + try/except) is intentional. The project explicitly rejected SQLAlchemy ORM ("raw SQL works, migration high-effort low-payoff" — PROJECT.md). Do not introduce Alembic or any migration framework for a single column add.

---

## Common Pitfalls

### Pitfall 1: PG_SCHEMA Not Updated for Fresh Installs

**What goes wrong:** New deployments (or a developer wiping and recreating the PostgreSQL database) will be missing `onboarding_completed` because `PG_SCHEMA` is the fresh-install schema and it won't have the column. Migrations only run on top of an existing schema; they don't add to `PG_SCHEMA` automatically.

**Why it happens:** The project maintains two schema representations — `SCHEMA` (SQLite fresh install), `PG_SCHEMA` (PostgreSQL fresh install), and `MIGRATIONS` (incremental patches). Developers forget to update all three.

**How to avoid:** Update `PG_SCHEMA`'s `users` CREATE TABLE to include `onboarding_completed BOOLEAN DEFAULT FALSE`. Update `SCHEMA`'s `users` CREATE TABLE to include `onboarding_completed BOOLEAN DEFAULT 0`.

**Warning signs:** A fresh-install test on SQLite or PG fails with "no such column: onboarding_completed" when calling `set_onboarding_completed()`.

### Pitfall 2: Backfill Migration Silently No-ops

**What goes wrong:** If the backfill UPDATE runs before the ADD COLUMN in the MIGRATIONS list, it succeeds (UPDATE on a valid table with valid conditions is legal even if the SET column doesn't exist... actually it will fail). But more subtly: if the try/except catches the ADD COLUMN failure and skips it, the backfill UPDATE will then fail with "no such column" and also be silently swallowed.

**Why it happens:** SQLite `try/except sqlite3.OperationalError` in `init_schema()` silently skips ANY OperationalError — not just "column already exists". If the ADD COLUMN fails for any other reason, the backfill is also skipped.

**How to avoid:** Test migrations locally by deleting the local SQLite database and re-running `init_schema()` to verify both entries execute cleanly. Also verify the production PostgreSQL schema after deployment.

**Warning signs:** After deployment, all existing users have `onboarding_completed = FALSE` when they should be `TRUE` (they'd see the wizard unexpectedly).

### Pitfall 3: Missing User Instantiation Sites

**What goes wrong:** Forgetting to add `onboarding_completed` to one of the six User construction sites causes `AttributeError: 'User' object has no attribute 'onboarding_completed'` at runtime when that specific query path is exercised.

**Why it happens:** There is no `_row_to_user()` helper to update in one place. The attribute is added to the dataclass with a default of `False`, so Python won't complain at dataclass construction time — but the value from the DB will be ignored, causing stale data.

**How to avoid:** Use grep to find all `User(` instantiations in database.py and update each one. Specifically: `get_user_by_email`, `get_user_by_id`, `get_unverified_user_by_email`, `get_user_by_telegram_chat_id`, `get_users_pending_purge`, `get_all_users`.

**Warning signs:** User.onboarding_completed is always False even after the wizard is completed.

### Pitfall 4: Backfill Logic Mismatch

**What goes wrong:** The backfill condition in STATE.md is: "UPDATE WHERE local_area_id IS NOT NULL OR telegram_chat_id IS NOT NULL". If this condition is wrong (too narrow — misses users who should be marked done), existing users will unexpectedly see the wizard.

**Why it happens:** The decision was made that users with ANY configured preference (area OR Telegram) are considered onboarded. Users with neither may or may not have completed onboarding — treated conservatively as NOT completed (they'll see wizard, which is the safer outcome than silently skipping it for someone who needs it).

**How to avoid:** The backfill condition is locked per STATE.md decisions. Do not alter it. Note: Admin users should also be excluded — an admin with no area and no Telegram will see the wizard, which is acceptable behavior (they can skip it).

---

## Code Examples

### Complete Migration 14 Entries

```python
# Source: Derived from existing MIGRATIONS pattern in database.py lines 205-291
# Append to end of MIGRATIONS list after migration 13

# Migration 14: Add onboarding_completed for v3.4 wizard gating
"""
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0;
""",
# Migration 14b: Backfill — existing users with area or Telegram configured are already onboarded
"""
UPDATE users SET onboarding_completed = 1
WHERE local_area_id IS NOT NULL OR telegram_chat_id IS NOT NULL;
""",
```

### PG_SCHEMA users table update

```python
# Add to users CREATE TABLE in PG_SCHEMA (around line 384, after local_area_name):
    onboarding_completed BOOLEAN DEFAULT FALSE,
```

### SCHEMA (SQLite) users table update

```python
# Add to users CREATE TABLE in SCHEMA (around line 116, after created_at):
    onboarding_completed BOOLEAN DEFAULT 0,
```

### User dataclass field addition

```python
# Add after scheduled_purge_at field (line ~485):
onboarding_completed: bool = False  # Set True after wizard completion or backfill
```

### User instantiation update (apply to all 6 sites)

```python
# Add this line to every User(...) call in database.py
onboarding_completed=bool(row["onboarding_completed"]) if row["onboarding_completed"] is not None else False,
```

### set_onboarding_completed method

```python
def set_onboarding_completed(self, user_id: int, completed: bool = True) -> None:
    """Set a user's onboarding completion status.

    Called when the wizard is completed or skipped entirely.

    Args:
        user_id: User ID to update
        completed: Completion status (default True)
    """
    with self.get_connection() as conn:
        conn.execute(
            f"UPDATE users SET onboarding_completed = {self.ph} WHERE id = {self.ph}",
            (completed, user_id)
        )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global wizard-shown flag | Per-user `onboarding_completed` boolean | v3.4 | Enables per-user wizard gating in multi-user app |
| Alembic/SQLAlchemy migrations | Hand-rolled MIGRATIONS list | Project inception | No framework dependency; sufficient for project scale |

**Deprecated/outdated:**
- None relevant to this phase.

---

## Open Questions

1. **Should admin users be auto-marked onboarding_completed = TRUE?**
   - What we know: Migration 9 auto-verified admin users (`UPDATE users SET email_verified = 1 WHERE is_admin = 1`) to prevent lockout. Admins already have local_area_id=34 set from create_user() first-user logic.
   - What's unclear: Whether the first/admin user will match the backfill condition (they will — first user gets local_area_id=34 set in create_user, so the backfill WHERE covers them).
   - Recommendation: No special admin handling needed. The existing backfill logic covers the first/admin user automatically.

2. **Will the `DEFAULT 0` → `DEFAULT FALSE` PG transform affect the backfill UPDATE?**
   - What we know: The backfill UPDATE string is `UPDATE users SET onboarding_completed = 1 WHERE ...`. The transform replaces `"DEFAULT 0"` and `"DEFAULT 1"` — these are substring matches. The string `"= 1"` does NOT match `"DEFAULT 1"` (the transform requires the full word "DEFAULT" before the value).
   - What's unclear: Could cause issues if migration string is ever changed to use "DEFAULT 1" phrasing.
   - Recommendation: Current backfill string is safe. Confirm by reading the transform code before merging.

---

## Sources

### Primary (HIGH confidence)

- Direct codebase reading — `ra-tracker/ra_tracker/database.py` (lines 1-1200+) — full MIGRATIONS list, PG_SCHEMA, SCHEMA, User dataclass, Database class methods, init_schema() logic
- `.planning/STATE.md` — locked backfill condition: "UPDATE WHERE local_area_id IS NOT NULL OR telegram_chat_id IS NOT NULL"
- `.planning/REQUIREMENTS.md` — FOUND-01 requirement definition

### Secondary (MEDIUM confidence)

- SQLite documentation knowledge: `ALTER TABLE ... ADD COLUMN` is SQLite's only supported DDL change; multi-statement strings work in executescript but not in execute()
- PostgreSQL documentation knowledge: `ADD COLUMN IF NOT EXISTS` supported since PostgreSQL 9.6

---

## Metadata

**Confidence breakdown:**
- Migration pattern: HIGH — read actual MIGRATIONS list in codebase, pattern is crystal clear
- User dataclass/instantiation: HIGH — read all 6 User() instantiation sites directly
- Backfill logic: HIGH — condition locked in STATE.md decisions
- PG_SCHEMA gap risk: HIGH — confirmed two separate schema strings exist and both must be updated
- Test infrastructure: HIGH — no tests exist in this project; no pytest.ini found; validation is manual deployment verification

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (database.py changes in later phases could shift line numbers but not patterns)
