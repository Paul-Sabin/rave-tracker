"""Scheduled jobs for RA Tracker."""

import logging
from datetime import datetime
from typing import Optional, List, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import get_config
from ..database import get_db, Event, Rule
from ..services.fetcher import Fetcher
from ..services.notifier import Notifier, notify_users_for_events

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None
_last_fetch_time: Optional[datetime] = None


def should_notify_for_event(event: Event, rule: Rule, local_area_id: Optional[int]) -> bool:
    """Check if an event should trigger a notification based on rule's notify_mode.

    Args:
        event: The event to check
        rule: The rule that matched the event
        local_area_id: User's configured local area ID

    Returns:
        True if notification should be sent
    """
    mode = rule.notify_mode or 'local'

    if mode == 'none':
        return False
    elif mode == 'local':
        # Only notify for events in user's local area
        return local_area_id is not None and event.area_id == local_area_id
    else:  # mode == 'all'
        return True


def fetch_and_notify():
    """Main scheduled job: fetch events for all rules and send notifications."""
    global _last_fetch_time

    logger.info("Starting fetch and notify job")

    try:
        db = get_db()
        config = get_config()
        fetcher = Fetcher()
        local_area_id = config.user.local_area_id

        rules = db.get_active_rules()
        if not rules:
            logger.info("No active rules configured")
            db.clear_all_events()
            _last_fetch_time = datetime.now()
            return

        # Clear all events and rebuild from active rules
        db.clear_all_events()
        logger.info("Cleared events cache, fetching fresh data")

        # Phase 1: Fetch all events and track new ones per-event (not per-rule)
        total_events = 0
        new_events_map: Dict[int, Event] = {}  # event_id -> Event (deduplicated)
        event_rules: Dict[int, List[Rule]] = {}  # event_id -> list of matching rules

        for rule in rules:
            try:
                events = fetcher.fetch_for_rule(rule)
                total_events += len(events)
                logger.info(f"Fetched {len(events)} events for {rule.rule_type} '{rule.target_name}'")

                # Check each event for notification eligibility
                for event in events:
                    # Skip if already notified (per-event deduplication)
                    if db.has_event_notification(event.id):
                        continue

                    # Check if this rule's notify_mode allows notification
                    if should_notify_for_event(event, rule, local_area_id):
                        new_events_map[event.id] = event
                        if event.id not in event_rules:
                            event_rules[event.id] = []
                        event_rules[event.id].append(rule)

            except Exception as e:
                logger.error(f"Error fetching for rule {rule.target_name}: {e}")

        logger.info(f"Fetch complete. {total_events} events from {len(rules)} rules.")
        _last_fetch_time = datetime.now()

        # Phase 2: Send per-user notifications
        # Each event only appears once regardless of how many rules matched
        if new_events_map:
            new_events_list = [(event, event_rules[event.id]) for event in new_events_map.values()]
            logger.info(f"Found {len(new_events_list)} new events to notify")

            try:
                results = notify_users_for_events(new_events_list)

                # Log summary
                total_users = len(results)
                telegram_success = sum(1 for r in results.values() if r.get("telegram"))
                email_success = sum(1 for r in results.values() if r.get("email"))

                logger.info(
                    f"Notified {total_users} user(s): "
                    f"Telegram {telegram_success}/{total_users}, "
                    f"Email {email_success}/{total_users}"
                )

                # Optional: Admin summary to global chat_id (legacy behavior)
                if results and config.telegram.chat_id:
                    try:
                        notifier = Notifier()
                        admin_msg = f"RA Tracker: Notified {total_users} user(s) about {len(new_events_list)} event(s)"
                        from ..services.notifier import _run_async
                        _run_async(notifier.bot.send_message(
                            chat_id=config.telegram.chat_id,
                            text=admin_msg
                        ))
                    except Exception as e:
                        logger.debug(f"Admin notification failed (non-critical): {e}")
            except Exception as e:
                logger.warning(f"Failed to send notifications (non-blocking): {e}")

    except Exception as e:
        logger.error(f"Error in fetch_and_notify: {e}", exc_info=True)


def get_scheduler() -> BackgroundScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def start_scheduler():
    """Start the scheduler with configured jobs."""
    config = get_config()
    scheduler = get_scheduler()

    fetch_interval = config.scheduler.fetch_interval_hours

    scheduler.add_job(
        fetch_and_notify,
        trigger=IntervalTrigger(hours=fetch_interval),
        id="fetch_and_notify",
        name="Fetch events and send notifications",
        replace_existing=True,
    )

    logger.info(f"Scheduled fetch job to run every {fetch_interval} hours")

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")


def run_fetch_now():
    """Manually trigger a fetch."""
    logger.info("Manual fetch triggered")
    fetch_and_notify()


def get_last_fetch_time() -> Optional[datetime]:
    """Get the timestamp of the last fetch."""
    return _last_fetch_time


def get_next_fetch_time() -> Optional[datetime]:
    """Get the scheduled time of the next fetch."""
    scheduler = get_scheduler()
    job = scheduler.get_job("fetch_and_notify")
    if job and job.next_run_time:
        return job.next_run_time
    return None


def get_scheduler_status() -> dict:
    """Get scheduler status information."""
    scheduler = get_scheduler()

    return {
        "running": scheduler.running,
        "last_fetch": _last_fetch_time.isoformat() if _last_fetch_time else None,
        "next_fetch": get_next_fetch_time().isoformat() if get_next_fetch_time() else None,
    }
