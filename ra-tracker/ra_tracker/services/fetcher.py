"""Fetcher service - retrieves events using targeted queries."""

import logging
from typing import List, Dict, Tuple

from ..api.ra_client import RAClient, RAEvent
from ..database import get_db, Event, Rule

logger = logging.getLogger(__name__)


class Fetcher:
    """Service for fetching events based on tracking rules."""

    def __init__(self):
        self.client = RAClient()
        self.db = get_db()

    def fetch_for_rule(self, rule: Rule) -> List[Event]:
        """Fetch events for a specific rule.

        Args:
            rule: The tracking rule

        Returns:
            List of events fetched for this rule
        """
        logger.info(f"Fetching events for {rule.rule_type} rule: {rule.target_name}")

        try:
            if rule.rule_type == "artist":
                ra_events = self.client.get_artist_events(rule.target_id)
            elif rule.rule_type == "venue":
                ra_events = self.client.get_venue_events(rule.target_id)
            elif rule.rule_type == "promoter":
                ra_events = self.client.get_promoter_events(rule.target_id)
            else:
                logger.warning(f"Unknown rule type: {rule.rule_type}")
                return []
        except Exception as e:
            logger.error(f"Failed to fetch events for rule {rule.target_name}: {e}")
            return []

        # Convert and store events
        events = []
        for ra_event in ra_events:
            event = self._convert_event(ra_event)
            if event:
                self.db.upsert_event(event, rule_id=rule.id)
                events.append(event)

        logger.info(f"Fetched {len(events)} events for {rule.target_name}")
        return events

    def fetch_all_rules(self) -> Dict[int, List[Event]]:
        """Fetch events for all active rules.

        Returns:
            Dict mapping rule_id to list of events
        """
        rules = self.db.get_active_rules()
        if not rules:
            logger.warning("No active rules configured")
            return {}

        results = {}
        seen_event_ids = set()

        for rule in rules:
            events = self.fetch_for_rule(rule)
            # Track which events are new (not seen in previous rules)
            new_events = [e for e in events if e.id not in seen_event_ids]
            results[rule.id] = events
            seen_event_ids.update(e.id for e in events)

        total_events = len(seen_event_ids)
        logger.info(f"Fetched {total_events} unique events across {len(rules)} rules")

        return results

    def get_new_events_for_rule(self, rule: Rule) -> List[Event]:
        """Fetch events and return only those not already in DB.

        Args:
            rule: The tracking rule

        Returns:
            List of new events (not previously in database)
        """
        events = self.fetch_for_rule(rule)
        new_events = []

        for event in events:
            # Check if we've already notified for this event+rule combo
            if not self.db.has_notification(event.id, rule.id):
                new_events.append(event)

        return new_events

    def _convert_event(self, ra_event: RAEvent) -> Event:
        """Convert an RAEvent to a database Event."""
        return Event(
            id=ra_event.id,
            title=ra_event.title,
            date=ra_event.date,
            start_time=ra_event.start_time,
            end_time=ra_event.end_time,
            venue_id=ra_event.venue_id,
            venue_name=ra_event.venue_name,
            area_id=ra_event.area_id,
            area_name=ra_event.area_name,
            content_url=ra_event.content_url,
            cost=ra_event.cost,
            is_ticketed=ra_event.is_ticketed,
            is_festival=ra_event.is_festival,
            is_multi_day=ra_event.is_multi_day,
            attending=ra_event.attending,
            interested_count=ra_event.interested_count,
            pick_blurb=ra_event.pick_blurb,
            set_times_status=ra_event.set_times_status,
            set_times_lineup=ra_event.set_times_lineup,
            tickets_json=ra_event.tickets_json,
            artists=ra_event.artists,
            promoters=ra_event.promoters,
        )


def run_fetch() -> Dict[int, List[Event]]:
    """Run a fetch operation for all active rules.

    Returns:
        Dict mapping rule_id to list of events
    """
    fetcher = Fetcher()
    return fetcher.fetch_all_rules()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from ..database import Rule

    db = get_db()

    # Add test rules
    if not db.rule_exists("venue", 75457):
        db.add_rule(Rule(id=None, rule_type="venue", target_id=75457, target_name="OHM Berlin"))
    if not db.rule_exists("promoter", 1039):
        db.add_rule(Rule(id=None, rule_type="promoter", target_id=1039, target_name="OstGut GmbH"))

    results = run_fetch()
    for rule_id, events in results.items():
        rule = db.get_rule(rule_id)
        print(f"\n{rule.target_name}: {len(events)} events")
        for event in events[:3]:
            print(f"  {event.date} | {event.title}")
