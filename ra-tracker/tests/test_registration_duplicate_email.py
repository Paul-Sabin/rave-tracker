"""Registering an address that already exists must fail the same way on both backends.

The route caught sqlite3.IntegrityError to render "An account with this email
already exists". Production runs PostgreSQL, which raises psycopg2's unrelated
IntegrityError, so the catch never fired and the user got a 500 instead of the
message. The database layer now raises a backend-agnostic exception and the web
layer no longer knows which driver is underneath.
"""

import sqlite3
from unittest.mock import patch

import pytest

from ra_tracker.database import EmailAlreadyExistsError, _is_unique_violation

PASSWORD = "correct-horse-battery-staple-9"


class _FakePgIntegrityError(Exception):
    """Stands in for psycopg2.IntegrityError, which carries a pgcode."""

    def __init__(self, pgcode):
        super().__init__("duplicate key value violates unique constraint")
        self.pgcode = pgcode


# --------------------------------------------------------------------------
# Classifying the driver exception
# --------------------------------------------------------------------------


def test_a_sqlite_unique_violation_is_recognised():
    exc = sqlite3.IntegrityError("UNIQUE constraint failed: users.email")
    assert _is_unique_violation(exc) is True


def test_a_sqlite_not_null_violation_is_not_a_duplicate():
    """Other IntegrityErrors are real faults and must keep propagating."""
    exc = sqlite3.IntegrityError("NOT NULL constraint failed: users.email")
    assert _is_unique_violation(exc) is False


def test_an_unrelated_exception_is_not_a_duplicate():
    assert _is_unique_violation(ValueError("nope")) is False


def test_a_postgres_unique_violation_is_recognised():
    """23505 is unique_violation. This is the case the old code missed."""
    with patch("ra_tracker.database.psycopg2") as fake_psycopg2:
        fake_psycopg2.IntegrityError = _FakePgIntegrityError
        assert _is_unique_violation(_FakePgIntegrityError("23505")) is True


def test_a_postgres_foreign_key_violation_is_not_a_duplicate():
    with patch("ra_tracker.database.psycopg2") as fake_psycopg2:
        fake_psycopg2.IntegrityError = _FakePgIntegrityError
        assert _is_unique_violation(_FakePgIntegrityError("23503")) is False


# --------------------------------------------------------------------------
# The database layer
# --------------------------------------------------------------------------


def test_creating_a_duplicate_user_raises_the_shared_exception(db):
    db.create_user("taken@example.test", PASSWORD, "First")

    with pytest.raises(EmailAlreadyExistsError):
        db.create_user("taken@example.test", PASSWORD, "Second")


def test_the_shared_exception_is_not_a_sqlite_exception():
    """Callers must not be able to catch this by driver class and appear to work."""
    assert not issubclass(EmailAlreadyExistsError, sqlite3.Error)


def test_a_postgres_duplicate_also_raises_the_shared_exception(db):
    """The regression: on PostgreSQL the insert raises a class sqlite3 never does."""
    with patch("ra_tracker.database.psycopg2") as fake_psycopg2, patch.object(
        db, "_insert_user", side_effect=_FakePgIntegrityError("23505")
    ):
        fake_psycopg2.IntegrityError = _FakePgIntegrityError

        with pytest.raises(EmailAlreadyExistsError):
            db.create_user("taken@example.test", PASSWORD, "Second")


def test_an_unrelated_database_error_still_propagates(db):
    """Swallowing everything here would hide real faults as "email taken"."""
    with patch.object(db, "_insert_user", side_effect=RuntimeError("disk full")):
        with pytest.raises(RuntimeError):
            db.create_user("new@example.test", PASSWORD, "Someone")


def test_the_first_user_is_still_the_admin(db):
    """create_user was split in two; the first-user behaviour must survive."""
    first = db.create_user("first@example.test", PASSWORD, "First")
    second = db.create_user("second@example.test", PASSWORD, "Second")

    assert db.get_user_by_id(first).is_admin is True
    assert db.get_user_by_id(second).is_admin is False


def test_the_first_user_still_claims_legacy_rows(db):
    """Legacy rules and notifications with no owner go to the first account."""
    from ra_tracker.database import Rule

    db.add_rule(Rule(id=None, rule_type="venue", target_id=1, target_name="Berghain"))
    db.add_event_notification(2353135)

    user_id = db.create_user("first@example.test", PASSWORD, "First")

    assert [r.user_id for r in db.get_active_rules(user_id=user_id)] == [user_id]
    assert db.has_event_notification(2353135, user_id=user_id) is True


# --------------------------------------------------------------------------
# The route
# --------------------------------------------------------------------------


def register(client, email):
    """GET the form to seed the CSRF cookie, then POST it back."""
    client.get("/register")
    token = client.cookies.get("csrftoken")
    assert token, "CSRF middleware did not set a csrftoken cookie"
    return client.post("/register", data={
        "email": email,
        "password": PASSWORD,
        "display_name": "Someone",
        "consent": "on",
        "csrf_token": token,
    })


def test_registering_a_taken_email_shows_the_message(client, db):
    db.create_user("taken@example.test", PASSWORD, "First")

    with patch("ra_tracker.web.routes.send_verification_email", return_value=True):
        response = register(client, "taken@example.test")

    assert response.status_code == 200
    assert "An account with this email already exists" in response.text


def test_registering_a_taken_email_creates_no_second_account(client, db):
    db.create_user("taken@example.test", PASSWORD, "First")

    with patch("ra_tracker.web.routes.send_verification_email", return_value=True):
        register(client, "taken@example.test")

    emails = [u.email for u in db.get_all_users()]
    assert emails.count("taken@example.test") == 1


def test_a_postgres_duplicate_does_not_return_a_server_error(client, db):
    """What production actually did: an uncaught driver exception, so a 500."""
    with patch("ra_tracker.web.routes.send_verification_email", return_value=True), \
            patch.object(type(db), "create_user",
                         side_effect=EmailAlreadyExistsError("taken@example.test")):
        response = register(client, "taken@example.test")

    assert response.status_code == 200
    assert "An account with this email already exists" in response.text
