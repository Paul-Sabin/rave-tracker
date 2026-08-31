"""Admin settings must reach the scheduler.

The web app and the scheduler run as two separate containers on Railway. They
share a database and nothing else — not a filesystem. Admin settings used to be
written to config.yaml, which meant the scheduler never saw a change and the
web container lost it on the next redeploy. Settings now live in the database.

The tests that matter most are the ones that never touch a shared object: they
save through one Config and read through a second, freshly loaded one, which is
the only honest way to model two processes inside one test run.
"""

import os
from unittest.mock import patch

import pytest

from ra_tracker.config import Config, get_config, set_config
from ra_tracker.database import Database
from ra_tracker.scheduler import jobs


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


def test_settings_round_trip_with_their_types(db):
    """Values are JSON, so a list stays a list and an int stays an int."""
    db.set_app_settings({
        "scheduler.fetch_times": ["08:00", "20:00"],
        "scheduler.event_horizon_days": 45,
        "scheduler.notification_mode": "daily_digest",
    })

    stored = db.get_app_settings()

    assert stored["scheduler.fetch_times"] == ["08:00", "20:00"]
    assert stored["scheduler.event_horizon_days"] == 45
    assert stored["scheduler.notification_mode"] == "daily_digest"


def test_saving_the_same_key_twice_overwrites(db):
    db.set_app_settings({"scheduler.digest_time": "08:00"})
    db.set_app_settings({"scheduler.digest_time": "21:30"})

    assert db.get_app_settings()["scheduler.digest_time"] == "21:30"


def test_no_settings_yet_reads_as_empty(db):
    assert db.get_app_settings() == {}


def test_an_unreadable_row_is_skipped_not_raised(db):
    """One corrupt row must not stop the scheduler from starting."""
    db.set_app_settings({"scheduler.digest_time": "09:00"})
    with db.get_connection() as conn:
        conn.execute(
            f"INSERT INTO app_settings (setting_key, setting_value) VALUES ({db.ph}, {db.ph})",
            ("scheduler.fetch_times", "{not json"),
        )

    stored = db.get_app_settings()

    assert stored == {"scheduler.digest_time": "09:00"}


# --------------------------------------------------------------------------
# The overlay
# --------------------------------------------------------------------------


@pytest.fixture
def restore_global_config():
    """Undo set_config() so a test cannot leak settings into the next one."""
    original = get_config()
    yield
    set_config(original)


def test_stored_settings_beat_the_config_file(db):
    config = Config()
    config.scheduler.fetch_times = ["03:00"]
    config.scheduler.notification_mode = "upon_fetch"
    db.set_app_settings({
        "scheduler.fetch_times": ["08:00", "20:00"],
        "scheduler.notification_mode": "daily_digest",
    })

    config.apply_db_overrides(db)

    assert config.scheduler.fetch_times == ["08:00", "20:00"]
    assert config.scheduler.notification_mode == "daily_digest"


def test_the_env_var_still_beats_stored_settings(db):
    """Documented precedence is env > database > file.

    Goes through load() rather than calling the overlay alone, because the two
    halves of the rule live in different places: load() applies the env var,
    and the overlay declines to undo it.
    """
    db.set_app_settings({"telegram.chat_id": "111"})

    with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "999"}):
        config = Config.load().apply_db_overrides(db)

    assert config.telegram.chat_id == "999"


def test_stored_chat_id_applies_when_no_env_var_is_set(db):
    db.set_app_settings({"telegram.chat_id": "111"})
    config = Config()

    with patch.dict(os.environ):
        os.environ.pop("TELEGRAM_CHAT_ID", None)
        config.apply_db_overrides(db)

    assert config.telegram.chat_id == "111"


def test_a_nonsense_notification_mode_is_ignored(db):
    db.set_app_settings({"scheduler.notification_mode": "whenever_i_feel_like_it"})
    config = Config()

    config.apply_db_overrides(db)

    assert config.scheduler.notification_mode == "upon_fetch"


def test_a_nonsense_fetch_times_value_is_ignored(db):
    db.set_app_settings({"scheduler.fetch_times": "08:00"})  # string, not a list
    config = Config()
    config.scheduler.fetch_times = ["03:00"]

    config.apply_db_overrides(db)

    assert config.scheduler.fetch_times == ["03:00"]


def test_an_empty_store_leaves_the_config_alone(db):
    config = Config()
    config.scheduler.fetch_times = ["03:00"]

    config.apply_db_overrides(db)

    assert config.scheduler.fetch_times == ["03:00"]


def test_a_broken_database_does_not_stop_startup():
    """Settings are a convenience; failing to read them must not be fatal."""
    class Exploding:
        def get_app_settings(self):
            raise RuntimeError("connection refused")

    config = Config()
    config.scheduler.fetch_times = ["03:00"]

    config.apply_db_overrides(Exploding())

    assert config.scheduler.fetch_times == ["03:00"]


def test_apply_returns_self_so_it_can_be_chained(db):
    config = Config()
    assert config.apply_db_overrides(db) is config


# --------------------------------------------------------------------------
# Crossing the process boundary
#
# The bug was not "the value is wrong" but "the other container never sees it".
# These save through one Config object and read through a different one built
# from scratch, which is as close as a single test run gets to two processes.
# --------------------------------------------------------------------------


def test_a_second_process_sees_settings_saved_by_the_first(tmp_path):
    shared_db_path = str(tmp_path / "shared.db")

    web_db = Database(db_path=shared_db_path, db_url="")
    web_db.init_schema()
    web_config = Config()
    web_config.scheduler.fetch_times = ["06:00", "18:00"]
    web_config.scheduler.notification_mode = "daily_digest"
    web_config.scheduler.digest_time = "07:15"
    web_db.set_app_settings(web_config.db_managed_settings())

    # A different process: its own Database handle, its own Config, and a
    # config file that knows nothing about any of this.
    scheduler_db = Database(db_path=shared_db_path, db_url="")
    scheduler_config = Config().apply_db_overrides(scheduler_db)

    assert scheduler_config.scheduler.fetch_times == ["06:00", "18:00"]
    assert scheduler_config.scheduler.notification_mode == "daily_digest"
    assert scheduler_config.scheduler.digest_time == "07:15"


def test_secrets_are_not_copied_into_the_database():
    """The bot token, secret key and SMTP password stay in the environment."""
    config = Config()
    config.telegram.bot_token = "secret-bot-token"
    config.app.secret_key = "secret-key"
    config.email.password = "smtp-password"
    config.email.api_key = "brevo-key"

    persisted = repr(config.db_managed_settings())

    for secret in ("secret-bot-token", "secret-key", "smtp-password", "brevo-key"):
        assert secret not in persisted


# --------------------------------------------------------------------------
# The scheduler
# --------------------------------------------------------------------------


@pytest.fixture
def clean_scheduler(db, restore_global_config):
    """A fresh scheduler with no leftover jobs or state.

    Started paused, which matters: while a scheduler is unstarted, add_job only
    appends to a pending list and replace_existing does nothing, so repeated
    installs would pile up duplicate ids instead of replacing each other.
    Paused gives a live jobstore without any trigger ever firing — the fetch
    jobs must never actually run and hit the RA API from a test.
    """
    jobs._scheduler = None
    jobs._schedule_state = None
    scheduler = jobs.get_scheduler()
    scheduler.start(paused=True)
    yield scheduler
    scheduler.shutdown(wait=False)
    jobs._scheduler = None
    jobs._schedule_state = None


def fetch_job_times(scheduler):
    """The hour:minute each per-time fetch job is set to fire at."""
    times = []
    for job in scheduler.get_jobs():
        if job.id.startswith("fetch_and_notify_"):
            fields = {f.name: str(f) for f in job.trigger.fields}
            times.append(f"{int(fields['hour']):02d}:{int(fields['minute']):02d}")
    return sorted(times)


def test_effective_config_publishes_to_the_global(db, restore_global_config):
    """Fetcher, Notifier and the email sender all read the cached global.

    Reloading into a local variable, which is what the job used to do, left
    every one of them on the values from process start.
    """
    db.set_app_settings({"scheduler.notification_mode": "daily_digest"})

    jobs.effective_config()

    assert get_config().scheduler.notification_mode == "daily_digest"


def test_reconcile_installs_the_stored_schedule(db, clean_scheduler):
    db.set_app_settings({"scheduler.fetch_times": ["08:00", "20:00"]})

    assert jobs.reconcile_schedule() is True
    assert fetch_job_times(clean_scheduler) == ["08:00", "20:00"]


def test_reconcile_does_nothing_when_the_schedule_is_unchanged(db, clean_scheduler):
    db.set_app_settings({"scheduler.fetch_times": ["08:00"]})
    assert jobs.reconcile_schedule() is True

    assert jobs.reconcile_schedule() is False


def test_reconcile_picks_up_a_changed_fetch_time(db, clean_scheduler):
    db.set_app_settings({"scheduler.fetch_times": ["08:00"]})
    jobs.reconcile_schedule()

    db.set_app_settings({"scheduler.fetch_times": ["09:30"]})

    assert jobs.reconcile_schedule() is True
    assert fetch_job_times(clean_scheduler) == ["09:30"]


def test_removing_a_fetch_time_removes_its_job(db, clean_scheduler):
    """replace_existing only overwrites; a shrinking list leaves orphans behind,
    so removing a fetch time would never stop that fetch."""
    db.set_app_settings({"scheduler.fetch_times": ["08:00", "14:00", "20:00"]})
    jobs.reconcile_schedule()
    assert len(fetch_job_times(clean_scheduler)) == 3

    db.set_app_settings({"scheduler.fetch_times": ["08:00"]})
    jobs.reconcile_schedule()

    assert fetch_job_times(clean_scheduler) == ["08:00"]


def test_reconcile_picks_up_a_changed_digest_time(db, clean_scheduler):
    db.set_app_settings({"scheduler.digest_time": "08:00"})
    jobs.reconcile_schedule()

    db.set_app_settings({"scheduler.digest_time": "21:45"})
    assert jobs.reconcile_schedule() is True

    job = clean_scheduler.get_job("send_daily_digest")
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert (int(fields["hour"]), int(fields["minute"])) == (21, 45)


def test_start_scheduler_registers_the_reconcile_job(db, clean_scheduler):
    """Without this job the stored settings only apply on the next redeploy."""
    with patch.object(jobs, "_scheduler", clean_scheduler):
        jobs.start_scheduler()

    assert clean_scheduler.get_job("reconcile_schedule") is not None


# --------------------------------------------------------------------------
# The admin route
# --------------------------------------------------------------------------


@pytest.fixture
def admin_client(app, db):
    """A client logged in as an admin. The first user created becomes admin."""
    from fastapi.testclient import TestClient
    from ra_tracker.web.auth import create_user_session

    user_id = db.create_user("admin@example.test", "correct-horse-battery-9", "Admin")
    db.set_email_verified(user_id)
    assert db.get_user_by_id(user_id).is_admin, "first user should be admin"

    token, _ = create_user_session(user_id)
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("session_token", token)
    return client


def save_settings(client, **overrides):
    """GET the form to seed the CSRF cookie, then POST it back."""
    client.get("/admin/settings")
    token = client.cookies.get("csrftoken")
    assert token, "CSRF middleware did not set a csrftoken cookie"
    data = {
        "bot_token": "",
        "chat_id": "",
        "fetch_times_str": "08:00, 20:00",
        "event_horizon_days": 30,
        "notification_mode": "upon_fetch",
        "digest_time": "08:00",
        "csrf_token": token,
    }
    data.update(overrides)
    return client.post("/admin/settings/save", data=data)


def test_saving_the_form_persists_to_the_database(db, admin_client, restore_global_config):
    response = save_settings(
        admin_client,
        fetch_times_str="09:00, 21:00",
        notification_mode="daily_digest",
        digest_time="07:30",
    )
    assert response.status_code == 303

    stored = db.get_app_settings()
    assert stored["scheduler.fetch_times"] == ["09:00", "21:00"]
    assert stored["scheduler.notification_mode"] == "daily_digest"
    assert stored["scheduler.digest_time"] == "07:30"


def test_a_saved_setting_reaches_a_separate_scheduler_config(db, admin_client, restore_global_config):
    """The end-to-end claim: what the admin saves, the scheduler process reads."""
    save_settings(admin_client, fetch_times_str="05:45", notification_mode="daily_digest")

    scheduler_config = Config().apply_db_overrides(db)

    assert scheduler_config.scheduler.fetch_times == ["05:45"]
    assert scheduler_config.scheduler.notification_mode == "daily_digest"


def test_saving_does_not_write_a_config_file(db, admin_client, tmp_path, restore_global_config):
    """A file written here is invisible to the scheduler and lost on redeploy."""
    target = tmp_path / "config.yaml"
    with patch.object(Config, "save", side_effect=AssertionError("wrote config.yaml")):
        response = save_settings(admin_client)

    assert response.status_code == 303
    assert not target.exists()


def test_malformed_fetch_times_are_discarded(db, admin_client, restore_global_config):
    save_settings(admin_client, fetch_times_str="08:00, nonsense, 20:00, 7:5")

    assert db.get_app_settings()["scheduler.fetch_times"] == ["08:00", "20:00"]


def test_the_bot_token_is_never_persisted(db, admin_client, restore_global_config):
    save_settings(admin_client, bot_token="brand-new-token")

    assert "brand-new-token" not in repr(db.get_app_settings())
