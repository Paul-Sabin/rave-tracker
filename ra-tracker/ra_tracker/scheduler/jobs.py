"""Scheduled jobs for RA Tracker."""

import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import get_config
from ..database import get_db, Event, Rule
from ..services.fetcher import Fetcher
from ..services.notifier import Notifier, notify_users_for_events
from ..web.audit import log_audit_event_direct

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
                        admin_msg = f"Rave Tracker: Notified {total_users} user(s) about {len(new_events_list)} event(s)"
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


def purge_expired_accounts():
    """Daily job: permanently delete accounts past 30-day grace period.

    This job runs daily at 3 AM to:
    1. Find all users with scheduled_purge_at <= now
    2. Anonymize their audit logs (set user_id=NULL, add anonymization metadata)
    3. Log the purge event
    4. Hard delete all user data
    """
    logger.info("Starting account purge job")

    db = get_db()
    now = datetime.utcnow()

    # Find accounts to purge
    expired_users = db.get_users_pending_purge(before=now)

    if not expired_users:
        logger.info("Purge complete. No accounts to purge.")
        return

    purged_count = 0
    for user in expired_users:
        try:
            # Anonymize audit logs first (before we lose user context)
            anonymized = db.anonymize_audit_logs_for_user(user.id)
            logger.info(f"Anonymized {anonymized} audit logs for user {user.id}")

            # Log the purge event BEFORE deleting (so we have user context)
            # Use email hash for correlation without storing PII
            email_hash = hashlib.sha256(user.email.encode()).hexdigest()[:8]
            log_audit_event_direct(
                event_type="account.purge",
                user_id=None,  # Will be anonymized anyway
                ip_address=None,  # Background job, no IP
                details={"purged_user_email_hash": email_hash},
                target_type="user",
                target_id=user.id,
            )

            # Delete all user data
            db.hard_delete_user(user.id)

            purged_count += 1
            logger.info(f"Purged user {user.id}")
        except Exception as e:
            logger.error(f"Failed to purge user {user.id}: {e}")

    logger.info(f"Purge complete. {purged_count}/{len(expired_users)} accounts deleted.")


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

    # Event fetch job - runs on configured interval
    scheduler.add_job(
        fetch_and_notify,
        trigger=IntervalTrigger(hours=fetch_interval),
        id="fetch_and_notify",
        name="Fetch events and send notifications",
        replace_existing=True,
    )
    logger.info(f"Scheduled fetch job to run every {fetch_interval} hours")

    # Account purge job - runs daily at 3 AM UTC
    scheduler.add_job(
        purge_expired_accounts,
        trigger=CronTrigger(hour=3, minute=0),
        id="purge_expired_accounts",
        name="Purge accounts past 30-day grace period",
        replace_existing=True,
    )
    logger.info("Scheduled purge job to run daily at 3:00 AM UTC")

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
