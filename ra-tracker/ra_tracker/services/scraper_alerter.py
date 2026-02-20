"""Scraper failure alert service — sends Telegram alerts to admin."""

import logging
import asyncio
from typing import Optional

from telegram import Bot

from ..config import get_config
from ..database import get_db
from ..api.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

FAILURE_THRESHOLD = 3  # Alert after this many consecutive failures


class ScraperAlerter:
    """Sends Telegram admin alerts on scraper failures.

    Alert fires once after FAILURE_THRESHOLD consecutive failures, then silences
    until the scraper recovers. Recovery notification sent when fetch succeeds
    after an alerted outage. All state persists in the database (survives restarts).
    """

    def check_and_alert(self, fetch_status: str) -> None:
        """Check scraper state and send alerts if needed.

        Args:
            fetch_status: 'SUCCESS', 'FAILURE', or 'SKIPPED'
        """
        config = get_config()
        db = get_db()

        # Need bot token and admin chat_id for alerts
        if not config.telegram.bot_token or not config.telegram.chat_id:
            return

        try:
            alert_state = db.get_scraper_alert_state()
        except Exception as e:
            logger.error(f"Failed to read scraper alert state: {e}")
            return

        if fetch_status == 'SUCCESS':
            # Reset consecutive failures
            if alert_state['consecutive_failures'] > 0:
                failures_recovered_from = alert_state['consecutive_failures']
                try:
                    db.reset_consecutive_failures()
                except Exception as e:
                    logger.error(f"Failed to reset consecutive failures: {e}")
                    return

                # Send recovery notification if alert was previously sent
                if alert_state['alert_sent']:
                    self._send_telegram(
                        bot_token=config.telegram.bot_token,
                        chat_id=config.telegram.chat_id,
                        message=self._recovery_message(failures_recovered_from),
                    )
                    try:
                        db.set_scraper_alert_sent(False)
                    except Exception as e:
                        logger.error(f"Failed to clear alert_sent flag: {e}")

        elif fetch_status in ('FAILURE', 'SKIPPED'):
            # Increment consecutive failures
            new_count = alert_state['consecutive_failures'] + 1
            try:
                db.update_consecutive_failures(new_count)
            except Exception as e:
                logger.error(f"Failed to update consecutive failures: {e}")
                return

            # Alert on threshold (3+ failures) if not already alerted
            if new_count >= FAILURE_THRESHOLD and not alert_state['alert_sent']:
                self._send_telegram(
                    bot_token=config.telegram.bot_token,
                    chat_id=config.telegram.chat_id,
                    message=self._failure_message(new_count),
                )
                try:
                    db.set_scraper_alert_sent(
                        True,
                        message=f"Alert sent after {new_count} consecutive failures"
                    )
                except Exception as e:
                    logger.error(f"Failed to set alert_sent flag: {e}")

    def _failure_message(self, failure_count: int) -> str:
        """Build failure alert message."""
        cb_state = circuit_breaker.state
        return (
            f"Scraper Failure Alert\n\n"
            f"{failure_count} consecutive fetch failures detected.\n"
            f"Circuit breaker state: {cb_state}\n\n"
            f"Check /admin/scraper-status for details."
        )

    def _recovery_message(self, failures_recovered_from: int) -> str:
        """Build recovery notification message."""
        return (
            f"Scraper Recovered\n\n"
            f"Scraper recovered after {failures_recovered_from} failures.\n"
            f"System operating normally."
        )

    def _send_telegram(self, bot_token: str, chat_id: str, message: str) -> None:
        """Send Telegram message synchronously (called from scheduler thread)."""
        async def _send():
            bot = Bot(token=bot_token)
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                disable_notification=False,  # Admin alerts should notify
            )

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_send())
            loop.close()
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")


# Module-level singleton
scraper_alerter = ScraperAlerter()
