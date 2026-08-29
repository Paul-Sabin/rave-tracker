"""Tests for notification de-duplication.

These cover the path that decides whether an event gets sent again on the next
fetch. A gap here does not fail loudly — it re-sends the same event to a real
person every few hours until somebody notices, so the assertions below are
deliberately about the recorded state, not about return values alone.

Two failure modes drive most of this file:

* the de-duplication row was written only after a channel *reported* success,
  so a delivery whose success signal was lost was repeated forever;
* uniqueness ignored ``user_id``, so the table held one row per event across
  every account, and the duplicate-insert path was guarded by an
  ``except sqlite3.IntegrityError`` that PostgreSQL never raises.
"""

import sqlite3
from datetime import date
from unittest.mock import patch

import pytest

from ra_tracker.database import Database, Event, Rule
from ra_tracker.services.notifier import notify_users_for_events


EVENT_ID = 2353135


def make_event(event_id: int = EVENT_ID) -> Event:
    return Event(
        id=event_id,
        title="Klubnacht",
        date=date(2026, 9, 12),
        venue_id=1,
        venue_name="Berghain",
        area_id=34,
        area_name="Berlin",
        content_url=f"/events/{event_id}",
    )


def make_rule(user_id: int, rule_id: int = 1) -> Rule:
    return Rule(
        id=rule_id,
        rule_type="venue",
        target_id=1,
        target_name="Berghain",
        notify_mode="all",
        user_id=user_id,
    )


def count_rows(db: Database, event_id: int = EVENT_ID) -> int:
    with db.get_connection() as conn:
        cursor = conn.execute(
            f"SELECT COUNT(*) FROM notifications WHERE event_id = {db.ph}",
            (event_id,),
        )
        return cursor.fetchone()[0]


# --------------------------------------------------------------------------
# Storage layer
# --------------------------------------------------------------------------


def test_add_notification_is_idempotent(db):
    """A repeated write is absorbed, not raised, and leaves one row."""
    assert db.add_notification(EVENT_ID, rule_id=0, user_id=1) is True
    assert db.add_notification(EVENT_ID, rule_id=0, user_id=1) is False
    assert count_rows(db) == 1


def test_two_users_can_each_be_recorded_for_one_event(db):
    """Uniqueness is per user, so a second account is not locked out."""
    assert db.add_notification(EVENT_ID, rule_id=0, user_id=1) is True
    assert db.add_notification(EVENT_ID, rule_id=0, user_id=2) is True
    assert count_rows(db) == 2


def test_has_event_notification_is_scoped_to_the_user(db):
    db.add_notification(EVENT_ID, rule_id=0, user_id=1)

    assert db.has_event_notification(EVENT_ID, user_id=1) is True
    assert db.has_event_notification(EVENT_ID, user_id=2) is False


def test_legacy_row_without_a_user_covers_everyone(db):
    """Pre-multi-tenant rows must not be re-sent to whoever upgrades."""
    db.add_event_notification(EVENT_ID)

    assert db.has_event_notification(EVENT_ID, user_id=1) is True
    assert db.has_event_notification(EVENT_ID, user_id=2) is True


def test_two_legacy_rows_for_one_event_still_collide(db):
    """COALESCE in the unique index: NULLs would otherwise never conflict."""
    assert db.add_event_notification(EVENT_ID) is True
    assert db.add_event_notification(EVENT_ID) is False
    assert count_rows(db) == 1


def test_digest_queue_and_notification_write_do_not_collide(db):
    """The digest send re-writes a row the queue already created."""
    assert db.queue_event_for_digest(EVENT_ID, user_id=1) is True
    assert db.get_queued_digest_events(user_id=1) == [EVENT_ID]

    # The send path writes the same (event, rule_id=0, user) key. Before the
    # fix this raised on PostgreSQL and aborted the whole digest.
    db.add_notification(EVENT_ID, rule_id=0, user_id=1)

    assert db.mark_digest_sent([EVENT_ID], user_id=1) == 1
    assert db.get_queued_digest_events(user_id=1) == []


# --------------------------------------------------------------------------
# PostgreSQL semantics
#
# The suite runs on SQLite, which silently forgave the production bug: SQLite
# raised sqlite3.IntegrityError, which the old code caught, while psycopg2
# raises its own unrelated class, which escaped. These tests pin the behaviour
# that made the difference.
# --------------------------------------------------------------------------


class _FakePgIntegrityError(Exception):
    """Stands in for psycopg2.errors.UniqueViolation.

    Deliberately not a subclass of sqlite3.IntegrityError — that is the whole
    point of the test.
    """


class _FakePgCursor:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class _FakePgConnection:
    """Rejects any duplicate insert the SQL did not ask the database to absorb.

    Mirrors what PostgreSQL does: a plain INSERT that violates the unique index
    raises, and only ON CONFLICT DO NOTHING turns that into a no-op.
    """

    def __init__(self, existing_keys):
        self._existing = existing_keys
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append(query)
        key = tuple(params or ())
        if "INSERT INTO notifications" not in query:
            return _FakePgCursor(0)
        if key in self._existing:
            if "ON CONFLICT DO NOTHING" not in query:
                raise _FakePgIntegrityError(
                    "duplicate key value violates unique constraint"
                )
            return _FakePgCursor(0)
        self._existing.add(key)
        return _FakePgCursor(1)


@pytest.fixture
def fake_pg(db):
    """`db`, forced into its PostgreSQL code path over a fake connection."""
    from contextlib import contextmanager

    connection = _FakePgConnection(existing_keys=set())
    db._use_postgres = True

    @contextmanager
    def get_connection():
        yield connection

    with patch.object(db, "get_connection", get_connection):
        yield db, connection

    db._use_postgres = False


def test_duplicate_insert_does_not_raise_on_postgres(fake_pg):
    """The regression itself: psycopg2's error class is not sqlite3's."""
    database, connection = fake_pg

    assert database.add_notification(EVENT_ID, rule_id=0, user_id=1) is True
    # Would raise _FakePgIntegrityError if the SQL relied on Python catching it.
    assert database.add_notification(EVENT_ID, rule_id=0, user_id=1) is False

    assert all("ON CONFLICT DO NOTHING" in q for q in connection.queries)


def test_postgres_conflict_clause_is_untargeted(fake_pg):
    """An expression index cannot arbitrate a column-targeted ON CONFLICT."""
    database, connection = fake_pg
    database.add_notification(EVENT_ID, rule_id=0, user_id=1)

    insert = next(q for q in connection.queries if "INSERT INTO notifications" in q)
    assert "ON CONFLICT DO NOTHING" in insert
    assert "ON CONFLICT (" not in insert


@pytest.mark.parametrize(
    "definition, stale",
    [
        ("UNIQUE (event_id, rule_id)", True),
        ("unique  (event_id,  rule_id)", True),
        ("UNIQUE (event_id, rule_id, COALESCE(user_id, 0))", False),
        ("UNIQUE (user_id, event_id)", False),
    ],
)
def test_stale_constraint_is_recognised_by_its_definition(definition, stale):
    """Drives the PostgreSQL migration; the wrong verdict either leaves the
    old constraint in place or drops the new one."""
    assert Database._is_stale_notification_constraint(definition) is stale


def test_postgres_migration_drops_only_the_stale_constraint(pg_db):
    """Needs TEST_DATABASE_URL. Rebuilds the pre-fix shape and re-migrates."""
    with pg_db.get_connection() as conn:
        conn.execute(
            "ALTER TABLE notifications ADD CONSTRAINT notifications_event_id_rule_id_key "
            "UNIQUE (event_id, rule_id)"
        )

    pg_db.init_schema()

    with pg_db.get_connection() as conn:
        cursor = conn.execute(Database._STALE_NOTIFICATION_CONSTRAINTS_SQL)
        remaining = [
            name for name, definition in cursor.fetchall()
            if Database._is_stale_notification_constraint(definition)
        ]
    assert remaining == []

    # The behaviour the constraint used to block.
    assert pg_db.add_notification(EVENT_ID, rule_id=0, user_id=1) is True
    assert pg_db.add_notification(EVENT_ID, rule_id=0, user_id=2) is True


def test_postgres_dedup_against_a_real_database(pg_db):
    """Same guarantees, on real PostgreSQL. Needs TEST_DATABASE_URL."""
    assert pg_db.add_notification(EVENT_ID, rule_id=0, user_id=1) is True
    assert pg_db.add_notification(EVENT_ID, rule_id=0, user_id=1) is False
    assert pg_db.add_notification(EVENT_ID, rule_id=0, user_id=2) is True

    assert pg_db.has_event_notification(EVENT_ID, user_id=1) is True
    assert pg_db.has_event_notification(EVENT_ID, user_id=3) is False
    assert count_rows(pg_db) == 2

    assert pg_db.queue_event_for_digest(EVENT_ID, user_id=3) is True
    assert pg_db.add_notification(EVENT_ID, rule_id=0, user_id=3) is False


# --------------------------------------------------------------------------
# Migration of databases created before the fix
# --------------------------------------------------------------------------


def _legacy_notifications_table(path):
    """Build a notifications table carrying the old table-level UNIQUE."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            rule_id INTEGER NOT NULL,
            user_id INTEGER,
            sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            queued_for_digest BOOLEAN DEFAULT 0,
            UNIQUE(event_id, rule_id)
        );
        INSERT INTO notifications (event_id, rule_id, user_id) VALUES (111, 0, 1);
        INSERT INTO notifications (event_id, rule_id, user_id) VALUES (222, 0, NULL);
        """
    )
    conn.commit()
    conn.close()


def test_migration_replaces_the_old_constraint(tmp_path):
    path = tmp_path / "legacy.db"
    _legacy_notifications_table(path)

    database = Database(db_path=str(path), db_url="")
    database.init_schema()

    with database.get_connection() as conn:
        indexes = conn.execute("PRAGMA index_list('notifications')").fetchall()
    names = [row["name"] for row in indexes]

    assert not any(n.startswith("sqlite_autoindex_notifications") for n in names)
    assert "idx_notifications_event_rule_user" in names


def test_migration_preserves_existing_rows(tmp_path):
    path = tmp_path / "legacy.db"
    _legacy_notifications_table(path)

    database = Database(db_path=str(path), db_url="")
    database.init_schema()

    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT id, event_id, user_id FROM notifications ORDER BY id"
        ).fetchall()

    assert [(r["id"], r["event_id"], r["user_id"]) for r in rows] == [
        (1, 111, 1),
        (2, 222, None),
    ]


def test_migration_unblocks_the_second_user(tmp_path):
    """The behaviour the old constraint prevented."""
    path = tmp_path / "legacy.db"
    _legacy_notifications_table(path)

    database = Database(db_path=str(path), db_url="")
    database.init_schema()

    assert database.add_notification(111, rule_id=0, user_id=2) is True
    assert database.has_event_notification(111, user_id=2) is True


def test_migration_is_safe_to_run_twice(tmp_path):
    path = tmp_path / "legacy.db"
    _legacy_notifications_table(path)

    database = Database(db_path=str(path), db_url="")
    database.init_schema()
    database.init_schema()

    assert count_rows(database, event_id=111) == 1


# --------------------------------------------------------------------------
# Dispatch: what gets recorded, and when
# --------------------------------------------------------------------------


@pytest.fixture
def email_user(db):
    """A verified user with email notifications on and Telegram off."""
    user_id = db.create_user("raver@example.test", "correct-horse-battery-9", "Raver")
    db.set_email_verified(user_id)
    return db.get_user_by_id(user_id)


def dispatch(events_and_rules, *, email_result, email_configured=True):
    """Run the sync dispatch wrapper with the email transport stubbed."""
    with patch(
        "ra_tracker.services.notifier.is_email_configured",
        return_value=email_configured,
    ), patch(
        "ra_tracker.services.notifier.send_notification_email",
    ) as send:
        if isinstance(email_result, Exception):
            send.side_effect = email_result
        else:
            send.return_value = email_result
        results = notify_users_for_events(events_and_rules)
    return results, send


def test_successful_send_is_recorded(db, email_user):
    payload = [(make_event(), [make_rule(email_user.id)])]

    results, send = dispatch(payload, email_result=True)

    assert send.call_count == 1
    assert results[email_user.id]["email"] is True
    assert db.has_event_notification(EVENT_ID, user_id=email_user.id) is True


def test_send_reported_as_failed_is_still_recorded(db, email_user):
    """The resend loop.

    Brevo can accept a message and still lose the HTTP response, so a False
    here does not mean the user's inbox is empty. Recording the attempt caps
    the damage at one lost notification instead of one per fetch, forever.
    """
    payload = [(make_event(), [make_rule(email_user.id)])]

    results, _ = dispatch(payload, email_result=False)

    assert results[email_user.id]["email"] is False
    assert results[email_user.id]["attempted"] is True
    assert db.has_event_notification(EVENT_ID, user_id=email_user.id) is True


def test_send_raising_is_still_recorded(db, email_user):
    payload = [(make_event(), [make_rule(email_user.id)])]

    results, _ = dispatch(payload, email_result=RuntimeError("connection reset"))

    assert results[email_user.id]["email"] is False
    assert db.has_event_notification(EVENT_ID, user_id=email_user.id) is True


def test_a_second_fetch_does_not_resend(db, email_user):
    """End to end: the same event, two consecutive fetches, one send."""
    payload = [(make_event(), [make_rule(email_user.id)])]

    _, first = dispatch(payload, email_result=False)
    assert first.call_count == 1

    # The scheduler's gate is what stops the second round.
    still_new = [
        (event, rules)
        for event, rules in payload
        if not db.has_event_notification(event.id, email_user.id)
    ]
    assert still_new == []


def test_nothing_is_recorded_when_no_channel_is_enabled(db, email_user):
    """Nothing was tried, so the event must stay pending, not be swallowed."""
    db.set_user_email_enabled(email_user.id, False)
    payload = [(make_event(), [make_rule(email_user.id)])]

    results, send = dispatch(payload, email_result=True)

    assert send.call_count == 0
    assert results[email_user.id]["attempted"] is False
    assert db.has_event_notification(EVENT_ID, user_id=email_user.id) is False


def test_nothing_is_recorded_when_email_is_unconfigured(db, email_user):
    payload = [(make_event(), [make_rule(email_user.id)])]

    results, send = dispatch(payload, email_result=True, email_configured=False)

    assert send.call_count == 0
    assert results[email_user.id]["attempted"] is False
    assert db.has_event_notification(EVENT_ID, user_id=email_user.id) is False


def test_one_users_failure_does_not_strand_the_next(db, email_user):
    """A raise mid-loop used to skip every user after it."""
    other_id = db.create_user("second@example.test", "correct-horse-battery-9", "Second")
    db.set_email_verified(other_id)

    event = make_event()
    payload = [(event, [make_rule(email_user.id), make_rule(other_id, rule_id=2)])]

    first_user_id = None

    async def flaky(user_email, user_id, events):
        nonlocal first_user_id
        if first_user_id is None:
            first_user_id = user_id
            raise RuntimeError("transport exploded")
        return True

    with patch(
        "ra_tracker.services.notifier.is_email_configured", return_value=True
    ), patch(
        "ra_tracker.services.notifier.send_notification_email", side_effect=flaky
    ):
        results = notify_users_for_events(payload)

    second_user_id = next(uid for uid in (email_user.id, other_id) if uid != first_user_id)

    assert results[second_user_id]["email"] is True
    # Both are recorded: the first attempted and failed, the second succeeded.
    assert db.has_event_notification(EVENT_ID, user_id=first_user_id) is True
    assert db.has_event_notification(EVENT_ID, user_id=second_user_id) is True


def test_each_user_is_recorded_independently(db, email_user):
    """One user being notified must not suppress the event for another."""
    other_id = db.create_user("second@example.test", "correct-horse-battery-9", "Second")
    db.set_email_verified(other_id)

    payload = [(make_event(), [make_rule(email_user.id)])]
    dispatch(payload, email_result=True)

    assert db.has_event_notification(EVENT_ID, user_id=email_user.id) is True
    assert db.has_event_notification(EVENT_ID, user_id=other_id) is False
