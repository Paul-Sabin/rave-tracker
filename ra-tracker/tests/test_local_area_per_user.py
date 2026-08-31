"""Notifications must filter on each account's own local area.

Every account picks a local area in the welcome wizard, stored as
users.local_area_id, and the dashboard already filters on it. The notification
path read the single global config.user.local_area_id instead, so an account
outside that one area saw its own city on the dashboard while being notified
about a different one.

'local' is the default notify_mode, which made this silent rather than noisy:
affected users simply never heard about events near them.
"""

from datetime import date

import pytest

from ra_tracker.config import Config
from ra_tracker.database import Event, Rule
from ra_tracker.scheduler.jobs import (
    local_area_resolver,
    notification_horizon,
    should_notify_for_event,
)

BERLIN = 34
HAMBURG = 12
PASSWORD = "correct-horse-battery-staple-9"


def make_event(area_id: int, event_id: int = 1) -> Event:
    return Event(
        id=event_id,
        title="Klubnacht",
        date=date(2026, 9, 12),
        venue_id=1,
        venue_name="Somewhere",
        area_id=area_id,
        area_name="Somewhere",
    )


def make_rule(user_id, notify_mode: str = "local") -> Rule:
    return Rule(
        id=1,
        rule_type="venue",
        target_id=1,
        target_name="Somewhere",
        notify_mode=notify_mode,
        user_id=user_id,
    )


def config_with_global_area(area_id) -> Config:
    config = Config()
    config.user.local_area_id = area_id
    return config


def add_user(db, email: str, area_id):
    user_id = db.create_user(email, PASSWORD, email.split("@")[0])
    db.set_email_verified(user_id)
    db.update_user_local_area(user_id, area_id, "Somewhere")
    return user_id


# --------------------------------------------------------------------------
# Resolving the area
# --------------------------------------------------------------------------


def test_each_account_resolves_to_its_own_area(db):
    berliner = add_user(db, "berlin@example.test", BERLIN)
    hamburger = add_user(db, "hamburg@example.test", HAMBURG)
    resolve = local_area_resolver(db, config_with_global_area(BERLIN))

    assert resolve(berliner) == BERLIN
    assert resolve(hamburger) == HAMBURG


def test_a_rule_with_no_owner_falls_back_to_the_global_area(db):
    """Legacy rules predate per-user areas; keep their behaviour unchanged."""
    resolve = local_area_resolver(db, config_with_global_area(BERLIN))

    assert resolve(None) == BERLIN


def test_an_account_with_no_area_falls_back_to_the_global_area(db):
    user_id = add_user(db, "nowhere@example.test", None)
    resolve = local_area_resolver(db, config_with_global_area(BERLIN))

    assert resolve(user_id) == BERLIN


def test_an_unknown_account_falls_back_rather_than_raising(db):
    resolve = local_area_resolver(db, config_with_global_area(BERLIN))

    assert resolve(9999) == BERLIN


def test_each_account_is_looked_up_only_once(db):
    """Memoised: the resolver is called per event, not per account."""
    user_id = add_user(db, "berlin@example.test", BERLIN)
    resolve = local_area_resolver(db, config_with_global_area(BERLIN))

    calls = []
    original = db.get_user_by_id

    def counting(uid):
        calls.append(uid)
        return original(uid)

    db.get_user_by_id = counting
    try:
        for _ in range(5):
            resolve(user_id)
    finally:
        db.get_user_by_id = original

    assert calls == [user_id]


# --------------------------------------------------------------------------
# The filtering decision
# --------------------------------------------------------------------------


def test_a_hamburg_account_is_notified_about_hamburg(db):
    """The bug: this used to be filtered out against the global Berlin area."""
    hamburger = add_user(db, "hamburg@example.test", HAMBURG)
    resolve = local_area_resolver(db, config_with_global_area(BERLIN))
    rule = make_rule(hamburger)

    assert should_notify_for_event(make_event(HAMBURG), rule, resolve(rule.user_id)) is True


def test_a_hamburg_account_is_not_notified_about_berlin(db):
    """The other half: they used to receive Berlin events and nothing else."""
    hamburger = add_user(db, "hamburg@example.test", HAMBURG)
    resolve = local_area_resolver(db, config_with_global_area(BERLIN))
    rule = make_rule(hamburger)

    assert should_notify_for_event(make_event(BERLIN), rule, resolve(rule.user_id)) is False


def test_two_accounts_get_opposite_answers_for_one_event(db):
    """One event, one fetch cycle, two accounts, two different verdicts."""
    berliner = add_user(db, "berlin@example.test", BERLIN)
    hamburger = add_user(db, "hamburg@example.test", HAMBURG)
    resolve = local_area_resolver(db, config_with_global_area(BERLIN))
    event = make_event(HAMBURG)

    assert should_notify_for_event(event, make_rule(hamburger), resolve(hamburger)) is True
    assert should_notify_for_event(event, make_rule(berliner), resolve(berliner)) is False


@pytest.mark.parametrize("area_id", [BERLIN, HAMBURG])
def test_notify_mode_all_ignores_the_area(db, area_id):
    hamburger = add_user(db, "hamburg@example.test", HAMBURG)
    resolve = local_area_resolver(db, config_with_global_area(BERLIN))
    rule = make_rule(hamburger, notify_mode="all")

    assert should_notify_for_event(make_event(area_id), rule, resolve(rule.user_id)) is True


@pytest.mark.parametrize("area_id", [BERLIN, HAMBURG])
def test_notify_mode_none_ignores_the_area(db, area_id):
    hamburger = add_user(db, "hamburg@example.test", HAMBURG)
    resolve = local_area_resolver(db, config_with_global_area(BERLIN))
    rule = make_rule(hamburger, notify_mode="none")

    assert should_notify_for_event(make_event(area_id), rule, resolve(rule.user_id)) is False


def test_no_area_anywhere_means_no_local_notifications(db):
    """With nothing to compare against, 'local' cannot match. Unchanged."""
    user_id = add_user(db, "nowhere@example.test", None)
    resolve = local_area_resolver(db, config_with_global_area(None))
    rule = make_rule(user_id)

    assert should_notify_for_event(make_event(BERLIN), rule, resolve(rule.user_id)) is False


# --------------------------------------------------------------------------
# The notification horizon
#
# scheduler.event_horizon_days was defined, saved and shown in the admin UI but
# read by nothing, so the setting silently did nothing. It now bounds how far
# ahead an event can be dated and still trigger a notification.
# --------------------------------------------------------------------------


def config_with_horizon(days) -> Config:
    config = Config()
    config.scheduler.event_horizon_days = days
    return config


def test_the_horizon_is_the_configured_number_of_days_out():
    from datetime import timedelta

    horizon = notification_horizon(config_with_horizon(30))

    assert horizon == date.today() + timedelta(days=30)


@pytest.mark.parametrize("days", [0, -1, None])
def test_a_missing_or_nonsense_horizon_disables_the_limit(days):
    """Filtering everything out would silence every notification, which is a
    far worse failure than ignoring a mistyped value."""
    assert notification_horizon(config_with_horizon(days)) is None


# --------------------------------------------------------------------------
# Through the real fetch cycle
#
# The unit tests above check the two helpers in isolation. These drive
# fetch_and_notify itself, which is the only way to show that the filters are
# actually wired into the path that decides who gets an email.
# --------------------------------------------------------------------------


@pytest.fixture
def captured_dispatch(db):
    """Run fetch_and_notify with the network stubbed, capturing what it sends.

    Yields a dict whose "events" key is filled with the (event, rules) list
    handed to the notifier, so a test can assert on exactly what would go out.
    """
    from unittest.mock import patch

    captured = {"events": None}

    def fake_notify(new_events):
        captured["events"] = new_events
        return {}

    def run(events_by_rule):
        """events_by_rule: callable(rule) -> list[Event]."""
        with patch("ra_tracker.scheduler.jobs.Fetcher") as fetcher_cls, \
                patch("ra_tracker.scheduler.jobs.notify_users_for_events", fake_notify), \
                patch("ra_tracker.scheduler.jobs.scraper_alerter"):
            fetcher_cls.return_value.fetch_for_rule.side_effect = events_by_rule
            from ra_tracker.scheduler.jobs import fetch_and_notify
            fetch_and_notify()
        return captured["events"]

    captured["run"] = run
    yield captured


def notified_event_ids(dispatched):
    return sorted(event.id for event, _rules in (dispatched or []))


def test_an_event_beyond_the_horizon_is_not_notified(db, captured_dispatch):
    from datetime import timedelta

    user_id = add_user(db, "berlin@example.test", BERLIN)
    db.add_rule(
        Rule(id=None, rule_type="venue", target_id=1, target_name="Somewhere",
             notify_mode="all"),
        user_id=user_id,
    )
    db.set_app_settings({"scheduler.event_horizon_days": 30})

    near = make_event(BERLIN, event_id=101)
    near.date = date.today() + timedelta(days=10)
    far = make_event(BERLIN, event_id=102)
    far.date = date.today() + timedelta(days=90)

    dispatched = captured_dispatch["run"](lambda rule: [near, far])

    assert notified_event_ids(dispatched) == [101]


def test_both_events_are_notified_when_the_horizon_is_generous(db, captured_dispatch):
    from datetime import timedelta

    user_id = add_user(db, "berlin@example.test", BERLIN)
    db.add_rule(
        Rule(id=None, rule_type="venue", target_id=1, target_name="Somewhere",
             notify_mode="all"),
        user_id=user_id,
    )
    db.set_app_settings({"scheduler.event_horizon_days": 365})

    near = make_event(BERLIN, event_id=101)
    near.date = date.today() + timedelta(days=10)
    far = make_event(BERLIN, event_id=102)
    far.date = date.today() + timedelta(days=90)

    dispatched = captured_dispatch["run"](lambda rule: [near, far])

    assert notified_event_ids(dispatched) == [101, 102]


def test_the_fetch_cycle_filters_on_the_owners_own_area(db, captured_dispatch):
    """End to end: two accounts, two areas, one fetch, one event each."""
    from datetime import timedelta

    berliner = add_user(db, "berlin@example.test", BERLIN)
    hamburger = add_user(db, "hamburg@example.test", HAMBURG)
    for owner in (berliner, hamburger):
        db.add_rule(
            Rule(id=None, rule_type="venue", target_id=1, target_name="Somewhere",
                 notify_mode="local"),
            user_id=owner,
        )
    db.set_app_settings({"scheduler.event_horizon_days": 365})

    berlin_event = make_event(BERLIN, event_id=201)
    berlin_event.date = date.today() + timedelta(days=5)
    hamburg_event = make_event(HAMBURG, event_id=202)
    hamburg_event.date = date.today() + timedelta(days=5)

    dispatched = captured_dispatch["run"](lambda rule: [berlin_event, hamburg_event])

    # Both events go out, but each only to the account whose area it is in.
    by_event = {event.id: {r.user_id for r in rules} for event, rules in dispatched}
    assert by_event == {201: {berliner}, 202: {hamburger}}
