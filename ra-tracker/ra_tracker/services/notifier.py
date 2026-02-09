"""Telegram notifier service - sends notifications for events."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Tuple

from telegram import Bot
from telegram.error import TelegramError

from ..config import get_config
from ..database import get_db, Event, Rule
from ..services.email_sender import send_notification_email, is_email_configured

logger = logging.getLogger(__name__)

# Thread pool for running async code from sync contexts
_executor = ThreadPoolExecutor(max_workers=1)


def _run_async(coro):
    """Run an async coroutine from sync code, handling existing event loops."""
    try:
        # Check if there's already a running loop (e.g., FastAPI)
        loop = asyncio.get_running_loop()
        # We're in an async context, run in thread pool to avoid conflicts
        import concurrent.futures
        future = _executor.submit(asyncio.run, coro)
        return future.result(timeout=30)
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(coro)


class Notifier:
    """Service for sending Telegram notifications."""

    def __init__(self):
        self.config = get_config()
        self.db = get_db()
        self._bot = None

    @property
    def bot(self) -> Bot:
        """Get the Telegram bot instance."""
        if self._bot is None:
            if not self.config.telegram.bot_token:
                raise ValueError("Telegram bot token not configured")
            self._bot = Bot(token=self.config.telegram.bot_token)
        return self._bot

    def format_message(self, event: Event, rule: Rule) -> str:
        """Format a notification message for an event."""
        # Format date/time
        date_str = event.date.strftime("%a %d %b %Y") if event.date else "Date TBA"
        time_str = ""
        if event.start_time:
            time_str = f", {event.start_time.strftime('%H:%M')}"

        # Format venue
        venue = event.venue_name or "Venue TBA"

        # Format artists
        artist_list = ""
        if event.artists:
            artist_names = [name for _, name in event.artists[:5]]
            artist_list = ", ".join(artist_names)
            if len(event.artists) > 5:
                artist_list += f" +{len(event.artists) - 5} more"

        # Format rule match
        rule_type_label = rule.rule_type.title()

        # Build message
        lines = [
            f"🎵 *{self._escape_md(event.title)}*",
            "",
        ]

        if artist_list:
            lines.append(f"🎧 {self._escape_md(artist_list)}")

        lines.extend([
            f"📅 {date_str}{time_str}",
            f"📍 {self._escape_md(venue)}",
            "",
            f"✅ {rule_type_label}: {self._escape_md(rule.target_name)}",
        ])

        # Add link
        if event.content_url:
            url = event.content_url
            if not url.startswith("http"):
                url = f"https://ra.co{url}"
            lines.append(f"\n🔗 {url}")

        return "\n".join(lines)

    def _escape_md(self, text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
        if not text:
            return ""
        special = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special:
            text = text.replace(char, f"\\{char}")
        return text

    async def send_notification_async(self, event: Event, rule: Rule) -> bool:
        """Send a notification asynchronously."""
        if not self.config.telegram.chat_id:
            logger.warning("Telegram chat_id not configured")
            return False

        message = self.format_message(event, rule)

        try:
            await self.bot.send_message(
                chat_id=self.config.telegram.chat_id,
                text=message,
                parse_mode="MarkdownV2",
                disable_web_page_preview=False,
            )
            self.db.add_notification(event.id, rule.id)
            logger.info(f"Sent notification for event {event.id}: {event.title}")
            return True

        except TelegramError as e:
            logger.error(f"Failed to send notification: {e}")
            # Try plain text fallback
            try:
                plain_msg = self._format_plain(event, rule)
                await self.bot.send_message(
                    chat_id=self.config.telegram.chat_id,
                    text=plain_msg,
                )
                self.db.add_notification(event.id, rule.id)
                return True
            except TelegramError as e2:
                logger.error(f"Plain text fallback also failed: {e2}")
                return False

    def _format_plain(self, event: Event, rule: Rule) -> str:
        """Format plain text message (no markdown)."""
        date_str = event.date.strftime("%a %d %b %Y") if event.date else "Date TBA"
        venue = event.venue_name or "TBA"

        lines = [
            f"🎵 {event.title}",
            f"📅 {date_str}",
            f"📍 {venue}",
            f"✅ {rule.rule_type.title()}: {rule.target_name}",
        ]

        if event.content_url:
            url = event.content_url
            if not url.startswith("http"):
                url = f"https://ra.co{url}"
            lines.append(f"🔗 {url}")

        return "\n".join(lines)

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.config.telegram.bot_token and self.config.telegram.chat_id)

    def send_notification(self, event: Event, rule: Rule) -> bool:
        """Send a notification synchronously."""
        if not self.is_configured():
            logger.debug("Telegram not configured, skipping notification")
            return False
        return _run_async(self.send_notification_async(event, rule))

    async def send_all_async(self, notifications: List[Tuple[Rule, List[Event]]]) -> int:
        """Send all notifications asynchronously."""
        sent = 0
        for rule, events in notifications:
            for event in events:
                if await self.send_notification_async(event, rule):
                    sent += 1
                await asyncio.sleep(0.5)  # Rate limit
        return sent

    def send_all(self, notifications: List[Tuple[Rule, List[Event]]]) -> int:
        """Send all notifications synchronously."""
        if not self.is_configured():
            logger.debug("Telegram not configured, skipping notifications")
            return 0
        return _run_async(self.send_all_async(notifications))

    async def send_test_async(self) -> bool:
        """Send a test message."""
        if not self.config.telegram.chat_id:
            return False
        try:
            await self.bot.send_message(
                chat_id=self.config.telegram.chat_id,
                text="🎵 Rave Tracker test - configuration working!",
            )
            return True
        except TelegramError as e:
            logger.error(f"Test message failed: {e}")
            return False

    def send_test(self) -> bool:
        """Send a test message synchronously."""
        if not self.is_configured():
            raise ValueError("Telegram bot token and chat ID must be configured")
        return _run_async(self.send_test_async())

    def send_summary(self, new_events: List[Tuple[Event, Rule]]) -> bool:
        """Send a summary notification for all new events. Non-blocking on failure."""
        if not self.is_configured():
            logger.debug("Telegram not configured, skipping summary")
            return False

        if not new_events:
            return True

        try:
            message = self._format_summary(new_events)
            _run_async(self._send_summary_async(message))

            # Mark all events as notified
            for event, rule in new_events:
                self.db.add_notification(event.id, rule.id)

            logger.info(f"Sent summary notification for {len(new_events)} events")
            return True

        except Exception as e:
            logger.warning(f"Failed to send summary notification: {e}")
            return False

    async def _send_summary_async(self, message: str) -> None:
        """Send a summary message asynchronously."""
        await self.bot.send_message(
            chat_id=self.config.telegram.chat_id,
            text=message,
            disable_web_page_preview=True,
        )

    def _format_summary(self, new_events: List[Tuple[Event, Rule]]) -> str:
        """Format a summary message for multiple new events."""
        # Group by rule
        by_rule = {}
        for event, rule in new_events:
            key = f"{rule.rule_type}:{rule.target_name}"
            if key not in by_rule:
                by_rule[key] = {"rule": rule, "events": []}
            by_rule[key]["events"].append(event)

        lines = [f"🎵 Rave Tracker: {len(new_events)} new events found!", ""]

        for key, data in by_rule.items():
            rule = data["rule"]
            events = data["events"]
            icon = "🎧" if rule.rule_type == "artist" else "📍" if rule.rule_type == "venue" else "🎪"
            lines.append(f"{icon} {rule.target_name}: {len(events)} event(s)")

            # List up to 3 events per rule
            for event in events[:3]:
                date_str = event.date.strftime("%d %b") if event.date else "TBA"
                venue = event.venue_name or ""
                venue_str = f" @ {venue}" if venue else ""
                lines.append(f"   • {date_str}: {event.title[:40]}{venue_str}")

            if len(events) > 3:
                lines.append(f"   ... +{len(events) - 3} more")
            lines.append("")

        lines.append("Check the dashboard for details.")
        return "\n".join(lines)

    def send_event_summary(self, new_events: List[Tuple[Event, List[Rule]]]) -> bool:
        """Send a summary notification for new events (per-event deduplication).

        Args:
            new_events: List of (event, matching_rules) tuples

        Returns:
            True if sent successfully
        """
        if not self.is_configured():
            logger.debug("Telegram not configured, skipping summary")
            return False

        if not new_events:
            return True

        try:
            message = self._format_event_summary(new_events)
            _run_async(self._send_summary_async(message))

            # Mark all events as notified (per-event, not per-rule)
            for event, _ in new_events:
                self.db.add_event_notification(event.id)

            logger.info(f"Sent event summary notification for {len(new_events)} events")
            return True

        except Exception as e:
            logger.warning(f"Failed to send event summary notification: {e}")
            return False

    def _format_event_summary(self, new_events: List[Tuple[Event, List[Rule]]]) -> str:
        """Format a summary message for events (grouped by date, each event once)."""
        # Sort events by date
        sorted_events = sorted(new_events, key=lambda x: (x[0].date or datetime.max.date(), x[0].start_time or datetime.max))

        lines = [f"🎵 Rave Tracker: {len(new_events)} new event(s)!", ""]

        for event, rules in sorted_events:
            # Date and time
            date_str = event.date.strftime("%a %d %b") if event.date else "TBA"
            time_str = event.start_time.strftime("%H:%M") if event.start_time else ""

            # Event title
            title = event.title[:50] if len(event.title) > 50 else event.title
            lines.append(f"📅 {date_str}{' ' + time_str if time_str else ''}")
            lines.append(f"   {title}")

            # Venue and location
            if event.venue_name:
                area = f" ({event.area_name})" if event.area_name else ""
                lines.append(f"   📍 {event.venue_name}{area}")

            # Show which rules matched (why this event is being notified)
            rule_names = [f"{r.rule_type[0].upper()}: {r.target_name}" for r in rules[:3]]
            if len(rules) > 3:
                rule_names.append(f"+{len(rules) - 3} more")
            lines.append(f"   ✅ {', '.join(rule_names)}")

            # Event link
            if event.content_url:
                url = event.content_url if event.content_url.startswith("http") else f"https://ra.co{event.content_url}"
                lines.append(f"   🔗 {url}")

            lines.append("")

        lines.append("Check the dashboard for details.")
        return "\n".join(lines)

    async def send_to_user_telegram_async(self, chat_id: int, events: List[Tuple[Event, List[Rule]]]) -> bool:
        """Send notification to a specific user's Telegram chat.

        Args:
            chat_id: User's Telegram chat ID
            events: List of (Event, matching_rules) tuples

        Returns:
            True if sent successfully
        """
        if not events:
            return True

        try:
            message = self._format_event_summary(events)
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                disable_web_page_preview=True,
            )
            logger.info(f"Sent Telegram notification to chat {chat_id} with {len(events)} events")
            return True
        except Exception as e:
            logger.warning(f"Failed to send Telegram to chat {chat_id}: {e}")
            return False


def get_notifier() -> Notifier:
    """Get a notifier instance."""
    return Notifier()


async def notify_users_for_events_async(new_events: List[Tuple[Event, List[Rule]]]) -> Dict[int, Dict[str, bool]]:
    """Send notifications to each user based on their preferences.

    Replaces the old single-chat notification pattern. For each event,
    finds which users have rules that matched it and sends to their
    enabled channels.

    Args:
        new_events: List of (Event, matching_rules) tuples

    Returns:
        Dict of user_id -> {"telegram": success, "email": success}
    """
    if not new_events:
        return {}

    db = get_db()
    results: Dict[int, Dict[str, bool]] = {}

    # Group events by user (via their rules)
    user_events: Dict[int, List[Tuple[Event, List[Rule]]]] = {}
    for event, rules in new_events:
        for rule in rules:
            user_id = rule.user_id
            if user_id is None:
                continue  # Skip legacy rules with no owner

            if user_id not in user_events:
                user_events[user_id] = []

            # Check if this event already added for this user
            event_ids = [e.id for e, _ in user_events[user_id]]
            if event.id not in event_ids:
                # Collect all rules from this user that match this event
                user_rules_for_event = [r for r in rules if r.user_id == user_id]
                user_events[user_id].append((event, user_rules_for_event))

    # Send to each user's enabled channels
    notifier = Notifier()
    email_available = is_email_configured()

    for user_id, events in user_events.items():
        user = db.get_user_by_id(user_id)
        if not user:
            logger.warning(f"User {user_id} not found, skipping notifications")
            continue

        results[user_id] = {"telegram": False, "email": False}

        # Check Telegram
        if user.telegram_enabled and user.telegram_chat_id:
            try:
                success = await notifier.send_to_user_telegram_async(
                    user.telegram_chat_id, events
                )
                results[user_id]["telegram"] = success
            except Exception as e:
                logger.error(f"Telegram notification failed for user {user_id}: {e}")

        # Check Email
        if user.email_enabled and email_available:
            try:
                success = await send_notification_email(
                    user.email,
                    user.id,
                    events,
                )
                results[user_id]["email"] = success
            except Exception as e:
                logger.error(f"Email notification failed for user {user_id}: {e}")

        # Mark events as notified for this user (only if at least one channel succeeded)
        if results[user_id]["telegram"] or results[user_id]["email"]:
            for event, _ in events:
                db.add_notification(event.id, rule_id=0, user_id=user_id)

    return results


def notify_users_for_events(new_events: List[Tuple[Event, List[Rule]]]) -> Dict[int, Dict[str, bool]]:
    """Sync wrapper for notify_users_for_events_async."""
    if not new_events:
        return {}
    return _run_async(notify_users_for_events_async(new_events))
