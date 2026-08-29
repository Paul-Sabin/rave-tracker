"""Shared fixtures for the Rave Tracker test suite.

The environment is locked down at import time, before any application module
is loaded. This matters: ``create_app()`` calls ``load_dotenv()`` while being
imported, and python-dotenv does not overwrite variables that are already set.
Pre-seeding ``os.environ`` here is therefore what guarantees a test run can
never reach the production database or send real Telegram/email traffic.
"""

import os
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# Force SQLite. An empty DATABASE_URL makes Database() take the SQLite branch
# and blocks a value in .env from pointing tests at production Postgres.
os.environ["DATABASE_URL"] = ""
os.environ["SECRET_KEY"] = "test-secret-key-not-a-real-secret"
os.environ["TELEGRAM_BOT_TOKEN"] = "test-bot-token"
os.environ["BREVO_SMTP_USERNAME"] = "test-smtp-user"
os.environ["BREVO_SMTP_PASSWORD"] = "test-smtp-password"
os.environ["SENTRY_DSN"] = ""
os.environ["ENVIRONMENT"] = "test"
os.environ["RA_TRACKER_CONFIG"] = str(_REPO / "config.yaml")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from ra_tracker.database import Database, set_db  # noqa: E402
from ra_tracker.web.app import create_app  # noqa: E402
from ra_tracker.web.auth import create_user_session  # noqa: E402

VERIFIED_EMAIL = "verified@example.test"
UNVERIFIED_EMAIL = "unverified@example.test"
PASSWORD = "correct-horse-battery-staple-9"


@pytest.fixture
def db(tmp_path):
    """A fresh SQLite database per test, registered as the global instance."""
    database = Database(db_path=str(tmp_path / "test.db"), db_url="")
    database.init_schema()
    set_db(database)
    yield database
    set_db(None)


@pytest.fixture
def pg_db():
    """A real PostgreSQL database, skipped unless TEST_DATABASE_URL is set.

    Production runs PostgreSQL while the rest of the suite runs SQLite, and the
    two disagree on things that matter here — exception classes for constraint
    violations, ON CONFLICT syntax, NULL handling in unique indexes. Point
    TEST_DATABASE_URL at a throwaway database to exercise the real thing:

        TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/ravetracker_test

    Every table is dropped before the schema is built, so never aim this at a
    database whose contents you want to keep.
    """
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; skipping PostgreSQL-backed test")

    database = Database(db_url=url)
    with database.get_connection() as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    database.init_schema()
    set_db(database)
    yield database
    set_db(None)


@pytest.fixture
def app(db):
    """The FastAPI app.

    Built per test so it always observes the current global database. The
    lifespan handler is never entered, which keeps the scheduler and the
    Telegram bot from starting.
    """
    return create_app()


@pytest.fixture
def client(app):
    """Unauthenticated client. Redirects are returned, not followed."""
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def verified_user(db):
    """A user with a verified email and onboarding not yet completed."""
    user_id = db.create_user(VERIFIED_EMAIL, PASSWORD, "Verified Tester")
    db.set_email_verified(user_id, True)
    return db.get_user_by_id(user_id)


@pytest.fixture
def unverified_user(db):
    """A user who has registered but not confirmed their email address."""
    user_id = db.create_user(UNVERIFIED_EMAIL, PASSWORD, "Unverified Tester")
    return db.get_user_by_id(user_id)


def _logged_in(app, user):
    token, _expires = create_user_session(user.id)
    test_client = TestClient(app, follow_redirects=False)
    test_client.cookies.set("session_token", token)
    return test_client


@pytest.fixture
def auth_client(app, verified_user):
    """Client carrying a session for the verified user."""
    return _logged_in(app, verified_user)


@pytest.fixture
def unverified_client(app, unverified_user):
    """Client carrying a session for the unverified user."""
    return _logged_in(app, unverified_user)
