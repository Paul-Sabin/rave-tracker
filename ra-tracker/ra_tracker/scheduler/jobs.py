"""Scheduled jobs for RA Tracker."""

import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import get_config, Config
from ..database import get_db, Event, Rule
from ..services.fetcher import Fetcher
from ..services.notifier import Notifier, notify_users_for_events
from ..services.scraper_alerter import scraper_alerter
from ..web.audit import log_audit_event_direct
from ..api.circuit_breaker import circuit_breaker

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

    # Check circuit breaker before proceeding
    if not circuit_breaker.should_allow_fetch():
        status = circuit_breaker.get_status()
        cooldown_remaining = status.cooldown_remaining or 0
        logger.warning(f"Scheduled fetch skipped: circuit breaker OPEN (cooldown remaining: {cooldown_remaining}s)")
        # Log the skipped cycle to the fetch log
        try:
            db = get_db()
            fetch_id = db.start_scraper_fetch()
            db.complete_scraper_fetch(
                fetch_id=fetch_id,
                events_found=0,
                rules_processed=0,
                status='SKIPPED',
                error_message='Circuit breaker OPEN',
                circuit_breaker_state=circuit_breaker.state
            )
        except Exception as log_err:
            logger.debug(f"Could not log skipped fetch cycle: {log_err}")
        # Still track the skip for alerting
        try:
            scraper_alerter.check_and_alert('SKIPPED')
        except Exception as e:
            logger.error(f"Alert check failed: {e}")
        return

    fetch_id = None
    try:
        db = get_db()
        fetch_id = db.start_scraper_fetch()

        config = Config.load()  # Reload from disk to pick up changes saved via admin settings
        fetcher = Fetcher()
        local_area_id = config.user.local_area_id

        rules = db.get_active_rules()
        if not rules:
            logger.info("No active rules configured")
            db.clear_all_events()
            db.complete_scraper_fetch(
                fetch_id=fetch_id,
                events_found=0,
                rules_processed=0,
                status='SUCCESS',
                circuit_breaker_state=circuit_breaker.state
            )
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
                # Log error to database
                db.log_scraper_error(
                    status_code=None,
                    error_message=str(e),
                    error_type='EXCEPTION',
                    circuit_breaker_state=circuit_breaker.state,
                    rule_target=rule.target_name
                )

        logger.info(f"Fetch complete. {total_events} events from {len(rules)} rules.")

        # Record successful fetch cycle
        db.complete_scraper_fetch(
            fetch_id=fetch_id,
            events_found=total_events,
            rules_processed=len(rules),
            status='SUCCESS',
            circuit_breaker_state=circuit_breaker.state
        )
        _last_fetch_time = datetime.now()

        # Check alerts after successful fetch
        try:
            scraper_alerter.check_and_alert('SUCCESS')
        except Exception as e:
            logger.error(f"Alert check failed: {e}")

        # Phase 2: Dispatch — behaviour depends on notification_mode
        if new_events_map:
            notification_mode = config.scheduler.notification_mode

            if notification_mode == "daily_digest":
                # Queue events for digest — do NOT send immediately
                queued_count = 0
                for event_id, event in new_events_map.items():
                    # Determine which users should receive this event (via their rules)
                    for rule in event_rules.get(event_id, []):
                        if rule.user_id is not None:
                            db.queue_event_for_digest(event_id, rule.user_id)
                            queued_count += 1
                logger.info(
                    f"Daily digest mode: queued {queued_count} event-user notification(s) "
                    f"({len(new_events_map)} unique event(s)) for digest send"
                )
            else:
                # "upon_fetch" mode (default) — send immediately (existing behaviour)
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
        # Record failed fetch cycle if we have a fetch_id
        if fetch_id is not None:
            try:
                db = get_db()
                db.complete_scraper_fetch(
                    fetch_id=fetch_id,
                    events_found=0,
                    rules_processed=0,
                    status='FAILURE',
                    error_message=str(e),
                    circuit_breaker_state=circuit_breaker.state
                )
            except Exception as log_err:
                logger.debug(f"Could not log failed fetch cycle: {log_err}")
        try:
            scraper_alerter.check_and_alert('FAILURE')
        except Exception as alert_e:
            logger.error(f"Alert check failed: {alert_e}")


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

    # Clean up old scraper health logs (30-day retention)
    try:
        db.cleanup_old_scraper_logs(days=30)
    except Exception as e:
        logger.error(f"Failed to cleanup scraper logs: {e}")

    # Clean up old scraper fetch logs (30-day retention)
    try:
        db.cleanup_old_fetch_logs(days=30)
    except Exception as e:
        logger.error(f"Failed to cleanup fetch logs: {e}")


def send_daily_digest():
    """Daily digest job: collect queued events per user and send batched notifications.

    Runs at config.scheduler.digest_time. Only meaningful when notification_mode == 'daily_digest'.
    Skips silently if there are no queued events.
    """
    logger.info("Starting daily digest job")

    config = get_config()
    db = get_db()

    # Get all distinct users who have events queued for digest
    try:
        with db.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT DISTINCT user_id FROM notifications
                WHERE queued_for_digest = {db._true_val} AND sent_at IS NULL AND user_id IS NOT NULL
                """
            ).fetchall()
        user_ids = [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Failed to query queued digest users: {e}")
        return

    if not user_ids:
        logger.info("Daily digest: no queued events to send")
        return

    logger.info(f"Daily digest: sending to {len(user_ids)} user(s)")

    from ..services.notifier import notify_users_for_events_async, _run_async

    for user_id in user_ids:
        try:
            event_ids = db.get_queued_digest_events(user_id)
            if not event_ids:
                continue

            # Load full Event objects for queued event_ids
            events_with_rules = []
            for event_id in event_ids:
                event = db.get_event(event_id)
                if event is None:
                    logger.warning(f"Digest: event {event_id} not found in DB, skipping")
                    continue
                # Get matching rules for this user and event
                rules = db.get_rules_for_event_and_user(event_id, user_id)
                if rules:
                    events_with_rules.append((event, rules))

            if not events_with_rules:
                logger.info(f"Digest user {user_id}: no valid events to send")
                db.mark_digest_sent(event_ids, user_id)
                continue

            # Send batched notification using existing per-user notify path
            results = _run_async(notify_users_for_events_async(events_with_rules))

            user_result = results.get(user_id, {})
            if user_result.get("telegram") or user_result.get("email"):
                db.mark_digest_sent(event_ids, user_id)
                logger.info(f"Digest sent to user {user_id}: {len(events_with_rules)} event(s)")
            else:
                logger.warning(f"Digest send failed for user {user_id} — events remain queued")

        except Exception as e:
            logger.error(f"Digest failed for user {user_id}: {e}")

    logger.info("Daily digest job complete")


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

    fetch_times = config.scheduler.fetch_times  # list of "HH:MM" strings

    if fetch_times:
        # Schedule one CronTrigger job per configured time
        for i, time_str in enumerate(fetch_times):
            try:
                hour, minute = time_str.split(":")
                job_id = f"fetch_and_notify_{i}"
                scheduler.add_job(
                    fetch_and_notify,
                    trigger=CronTrigger(hour=int(hour), minute=int(minute)),
                    id=job_id,
                    name=f"Fetch events and send notifications at {time_str}",
                    replace_existing=True,
                )
                logger.info(f"Scheduled fetch job at {time_str} daily")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Invalid fetch_time '{time_str}', skipping: {e}")
        # Keep a canonical "fetch_and_notify" id pointing to first job (for get_next_fetch_time)
        if fetch_times:
            first_hour, first_minute = fetch_times[0].split(":")
            scheduler.add_job(
                fetch_and_notify,
                trigger=CronTrigger(hour=int(first_hour), minute=int(first_minute)),
                id="fetch_and_notify",
                name="Fetch events and send notifications (primary)",
                replace_existing=True,
            )
    else:
        # Fallback to legacy interval trigger
        fetch_interval = config.scheduler.fetch_interval_hours
        scheduler.add_job(
            fetch_and_notify,
            trigger=IntervalTrigger(hours=fetch_interval),
            id="fetch_and_notify",
            name="Fetch events and send notifications",
            replace_existing=True,
        )
        logger.info(f"Scheduled fetch job to run every {fetch_interval} hours (legacy interval mode)")

    # Account purge job - runs daily at 3 AM UTC
    scheduler.add_job(
        purge_expired_accounts,
        trigger=CronTrigger(hour=3, minute=0),
        id="purge_expired_accounts",
        name="Purge accounts past 30-day grace period",
        replace_existing=True,
    )
    logger.info("Scheduled purge job to run daily at 3:00 AM UTC")

    # Daily digest job - sends batched notifications at configured digest time
    digest_time_str = config.scheduler.digest_time  # "HH:MM"
    try:
        d_hour, d_minute = digest_time_str.split(":")
        scheduler.add_job(
            send_daily_digest,
            trigger=CronTrigger(hour=int(d_hour), minute=int(d_minute)),
            id="send_daily_digest",
            name="Send daily digest notifications",
            replace_existing=True,
        )
        logger.info(f"Scheduled daily digest job at {digest_time_str}")
    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid digest_time '{digest_time_str}', digest job not scheduled: {e}")

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
    """Get the timestamp of the last successful fetch.

    Primary source is the database (works across gunicorn workers).
    Falls back to in-memory _last_fetch_time if DB is unavailable.
    """
    try:
        db = get_db()
        summary = db.get_scraper_health_summary(days=365)
        db_time = summary.get("last_successful_fetch")
        if db_time is not None:
            return db_time
    except Exception as e:
        logger.debug(f"Could not query last fetch time from DB: {e}")
    # Fallback to in-memory variable (resets on worker restart)
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

    # Get circuit breaker status
    cb_status = circuit_breaker.get_status()
    cb_dict = {
        "state": cb_status.state,
        "failure_count": cb_status.failure_count,
        "last_success": cb_status.last_success.isoformat() if cb_status.last_success else None,
        "last_failure": cb_status.last_failure.isoformat() if cb_status.last_failure else None,
        "cooldown_duration": cb_status.cooldown_duration,
        "cooldown_remaining": cb_status.cooldown_remaining,
        "error_count_since_success": cb_status.error_count_since_success,
    }

    return {
        "running": scheduler.running,
        "last_fetch": _last_fetch_time.isoformat() if _last_fetch_time else None,
        "next_fetch": get_next_fetch_time().isoformat() if get_next_fetch_time() else None,
        "circuit_breaker": cb_dict,
    }
