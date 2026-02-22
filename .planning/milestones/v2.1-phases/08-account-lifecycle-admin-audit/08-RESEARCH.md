# Phase 8: Account Lifecycle & Admin Audit UI - Research

**Researched:** 2026-02-08
**Domain:** Account soft delete, data purge, audit log UI
**Confidence:** HIGH

## Summary

Phase 8 implements user account deletion with a 30-day recovery grace period and an admin audit log viewing UI. The codebase already has all infrastructure needed: audit logging, APScheduler, session management, and admin routes.

Key research findings:
1. **Soft delete pattern**: Use `deleted_at` timestamp column (not boolean flag) - enables grace period calculation and uniqueness handling
2. **Audit log anonymization**: Replace `user_id` with sentinel value on purge, retain event data per GDPR requirements
3. **Cron job**: APScheduler already in use with `BackgroundScheduler` - add daily `CronTrigger` job for purge
4. **Audit log UI**: Table with horizontal filter bar, expandable JSON details, traditional pagination

**Primary recommendation:** Extend existing patterns (APScheduler, audit module, admin templates) rather than introducing new dependencies.

## Standard Stack

The established libraries/tools for this domain:

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 3.x | Scheduled task execution | Already used for fetch jobs |
| SQLite | 3.x | Database with soft delete columns | Already in use |
| FastAPI | Current | Routes for delete/recovery | Already in use |
| Jinja2 | Current | Admin UI templates | Already in use |

### Supporting (Already in Project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argon2-cffi | Current | Password verification for deletion | Already used |
| itsdangerous | Current | If recovery tokens needed | Already used |

### No New Dependencies Needed
This phase extends existing infrastructure without introducing new libraries.

**Date Range Picker:**
- Use native HTML5 `<input type="date">` for filter UI
- No JavaScript date picker library needed
- Provides adequate functionality for admin filtering

**Installation:**
```bash
# No new packages required
```

## Architecture Patterns

### Database Changes

Add two columns to users table:

```sql
-- Migration 10: Add soft delete columns
ALTER TABLE users ADD COLUMN deleted_at DATETIME;
ALTER TABLE users ADD COLUMN scheduled_purge_at DATETIME;
```

**Column design:**
- `deleted_at`: Timestamp when user requested deletion (NULL = active)
- `scheduled_purge_at`: When hard purge will occur (deleted_at + 30 days)

**Why timestamp over boolean:**
- Enables grace period calculation
- Supports date-based queries for purge job
- Provides audit trail of when deletion was requested

### Soft Delete State Machine

```
ACTIVE (deleted_at = NULL)
    |
    v [User requests deletion]
PENDING_DELETION (deleted_at = NOW, scheduled_purge_at = NOW + 30 days)
    |
    +---> [User logs in during grace] --> ACTIVE (reset both to NULL)
    |
    v [30 days pass, cron job runs]
PURGED (row deleted, audit logs anonymized)
```

### Project Structure
```
ra_tracker/
    web/
        routes.py          # Add delete/recovery endpoints
        admin.py           # Add audit-log route
    scheduler/
        jobs.py            # Add daily purge job
    database.py            # Add soft delete methods
    templates/
        settings.html      # Add Danger Zone section
        recovery.html      # New: recovery prompt page
        admin/
            audit_log.html # New: audit log UI
        email/
            account_deleted.html    # New: deletion confirmation
            account_recovered.html  # New: recovery confirmation
```

### Pattern 1: Soft Delete with Password Confirmation
**What:** User initiates deletion from Settings Danger Zone
**When to use:** Account deletion request

```python
# Source: Existing codebase patterns
@router.post("/settings/delete-account")
async def delete_account(
    request: Request,
    user: User = Depends(require_verified_email),
    password: str = Form(...),
):
    db = get_db()

    # Verify password (same pattern as password change)
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    hasher = PasswordHasher()

    try:
        hasher.verify(user.password_hash, password)
    except VerifyMismatchError:
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "error": "Password incorrect",
            # ... other context
        })

    # Soft delete
    scheduled_purge = datetime.now() + timedelta(days=30)
    db.soft_delete_user(user.id, scheduled_purge)

    # Log audit event
    log_audit_event("account.delete_request", request, user_id=user.id)

    # Clear session and redirect
    db.delete_user_sessions(user.id)

    # Send confirmation email
    await send_deletion_confirmation_email(user.email, scheduled_purge)

    response = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(response)
    return response
```

### Pattern 2: Recovery During Login
**What:** Intercept login for soft-deleted users, show recovery prompt
**When to use:** Login flow modification

```python
# Source: Existing login pattern in routes.py
# Modify login to check deleted_at

user = db.get_user_by_email(email)
if user and user.deleted_at:
    # User is in grace period - show recovery prompt
    # Store temp data in session or token for recovery page
    return RedirectResponse(url=f"/recover-account?token={generate_recovery_token(user.id)}")
```

### Pattern 3: Cron Job for Daily Purge
**What:** Daily job to hard-delete accounts past grace period
**When to use:** Scheduled background task

```python
# Source: APScheduler documentation, existing jobs.py pattern
from apscheduler.triggers.cron import CronTrigger

def purge_expired_accounts():
    """Daily job: permanently delete accounts past 30-day grace period."""
    logger.info("Starting account purge job")

    db = get_db()
    now = datetime.now()

    # Find accounts to purge
    expired_users = db.get_users_pending_purge(before=now)

    for user in expired_users:
        try:
            # Anonymize audit logs
            db.anonymize_audit_logs_for_user(user.id)

            # Delete all user data (cascade)
            db.hard_delete_user(user.id)

            logger.info(f"Purged user {user.id}")
        except Exception as e:
            logger.error(f"Failed to purge user {user.id}: {e}")

    logger.info(f"Purge complete. {len(expired_users)} accounts deleted.")

# In start_scheduler():
scheduler.add_job(
    purge_expired_accounts,
    trigger=CronTrigger(hour=3, minute=0),  # Run at 3 AM
    id="purge_expired_accounts",
    name="Purge accounts past 30-day grace period",
    replace_existing=True,
)
```

### Pattern 4: Audit Log Anonymization
**What:** Replace user_id with sentinel value, retain event data
**When to use:** User purge (GDPR compliance)

```python
# Source: GDPR requirements research
def anonymize_audit_logs_for_user(self, user_id: int) -> int:
    """Anonymize audit logs for a purged user.

    Replaces user_id with NULL or sentinel, retains event data.
    Per AUDIT-10 and CONTEXT.md: forever retention, anonymize on purge.
    """
    with self.get_connection() as conn:
        # Add details about anonymization
        cursor = conn.execute(
            """
            UPDATE audit_logs
            SET user_id = NULL,
                details = json_set(
                    COALESCE(details, '{}'),
                    '$.anonymized', 1,
                    '$.original_user_id_hash', ?
                )
            WHERE user_id = ?
            """,
            (hashlib.sha256(str(user_id).encode()).hexdigest()[:8], user_id)
        )
        return cursor.rowcount
```

### Pattern 5: Audit Log Query with Filters
**What:** Paginated query with multiple optional filters
**When to use:** Admin audit log UI

```python
# Source: Existing database pattern
def get_audit_logs_filtered(
    self,
    user_id: Optional[int] = None,
    event_type: Optional[str] = None,
    ip_address: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[dict], int]:
    """Query audit logs with filters. Returns (logs, total_count)."""
    with self.get_connection() as conn:
        # Build query dynamically
        where_clauses = ["1=1"]
        params = []

        if user_id is not None:
            where_clauses.append("user_id = ?")
            params.append(user_id)

        if event_type:
            where_clauses.append("event_type LIKE ?")
            params.append(f"{event_type}%")

        if ip_address:
            where_clauses.append("ip_address LIKE ?")
            params.append(f"{ip_address}%")

        if start_date:
            where_clauses.append("timestamp >= ?")
            params.append(start_date.isoformat())

        if end_date:
            where_clauses.append("timestamp <= ?")
            params.append(end_date.isoformat())

        where_sql = " AND ".join(where_clauses)

        # Count total
        count = conn.execute(
            f"SELECT COUNT(*) FROM audit_logs WHERE {where_sql}",
            params
        ).fetchone()[0]

        # Fetch page
        query = f"""
            SELECT al.*, u.email, u.display_name
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE {where_sql}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        logs = [dict(row) for row in cursor.fetchall()]

        return logs, count
```

### Anti-Patterns to Avoid
- **Boolean soft delete flag:** Use timestamp instead - enables grace period math
- **Hardcoded grace period:** Store `scheduled_purge_at` in DB, not calculated at query time
- **Blocking purge job:** Run in background, don't block web requests
- **Deleting audit logs:** Anonymize per GDPR, retain event history per AUDIT-10

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Scheduled daily jobs | Custom cron parsing | APScheduler CronTrigger | Already in project, handles edge cases |
| Password verification | Manual hash compare | Argon2 `verify()` | Timing-safe, already used |
| Session invalidation | Manual token deletion | `db.delete_user_sessions()` | Already exists in database.py |
| Email templating | String concatenation | Jinja2 templates | Already used for verification emails |

**Key insight:** All building blocks exist in the codebase. This phase is integration work, not greenfield development.

## Common Pitfalls

### Pitfall 1: Login Loop on Deleted Account
**What goes wrong:** User in grace period logs in, gets redirected to recovery, clicks "No", gets redirected to login, loops
**Why it happens:** Forgetting to invalidate session after "decline recovery"
**How to avoid:** After "No, continue deletion" - ensure session is cleared and redirect to login with message
**Warning signs:** User complains they can't access login page

### Pitfall 2: Cascade Delete Breaking Foreign Keys
**What goes wrong:** Hard delete fails because foreign key constraints
**Why it happens:** SQLite FK constraints enabled, user data has references
**How to avoid:** Delete in correct order: rules -> notifications -> sessions -> user. Or use CASCADE in schema.
**Warning signs:** IntegrityError on purge job

### Pitfall 3: Audit Log NULL User Display
**What goes wrong:** Admin UI shows "Unknown" for anonymized users instead of meaningful indicator
**Why it happens:** Template checks `user_id` but doesn't check anonymization flag
**How to avoid:** Check `details.anonymized` flag in template, display "[Deleted User]"
**Warning signs:** All old events show "Unknown" after any user deletion

### Pitfall 4: Timezone Confusion in Grace Period
**What goes wrong:** Grace period ends early/late depending on server timezone
**Why it happens:** Using local datetime vs UTC inconsistently
**How to avoid:** Use UTC consistently. Store `scheduled_purge_at` as UTC. Compare with `datetime.utcnow()`
**Warning signs:** Users report accounts purged before 30 days in certain timezones

### Pitfall 5: Email Sent After Purge
**What goes wrong:** Confirmation email sent to purged user's email fails or is privacy violation
**Why it happens:** Sending confirmation after hard delete when email is gone
**How to avoid:** Send confirmation email BEFORE hard delete, during soft delete phase only
**Warning signs:** Email errors in purge job logs

## Code Examples

Verified patterns from official sources and existing codebase:

### Danger Zone UI Pattern
```html
<!-- Source: GitHub-style danger zone pattern -->
<div class="card danger-zone">
    <div class="card-header">
        <span class="card-title text-danger">Danger Zone</span>
    </div>
    <div class="danger-action">
        <div class="danger-info">
            <span class="danger-title">Delete Account</span>
            <span class="danger-desc text-muted">
                Once deleted, your account enters a 30-day recovery period.
                After 30 days, all data is permanently erased.
            </span>
        </div>
        <button type="button" class="btn btn-danger" onclick="showDeleteModal()">
            Delete Account
        </button>
    </div>
</div>
```

### Recovery Interstitial Page
```html
<!-- Source: CONTEXT.md decision -->
{% extends "base.html" %}
{% block title %}Account Recovery{% endblock %}
{% block content %}
<div class="recovery-prompt">
    <h1>Account Scheduled for Deletion</h1>
    <p>Your account is scheduled to be permanently deleted on
       <strong>{{ scheduled_purge_at.strftime('%B %d, %Y') }}</strong>.</p>

    <form action="/recover-account" method="post">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <input type="hidden" name="token" value="{{ token }}">

        <div class="recovery-actions">
            <button type="submit" name="action" value="recover" class="btn btn-success">
                Yes, Recover My Account
            </button>
            <button type="submit" name="action" value="continue_deletion" class="btn btn-secondary">
                No, Continue Deletion
            </button>
        </div>
    </form>
</div>
{% endblock %}
```

### Audit Log Table with Expandable Details
```html
<!-- Source: Admin UI patterns research -->
<table class="table audit-table">
    <thead>
        <tr>
            <th>Timestamp</th>
            <th>User</th>
            <th>Event</th>
            <th>IP</th>
            <th></th>
        </tr>
    </thead>
    <tbody>
        {% for log in logs %}
        <tr class="audit-row">
            <td>{{ log.timestamp }}</td>
            <td>
                {% if log.user_id is none and log.details and log.details.get('anonymized') %}
                    <span class="text-muted">[Deleted User]</span>
                {% elif log.display_name %}
                    {{ log.display_name }}
                {% else %}
                    <span class="text-muted">Anonymous</span>
                {% endif %}
            </td>
            <td><span class="badge">{{ log.event_type }}</span></td>
            <td>{{ log.ip_address or '-' }}</td>
            <td>
                {% if log.details %}
                <button class="btn btn-sm" onclick="toggleDetails({{ loop.index }})">
                    Details
                </button>
                {% endif %}
            </td>
        </tr>
        {% if log.details %}
        <tr id="details-{{ loop.index }}" class="details-row" style="display:none;">
            <td colspan="5">
                <pre class="json-details">{{ log.details | tojson(indent=2) }}</pre>
            </td>
        </tr>
        {% endif %}
        {% endfor %}
    </tbody>
</table>
```

### Filter Bar with Date Range
```html
<!-- Source: Audit log UI research -->
<form class="filter-bar" method="get" action="/admin/audit-log">
    <div class="filter-group">
        <label for="user_search">User</label>
        <input type="text" id="user_search" name="user"
               placeholder="Email or name" value="{{ filters.user or '' }}">
    </div>

    <div class="filter-group">
        <label for="event_type">Event Type</label>
        <select id="event_type" name="event_type">
            <option value="">All Events</option>
            {% for type in event_types %}
            <option value="{{ type }}" {% if filters.event_type == type %}selected{% endif %}>
                {{ type }}
            </option>
            {% endfor %}
        </select>
    </div>

    <div class="filter-group">
        <label for="start_date">From</label>
        <input type="date" id="start_date" name="start_date"
               value="{{ filters.start_date or '' }}">
    </div>

    <div class="filter-group">
        <label for="end_date">To</label>
        <input type="date" id="end_date" name="end_date"
               value="{{ filters.end_date or '' }}">
    </div>

    <div class="filter-group">
        <label for="ip">IP Address</label>
        <input type="text" id="ip" name="ip"
               placeholder="192.168..." value="{{ filters.ip or '' }}">
    </div>

    <button type="submit" class="btn btn-primary">Filter</button>
    <a href="/admin/audit-log" class="btn btn-secondary">Clear</a>
</form>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Boolean `is_deleted` flag | `deleted_at` timestamp | Widespread adoption 2020+ | Enables grace period, time-based queries |
| Hard delete user data | Anonymize + retain audit logs | GDPR 2018+ | Legal compliance, audit trail preserved |
| Manual cron jobs | APScheduler in-process | Already in project | No external cron dependency |

**Deprecated/outdated:**
- **Hard delete on request:** Privacy regulations require data portability and grace periods
- **Storing plaintext user_id in anonymized logs:** Use hash or NULL

## Open Questions

Things that couldn't be fully resolved:

1. **Admin visibility into pending deletions**
   - What we know: Admins can filter audit log for `account.delete_request` events per CONTEXT.md
   - What's unclear: Should there be a dedicated "Pending Deletions" view?
   - Recommendation: Use audit log filter initially, add dedicated view if needed later

2. **Email delivery after deletion**
   - What we know: Send confirmation email with recovery info at deletion time
   - What's unclear: What if email delivery fails during deletion flow?
   - Recommendation: Non-blocking email (log failure but complete deletion)

3. **Time zone for scheduled purge display**
   - What we know: Store as UTC internally
   - What's unclear: Display in user's timezone or server timezone?
   - Recommendation: Display in UTC with "(UTC)" suffix for clarity

## Sources

### Primary (HIGH confidence)
- Existing codebase: database.py, jobs.py, admin.py, routes.py - patterns verified
- APScheduler 3.x documentation - CronTrigger usage verified
- CONTEXT.md decisions - locked requirements for this phase

### Secondary (MEDIUM confidence)
- [APScheduler User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) - cron trigger patterns
- [Soft Delete Patterns (Medium)](https://theshubhendra.medium.com/mastering-soft-delete-advanced-sqlalchemy-techniques-4678f4738947) - timestamp vs boolean
- [GDPR Log Management (Last9)](https://last9.io/blog/gdpr-log-management/) - anonymization requirements
- [Audit Log UI Guide (Medium)](https://medium.com/@tony.infisical/guide-to-building-audit-logs-for-application-software-b0083bb58604) - filter patterns

### Tertiary (LOW confidence)
- [Date Range Picker no library](https://devncoffee.com/date-range-picker-in-html-javascript/) - native HTML approach verified adequate
- [Soft Deletion critique (brandur.org)](https://brandur.org/soft-deletion) - considered but timestamp approach chosen per requirements

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all components already in project
- Architecture: HIGH - extends existing patterns directly
- Pitfalls: HIGH - based on codebase analysis and common patterns
- Audit log UI: MEDIUM - standard patterns, specific styling TBD

**Research date:** 2026-02-08
**Valid until:** 2026-03-08 (30 days - stable patterns)
