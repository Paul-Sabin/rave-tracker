# Phase 1: Database Schema - Research

**Researched:** 2026-01-19
**Domain:** SQLite schema migration, password hashing, multi-tenancy
**Confidence:** HIGH

## Summary

This phase adds a `users` table and establishes foreign key relationships between users and the existing `rules` and `notifications` tables. The key technical challenges are: (1) SQLite's limited ALTER TABLE support requiring table recreation for adding foreign keys, (2) choosing the right password hashing algorithm, and (3) handling the migration of existing data to the first registered user.

SQLite cannot add foreign key constraints to existing tables via ALTER TABLE. Instead, we use a nullable `user_id` column approach: add the column as nullable via simple ALTER TABLE, then assign values during first user registration. This avoids the complex table recreation pattern while maintaining backward compatibility. For password hashing, Argon2id is the 2025 standard, implemented via `argon2-cffi` library.

**Primary recommendation:** Use nullable `user_id` columns added via ALTER TABLE, assign existing data on first user registration, and use `argon2-cffi` for password hashing.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| argon2-cffi | 25.1.0 | Password hashing | Won Password Hashing Competition, OWASP 2025 recommended, memory-hard (GPU resistant) |
| sqlite3 | stdlib | Database access | Already in use, no additional dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shutil | stdlib | File copy for backup | Before running migrations |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| argon2-cffi | bcrypt | bcrypt is still secure with cost factor 12+, but has 72-byte password limit and less GPU resistance |
| argon2-cffi | passlib | passlib is a wrapper, adds complexity without benefit for single-algorithm use |

**Installation:**
```bash
pip install argon2-cffi
```

## Architecture Patterns

### Recommended Migration Strategy

Given SQLite's limitations and the user decision for "anonymous mode until first user registers," the recommended approach is:

1. **Add nullable columns first** - Use simple ALTER TABLE to add `user_id INTEGER` columns to `rules` and `notifications`
2. **Create users table** - Standard CREATE TABLE with all required fields
3. **Defer assignment** - Existing rows keep `user_id = NULL` until first registration
4. **Assign on registration** - When first user registers, UPDATE all NULL user_id rows to that user

This avoids the complex 12-step table recreation process.

### Pattern 1: Nullable Foreign Key with Deferred Assignment

**What:** Add foreign key column as nullable, assign later
**When to use:** When migrating existing data to a not-yet-created parent record
**Example:**
```python
# Source: SQLite documentation, verified pattern
MIGRATIONS = [
    # Add nullable user_id to rules
    "ALTER TABLE rules ADD COLUMN user_id INTEGER;",
    # Add nullable user_id to notifications
    "ALTER TABLE notifications ADD COLUMN user_id INTEGER;",
]

# Later, on first user registration:
def assign_legacy_data(conn, user_id: int):
    conn.execute("UPDATE rules SET user_id = ? WHERE user_id IS NULL", (user_id,))
    conn.execute("UPDATE notifications SET user_id = ? WHERE user_id IS NULL", (user_id,))
```

### Pattern 2: Anonymous Mode Detection

**What:** Check if any users exist to determine app mode
**When to use:** On every request to show/hide registration banner
**Example:**
```python
# Source: SQLite forum, EXISTS is optimal for existence checks
def has_users(conn) -> bool:
    """Check if any users exist. EXISTS stops at first row found."""
    cursor = conn.execute("SELECT EXISTS(SELECT 1 FROM users LIMIT 1)")
    return bool(cursor.fetchone()[0])

def is_anonymous_mode(conn) -> bool:
    """App is in anonymous mode until first user registers."""
    return not has_users(conn)
```

### Pattern 3: Password Hashing with Argon2

**What:** Hash passwords on registration, verify on login
**When to use:** All password storage and verification
**Example:**
```python
# Source: argon2-cffi official documentation
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

# On registration
password_hash = ph.hash(plain_password)
# Store password_hash in database

# On login
try:
    ph.verify(stored_hash, plain_password)
    # Check if hash needs upgrade
    if ph.check_needs_rehash(stored_hash):
        new_hash = ph.hash(plain_password)
        # Update database with new_hash
    # Login successful
except VerifyMismatchError:
    # Login failed
    pass
```

### Pattern 4: Database Backup Before Migration

**What:** Copy database file before schema changes
**When to use:** Before any migration that modifies existing data
**Example:**
```python
# Source: Python sqlite3 documentation
import sqlite3
from datetime import datetime

def backup_database(source_path: str) -> str:
    """Create timestamped backup using SQLite backup API."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{source_path}.backup_{timestamp}"

    source = sqlite3.connect(source_path)
    backup = sqlite3.connect(backup_path)
    with backup:
        source.backup(backup)
    backup.close()
    source.close()

    return backup_path
```

### User Dataclass Design

```python
@dataclass
class User:
    id: Optional[int]
    email: str  # Login identifier, must be unique
    password_hash: str  # Argon2id hash, never store plain
    display_name: str  # Required at registration
    is_admin: bool = False  # First user gets True
    email_verified: bool = False  # For future verification
    created_at: Optional[datetime] = None

    def __post_init__(self):
        # Never include password_hash in repr for security
        pass
```

### Recommended Project Structure
```
ra_tracker/
    database.py     # Add User dataclass, users table, migration
    (no new files needed for this phase)
```

### Anti-Patterns to Avoid
- **Storing plain passwords:** Always hash with argon2-cffi, never store plain text
- **Using bcrypt for new code:** Argon2id is the 2025 standard, bcrypt is legacy-acceptable only
- **Complex table recreation:** For nullable columns, use simple ALTER TABLE instead of 12-step process
- **COUNT(*) for existence checks:** Use EXISTS which stops at first row

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | SHA256/MD5 hash | argon2-cffi | Proper salting, timing-safe comparison, memory-hard |
| Hash verification | String comparison | ph.verify() | Timing-safe, handles encoding |
| Database backup | shutil.copy() | sqlite3.backup() | Works on locked databases, atomic |
| Salt generation | random.randint() | argon2-cffi handles it | Cryptographically secure, proper length |

**Key insight:** Password hashing has subtle security requirements (timing attacks, salt handling, iteration counts) that argon2-cffi handles automatically. Rolling your own is a security risk.

## Common Pitfalls

### Pitfall 1: Foreign Keys Not Enforced by Default
**What goes wrong:** Foreign key constraints silently ignored, orphan data created
**Why it happens:** SQLite disables foreign key enforcement by default for backward compatibility
**How to avoid:** Enable per-connection with `PRAGMA foreign_keys = ON`
**Warning signs:** Can insert invalid foreign key values without error

```python
# In get_connection():
conn = sqlite3.connect(self.db_path)
conn.execute("PRAGMA foreign_keys = ON")  # Must be per-connection
```

### Pitfall 2: PRAGMA Inside Transaction Fails
**What goes wrong:** `PRAGMA foreign_keys = ON` silently ignored
**Why it happens:** PRAGMA is a no-op when a transaction is pending
**How to avoid:** Execute PRAGMA before any BEGIN or after COMMIT
**Warning signs:** Foreign keys appear enabled but constraints not enforced

### Pitfall 3: ALTER TABLE Cannot Add NOT NULL Without Default
**What goes wrong:** "Cannot add a NOT NULL column with default value NULL" error
**Why it happens:** SQLite requires existing rows to have a value
**How to avoid:** Either use nullable column, or provide constant default
**Warning signs:** Migration fails on existing database with data

```python
# BAD - fails if table has rows
"ALTER TABLE rules ADD COLUMN user_id INTEGER NOT NULL;"

# GOOD - nullable column
"ALTER TABLE rules ADD COLUMN user_id INTEGER;"

# GOOD - with default (but default must be constant, not CURRENT_TIMESTAMP)
"ALTER TABLE rules ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0;"
```

### Pitfall 4: Password Hash in repr/logs
**What goes wrong:** Password hashes exposed in logs, error messages
**Why it happens:** Dataclass auto-generates __repr__ including all fields
**How to avoid:** Use `field(repr=False)` for password_hash
**Warning signs:** Seeing $argon2id$... strings in application logs

```python
from dataclasses import dataclass, field

@dataclass
class User:
    password_hash: str = field(repr=False)  # Exclude from repr
```

### Pitfall 5: First User Race Condition
**What goes wrong:** Two users register simultaneously, both become admin
**Why it happens:** Check for existing users and insert not atomic
**How to avoid:** Use transaction with "INSERT ... WHERE NOT EXISTS" or database constraint
**Warning signs:** Multiple users with is_admin=True

## Code Examples

Verified patterns from official sources:

### Complete Users Table Schema
```sql
-- Source: Based on context decisions + SQLite best practices
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0,
    email_verified BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
```

### Migration to Add user_id Columns
```python
# Source: Existing project migration pattern
MIGRATIONS = [
    # ... existing migrations ...

    # Migration: Add user_id to rules (nullable for existing data)
    "ALTER TABLE rules ADD COLUMN user_id INTEGER;",

    # Migration: Add user_id to notifications (nullable for existing data)
    "ALTER TABLE notifications ADD COLUMN user_id INTEGER;",
]
```

### Creating First User with Admin Flag
```python
# Source: argon2-cffi docs + context decisions
from argon2 import PasswordHasher

def create_user(conn, email: str, password: str, display_name: str) -> int:
    """Create user, first user becomes admin."""
    ph = PasswordHasher()
    password_hash = ph.hash(password)

    # Check if this is first user
    is_first = not conn.execute(
        "SELECT EXISTS(SELECT 1 FROM users LIMIT 1)"
    ).fetchone()[0]

    cursor = conn.execute(
        """
        INSERT INTO users (email, password_hash, display_name, is_admin)
        VALUES (?, ?, ?, ?)
        """,
        (email, password_hash, display_name, is_first)
    )
    user_id = cursor.lastrowid

    # If first user, assign legacy data
    if is_first:
        conn.execute("UPDATE rules SET user_id = ? WHERE user_id IS NULL", (user_id,))
        conn.execute("UPDATE notifications SET user_id = ? WHERE user_id IS NULL", (user_id,))

    return user_id
```

### Password Verification
```python
# Source: argon2-cffi official documentation
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

def verify_password(stored_hash: str, plain_password: str) -> tuple[bool, str | None]:
    """
    Verify password, return (success, new_hash_if_needed).

    Returns new hash if stored hash uses outdated parameters.
    """
    ph = PasswordHasher()
    try:
        ph.verify(stored_hash, plain_password)
        # Check if hash needs upgrade
        if ph.check_needs_rehash(stored_hash):
            return True, ph.hash(plain_password)
        return True, None
    except VerifyMismatchError:
        return False, None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| bcrypt | Argon2id | 2015 (PHC winner) | Memory-hard, GPU-resistant |
| SHA256 + salt | Argon2id | N/A (SHA256 was never appropriate) | Proper key derivation |
| MD5 | Argon2id | Deprecated 2010s | MD5 is cryptographically broken |

**Deprecated/outdated:**
- **bcrypt:** Still acceptable for existing systems, but Argon2id preferred for new code
- **passlib:** Wrapper library, unnecessary complexity for single-algorithm use
- **hashlib for passwords:** hashlib is for data integrity, not password storage

## Open Questions

Things that couldn't be fully resolved:

1. **telegram_chat_id column timing**
   - What we know: User decided this is Claude's discretion
   - What's unclear: Whether adding now saves a migration later
   - Recommendation: Add now as nullable INTEGER - trivial cost, avoids future migration

2. **Foreign key enforcement decision**
   - What we know: Must be enabled per-connection, can't be inside transaction
   - What's unclear: Whether to enforce (catches bugs) or skip (simpler migration)
   - Recommendation: Enable enforcement but use nullable user_id to avoid issues with existing data

3. **ON DELETE behavior**
   - What we know: Options are CASCADE, RESTRICT, SET NULL, NO ACTION
   - What's unclear: User preference not specified
   - Recommendation: Use RESTRICT (prevent user deletion if they have rules) - safest default

## Sources

### Primary (HIGH confidence)
- [argon2-cffi PyPI](https://pypi.org/project/argon2-cffi/) - version 25.1.0, installation, basic usage
- [argon2-cffi documentation](https://argon2-cffi.readthedocs.io/) - complete API, parameters, best practices
- [SQLite Foreign Key Support](https://sqlite.org/foreignkeys.html) - official documentation on PRAGMA, enforcement
- [Python sqlite3 documentation](https://docs.python.org/3/library/sqlite3.html) - backup() API

### Secondary (MEDIUM confidence)
- [OWASP Password Hashing Guide 2025](https://guptadeepak.com/the-complete-guide-to-password-hashing-argon2-vs-bcrypt-vs-scrypt-vs-pbkdf2-2026/) - Argon2id recommendations
- [SQLite Tutorial - ALTER TABLE](https://www.sqlitetutorial.net/sqlite-alter-table/) - limitations, workarounds
- [SQLite Tutorial - EXISTS](https://www.sqlitetutorial.net/sqlite-exists/) - performance characteristics
- [Alembic Batch Migrations](https://alembic.sqlalchemy.org/en/latest/batch.html) - move-and-copy pattern (not needed for our approach)

### Tertiary (LOW confidence)
- [SQLite Forum](https://sqlite.org/forum/info/e1c0ad678526b074) - EXISTS vs COUNT performance (community discussion)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - argon2-cffi is clearly the 2025 standard, well-documented
- Architecture: HIGH - SQLite limitations are well-known, nullable column approach is established
- Pitfalls: HIGH - based on official SQLite documentation and common issues

**Research date:** 2026-01-19
**Valid until:** 2026-02-19 (30 days - stable domain, Argon2 and SQLite patterns unlikely to change)
