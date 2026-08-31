"""A soft-deleted account must not receive notifications.

Deleting an account sets ``deleted_at`` and schedules a purge 30 days out. The
web side already honours that: login redirects to the recovery page and every
session is dropped. The scheduler did not, so a deleted account kept receiving
event emails for the whole grace period — and because login was blocked, its
owner had no way to reach the settings page and stop them.

Three independent paths could reach a send, so each is pinned separately:
the scheduler's rule set, the notifier itself, and the daily digest, which
does not go through the rule set at all.
"""

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from ra_tracker.database import Event, Rule
from ra_tracker.scheduler.jobs import send_daily_digest
from ra_tracker.services.notifier import notify_users_for_events

EVENT_ID = 2353135
PASSWORD = "correct-horse-battery-staple-9"


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


def add_user(db, email: str):
    user_id = db.create_user(email, PASSWORD, email.split("@")[0])
    db.set_email_verified(user_id)
    return user_id


def add_venue_rule(db, user_id: int, name: str = "Berghain", target_id: int = 1) -> int:
    return db.add_rule(
        Rule(id=None, rule_type="venue", target_id=target_id, target_name=name,
             notify_mode="all"),
        user_id=user_id,
    )


def soft_delete(db, user_id: int):
    db.soft_delete_user(user_id, datetime.utcnow() + timedelta(days=30))


@pytest.fixture
def live_user(db):
    return add_user(db, "live@example.test")


@pytest.fixture
def deleted_user(db):
    user_id = add_user(db, "deleted@example.test")
    soft_delete(db, user_id)
    return user_id


def dispatch(events_and_rules):
    """Run the dispatch wrapper with the email transport stubbed out."""
    with patch(
        "ra_tracker.services.notifier.is_email_configured", return_value=True
    ), patch(
        "ra_tracker.services.notifier.send_notification_email", return_value=True
    ) as send:
        results = notify_users_for_events(events_and_rules)
    return results, send


# --------------------------------------------------------------------------
# The scheduler's rule set
# --------------------------------------------------------------------------


def test_scheduler_skips_rules_owned_by_a_deleted_account(db, live_user, deleted_user):
    add_venue_rule(db, live_user, "Berghain", 1)
    add_venue_rule(db, deleted_user, "Tresor", 2)

    owners = {rule.user_id for rule in db.get_active_rules()}

    assert owners == {live_user}


def test_scheduler_keeps_legacy_rules_with_no_owner(db, deleted_user):
    """Rules predating multi-tenancy have user_id NULL and must survive."""
    add_venue_rule(db, None, "Tresor", 2)
    add_venue_rule(db, deleted_user, "Berghain", 1)

    rules = db.get_active_rules()

    assert [rule.target_name for rule in rules] == ["Tresor"]
    assert rules[0].user_id is None


def test_recovering_an_account_restores_its_rules(db, deleted_user):
    add_venue_rule(db, deleted_user, "Berghain", 1)
    assert db.get_active_rules() == []

    db.recover_user(deleted_user)

    assert [rule.user_id for rule in db.get_active_rules()] == [deleted_user]


def test_explicit_user_filter_still_returns_a_deleted_users_rules(db, deleted_user):
    """Asking for one user's rules by ID is a deliberate act; don't second-guess it.

    The settings and recovery screens need to show what the account owns.
    """
    add_venue_rule(db, deleted_user, "Berghain", 1)

    assert len(db.get_active_rules(user_id=deleted_user)) == 1


# --------------------------------------------------------------------------
# The notifier
# --------------------------------------------------------------------------


def test_no_email_is_sent_to_a_deleted_account(db, deleted_user):
    payload = [(make_event(), [make_rule(deleted_user)])]

    results, send = dispatch(payload)

    assert send.call_count == 0
    assert results[deleted_user] == {"telegram": False, "email": False, "attempted": False}


def test_no_telegram_is_sent_to_a_deleted_account(db, deleted_user):
    """Telegram bypasses the email config check, so it needs its own guard."""
    db.update_user_telegram(deleted_user, 12345)
    db.set_user_telegram_enabled(deleted_user, True)
    payload = [(make_event(), [make_rule(deleted_user)])]

    with patch(
        "ra_tracker.services.notifier.is_email_configured", return_value=True
    ), patch(
        "ra_tracker.services.notifier.Notifier.send_to_user_telegram_async"
    ) as telegram, patch(
        "ra_tracker.services.notifier.send_notification_email"
    ) as email:
        notify_users_for_events(payload)

    assert telegram.call_count == 0
    assert email.call_count == 0


def test_nothing_is_recorded_for_a_deleted_account(db, deleted_user):
    """Recording a send that never happened would poison recovery."""
    payload = [(make_event(), [make_rule(deleted_user)])]
    dispatch(payload)

    assert db.has_event_notification(EVENT_ID, user_id=deleted_user) is False


def test_a_recovered_account_receives_again(db, deleted_user):
    payload = [(make_event(), [make_rule(deleted_user)])]
    dispatch(payload)

    db.recover_user(deleted_user)
    _, send = dispatch(payload)

    assert send.call_count == 1
    assert db.has_event_notification(EVENT_ID, user_id=deleted_user) is True


def test_a_deleted_account_does_not_block_a_live_one(db, live_user, deleted_user):
    """Both users match the same event; only the live one hears about it."""
    event = make_event()
    payload = [(event, [make_rule(deleted_user), make_rule(live_user, rule_id=2)])]

    results, send = dispatch(payload)

    assert send.call_count == 1
    assert results[live_user]["email"] is True
    assert results[deleted_user]["attempted"] is False
    assert db.has_event_notification(EVENT_ID, user_id=live_user) is True
    assert db.has_event_notification(EVENT_ID, user_id=deleted_user) is False


# --------------------------------------------------------------------------
# The daily digest
#
# This path never consults the rule set — it reads its recipients straight out
# of the notifications queue — so excluding deleted owners upstream does not
# cover it.
# --------------------------------------------------------------------------


def queue_one_event(db, user_id: int):
    rule_id = add_venue_rule(db, user_id)
    db.upsert_event(make_event(), rule_id=rule_id)
    db.queue_event_for_digest(EVENT_ID, user_id)
    return rule_id


def run_digest():
    with patch(
        "ra_tracker.services.notifier.is_email_configured", return_value=True
    ), patch(
        "ra_tracker.services.notifier.send_notification_email", return_value=True
    ) as send:
        send_daily_digest()
    return send


def test_digest_is_not_sent_to_a_deleted_account(db):
    user_id = add_user(db, "deleted@example.test")
    queue_one_event(db, user_id)
    soft_delete(db, user_id)

    send = run_digest()

    assert send.call_count == 0


def test_digest_leaves_a_deleted_accounts_queue_intact(db):
    """Not drained: the rows go when the account is purged, and until then a
    recovery should still be able to deliver them."""
    user_id = add_user(db, "deleted@example.test")
    queue_one_event(db, user_id)
    soft_delete(db, user_id)

    run_digest()

    assert db.get_queued_digest_events(user_id) == [EVENT_ID]


def test_digest_still_reaches_a_live_account(db):
    user_id = add_user(db, "live@example.test")
    queue_one_event(db, user_id)

    send = run_digest()

    assert send.call_count == 1
    assert db.get_queued_digest_events(user_id) == []


def test_digest_skips_only_the_deleted_recipient(db):
    live_id = add_user(db, "live@example.test")
    deleted_id = add_user(db, "deleted@example.test")
    queue_one_event(db, live_id)
    queue_one_event(db, deleted_id)
    soft_delete(db, deleted_id)

    send = run_digest()

    assert send.call_count == 1
    assert db.get_queued_digest_events(live_id) == []
    assert db.get_queued_digest_events(deleted_id) == [EVENT_ID]
