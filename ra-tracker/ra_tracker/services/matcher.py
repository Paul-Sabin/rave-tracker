"""Matcher service - simplified for targeted query approach."""

import logging
from typing import List, Tuple

from ..database import get_db, Event, Rule

logger = logging.getLogger(__name__)


def get_unnotified_events(rule: Rule, events: List[Event]) -> List[Event]:
    """Get events that haven't been notified for this rule.

    Args:
        rule: The tracking rule
        events: List of events to check

    Returns:
        List of events not yet notified for this rule
    """
    db = get_db()
    unnotified = []

    for event in events:
        if not db.has_notification(event.id, rule.id):
            unnotified.append(event)

    return unnotified


def get_all_unnotified() -> List[Tuple[Rule, List[Event]]]:
    """Get all unnotified events grouped by rule.

    Returns:
        List of (rule, events) tuples
    """
    db = get_db()
    rules = db.get_active_rules()
    upcoming_events = db.get_upcoming_events()

    results = []

    for rule in rules:
        # Find events matching this rule
        matching_events = []

        for event in upcoming_events:
            matches = False

            if rule.rule_type == "artist":
                # Check if rule's artist is in event artists
                for artist_data in event.artists:
                    artist_id = artist_data[0]
                    if artist_id == rule.target_id:
                        matches = True
                        break

            elif rule.rule_type == "venue":
                if event.venue_id == rule.target_id:
                    matches = True

            elif rule.rule_type == "promoter":
                # Check if rule's promoter is in event promoters
                for promoter_data in event.promoters:
                    promoter_id = promoter_data[0]
                    if promoter_id == rule.target_id:
                        matches = True
                        break

            if matches and not db.has_notification(event.id, rule.id):
                matching_events.append(event)

        if matching_events:
            results.append((rule, matching_events))

    return results
