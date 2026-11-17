"""A production deployment must never fall back to SQLite silently.

Regression tests for an outage where DATABASE_URL resolved to an empty string
on the hosting platform: both services started on an empty SQLite file and
/health answered "healthy, connected", so nothing looked wrong.
"""

import pytest

from ra_tracker.config import Config
from ra_tracker.database import Database, DatabaseNotConfiguredError

RAILWAY_MARKERS = ("RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID")


@pytest.fixture
def off_platform(monkeypatch):
    """No Railway markers, whatever the machine running the tests has set."""
    for marker in RAILWAY_MARKERS:
        monkeypatch.delenv(marker, raising=False)


def test_sqlite_is_allowed_outside_production(tmp_path, off_platform):
    database = Database(db_path=str(tmp_path / "dev.db"), db_url="")

    assert database.backend == "sqlite"
    assert database.describe().startswith("SQLite at ")


def test_refuses_sqlite_when_environment_is_production(tmp_path, monkeypatch, off_platform):
    monkeypatch.setenv("ENVIRONMENT", "Production")

    with pytest.raises(DatabaseNotConfiguredError, match="DATABASE_URL is empty"):
        Database(db_path=str(tmp_path / "prod.db"), db_url="")

    assert not (tmp_path / "prod.db").exists()


@pytest.mark.parametrize("marker", RAILWAY_MARKERS)
def test_refuses_sqlite_on_railway_even_without_environment(tmp_path, monkeypatch, off_platform, marker):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv(marker, "production")

    with pytest.raises(DatabaseNotConfiguredError, match=marker):
        Database(db_path=str(tmp_path / "prod.db"), db_url="")


def test_whitespace_database_url_counts_as_unset(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "   ")

    assert not Config.load().database.url


def test_database_url_is_stripped(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", " postgres://u:p@db.example.test:5432/app\n")

    assert Config.load().database.url == "postgresql://u:p@db.example.test:5432/app"


def test_health_reports_the_backend(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected", "backend": "sqlite"}


def test_health_is_unhealthy_when_database_is_not_configured(client, monkeypatch):
    from ra_tracker import database as database_module

    monkeypatch.setattr(database_module, "_db", None)
    monkeypatch.setenv("ENVIRONMENT", "production")

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert "DATABASE_URL is empty" in response.json()["error"]
