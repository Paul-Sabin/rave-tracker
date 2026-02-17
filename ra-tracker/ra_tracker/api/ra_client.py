"""GraphQL client for ra.co API - Targeted query approach."""

import logging
import random
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, List, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

RA_GRAPHQL_URL = "https://ra.co/graphql"


class ScraperError(Exception):
    """Base class for scraper errors."""
    pass


class IPBlockedException(Exception):
    """Raised when IP is blocked (403)."""
    pass


@dataclass
class RAEvent:
    """Event data from RA."""
    id: int
    title: str
    date: date
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    venue_id: Optional[int] = None
    venue_name: Optional[str] = None
    area_id: Optional[int] = None
    area_name: Optional[str] = None
    content_url: Optional[str] = None
    cost: Optional[str] = None
    is_ticketed: Optional[bool] = None
    is_festival: Optional[bool] = None
    is_multi_day: Optional[bool] = None
    attending: Optional[int] = None
    interested_count: Optional[int] = None
    pick_blurb: Optional[str] = None  # RA editor pick description
    set_times_status: Optional[str] = None  # NONE, PUBLISHED, etc.
    set_times_lineup: Optional[str] = None  # JSON string of lineup
    tickets_json: Optional[str] = None  # JSON string of ticket info
    artists: List[tuple] = None  # List of (artist_id, artist_name, artist_url)
    promoters: List[tuple] = None  # List of (promoter_id, promoter_name)

    def __post_init__(self):
        if self.artists is None:
            self.artists = []
        if self.promoters is None:
            self.promoters = []


@dataclass
class RAArtist:
    """Artist data from RA."""
    id: int
    name: str


@dataclass
class RAVenue:
    """Venue data from RA."""
    id: int
    name: str


@dataclass
class RAPromoter:
    """Promoter data from RA."""
    id: int
    name: str


@dataclass
class RAArea:
    """Area/city data from RA."""
    id: int
    name: str


class RAClient:
    """GraphQL client for ra.co with targeted queries."""

    def __init__(self):
        self.session = requests.Session()

        # Initialize User-Agent generator
        self.ua_generator = UserAgent(
            browsers=['chrome', 'firefox', 'safari'],
            os=['windows', 'macos', 'linux'],
            min_version=100.0
        )

        # Configure retry strategy with exponential backoff
        retry_strategy = Retry(
            total=3,  # 3 retries
            backoff_factor=1,  # Produces 1s, 2s, 4s delays
            status_forcelist=[429, 500, 502, 503, 504],  # NOT 403
            allowed_methods=["POST"],
            respect_retry_after_header=True,
            raise_on_status=False  # We handle status codes manually
        )

        # Mount adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Set initial headers
        self.session.headers.update({
            "Content-Type": "application/json",
            "Referer": "https://ra.co/",
        })

        # Set initial User-Agent and track request count for rotation
        self._rotate_user_agent()
        self._request_count = 0
        self._rotation_interval = random.randint(5, 10)

    def _rotate_user_agent(self):
        """Rotate User-Agent string to appear more human-like."""
        new_ua = self.ua_generator.random
        self.session.headers.update({"User-Agent": new_ua})
        logger.debug(f"Rotated User-Agent: {new_ua[:60]}...")

    def _add_request_delay(self):
        """Add random delay between requests to appear more human-like."""
        delay = random.uniform(1.0, 3.0)
        logger.debug(f"Adding request delay: {delay:.2f}s")
        time.sleep(delay)

    def _execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query with resilience features."""
        # Rotate User-Agent periodically
        self._request_count += 1
        if self._request_count % self._rotation_interval == 0:
            self._rotate_user_agent()
            self._rotation_interval = random.randint(5, 10)  # Reset interval

        # Add random delay between requests
        self._add_request_delay()

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = self.session.post(RA_GRAPHQL_URL, json=payload, timeout=30)

            # Log response status for all requests
            logger.info(f"RA.co response: HTTP {response.status_code}")

            # Handle different status codes
            if response.status_code == 403:
                logger.error("403 Forbidden - IP likely blocked")
                raise IPBlockedException("IP blocked by RA.co (HTTP 403)")

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "unknown")
                logger.warning(f"429 Rate Limited - Retry-After: {retry_after}")
                response.raise_for_status()  # Trigger urllib3 retry

            # For other non-200 status codes, raise to trigger retry
            if response.status_code != 200:
                response.raise_for_status()

            # Parse response
            data = response.json()

            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                raise ScraperError(f"GraphQL errors: {data['errors']}")

            return data.get("data", {})
        except IPBlockedException:
            # Re-raise IP blocked exception without wrapping
            raise
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def _parse_event(self, event_data: dict) -> Optional[RAEvent]:
        """Parse event data from GraphQL response."""
        import json

        if not event_data:
            return None

        # Parse date
        event_date = None
        if event_data.get("date"):
            try:
                event_date = date.fromisoformat(event_data["date"][:10])
            except (ValueError, TypeError):
                pass

        # Parse start time
        start_time = None
        if event_data.get("startTime"):
            try:
                start_time = datetime.fromisoformat(
                    event_data["startTime"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Parse end time
        end_time = None
        if event_data.get("endTime"):
            try:
                end_time = datetime.fromisoformat(
                    event_data["endTime"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Parse venue
        venue = event_data.get("venue") or {}
        venue_id = int(venue["id"]) if venue.get("id") else None
        venue_name = venue.get("name")

        # Parse area
        area = event_data.get("area") or {}
        area_id = int(area["id"]) if area.get("id") else None
        area_name = area.get("name")

        # Parse artists (now includes contentUrl)
        artists = []
        for artist in event_data.get("artists") or []:
            if artist.get("id") and artist.get("name"):
                artist_url = artist.get("contentUrl", "")
                artists.append((int(artist["id"]), artist["name"], artist_url))

        # Parse promoters
        promoters = []
        for promoter in event_data.get("promoters") or []:
            if promoter.get("id") and promoter.get("name"):
                promoters.append((int(promoter["id"]), promoter["name"]))

        # Parse pick (RA editor pick)
        pick = event_data.get("pick")
        pick_blurb = pick.get("blurb") if pick else None

        # Parse set times
        set_times = event_data.get("setTimes") or {}
        set_times_status = set_times.get("status")
        set_times_lineup = json.dumps(set_times.get("lineup")) if set_times.get("lineup") else None

        # Parse tickets as JSON
        tickets = event_data.get("tickets") or []
        tickets_json = json.dumps(tickets) if tickets else None

        return RAEvent(
            id=int(event_data.get("id", 0)),
            title=event_data.get("title", ""),
            date=event_date,
            start_time=start_time,
            end_time=end_time,
            venue_id=venue_id,
            venue_name=venue_name,
            area_id=area_id,
            area_name=area_name,
            content_url=event_data.get("contentUrl", ""),
            cost=event_data.get("cost") or None,
            is_ticketed=event_data.get("isTicketed"),
            is_festival=event_data.get("isFestival"),
            is_multi_day=event_data.get("isMultiDayEvent"),
            attending=event_data.get("attending"),
            interested_count=event_data.get("interestedCount"),
            pick_blurb=pick_blurb,
            set_times_status=set_times_status,
            set_times_lineup=set_times_lineup,
            tickets_json=tickets_json,
            artists=artists,
            promoters=promoters,
        )

    def get_artist_events(self, artist_id: int, limit: int = 50) -> List[RAEvent]:
        """Get upcoming events for an artist."""
        query = """
        query GET_ARTIST_EVENTS($id: ID!) {
            artist(id: $id) {
                id
                name
                events(limit: 50, type: LATEST) {
                    id
                    title
                    date
                    startTime
                    endTime
                    contentUrl
                    cost
                    isTicketed
                    isFestival
                    isMultiDayEvent
                    attending
                    interestedCount
                    pick {
                        id
                        blurb
                    }
                    setTimes {
                        status
                        lineup
                    }
                    tickets {
                        id
                        title
                        priceRetail
                        currency {
                            code
                            symbol
                        }
                        onSaleFrom
                        onSaleUntil
                        status
                    }
                    venue {
                        id
                        name
                    }
                    area {
                        id
                        name
                    }
                    artists {
                        id
                        name
                        contentUrl
                    }
                    promoters {
                        id
                        name
                    }
                }
            }
        }
        """

        data = self._execute(query, {"id": str(artist_id)})
        artist = data.get("artist")
        if not artist:
            logger.warning(f"Artist {artist_id} not found")
            return []

        events = []
        for event_data in artist.get("events") or []:
            event = self._parse_event(event_data)
            if event and event.date and event.date >= date.today():
                events.append(event)

        logger.info(f"Found {len(events)} upcoming events for artist {artist.get('name')}")
        return events

    def get_venue_events(self, venue_id: int, limit: int = 50) -> List[RAEvent]:
        """Get upcoming events for a venue."""
        query = """
        query GET_VENUE_EVENTS($id: ID!) {
            venue(id: $id) {
                id
                name
                events(limit: 50, type: LATEST) {
                    id
                    title
                    date
                    startTime
                    endTime
                    contentUrl
                    cost
                    isTicketed
                    isFestival
                    isMultiDayEvent
                    attending
                    interestedCount
                    pick {
                        id
                        blurb
                    }
                    setTimes {
                        status
                        lineup
                    }
                    tickets {
                        id
                        title
                        priceRetail
                        currency {
                            code
                            symbol
                        }
                        onSaleFrom
                        onSaleUntil
                        status
                    }
                    venue {
                        id
                        name
                    }
                    area {
                        id
                        name
                    }
                    artists {
                        id
                        name
                        contentUrl
                    }
                    promoters {
                        id
                        name
                    }
                }
            }
        }
        """

        data = self._execute(query, {"id": str(venue_id)})
        venue = data.get("venue")
        if not venue:
            logger.warning(f"Venue {venue_id} not found")
            return []

        events = []
        for event_data in venue.get("events") or []:
            event = self._parse_event(event_data)
            if event and event.date and event.date >= date.today():
                events.append(event)

        logger.info(f"Found {len(events)} upcoming events for venue {venue.get('name')}")
        return events

    def get_promoter_events(self, promoter_id: int, limit: int = 50) -> List[RAEvent]:
        """Get upcoming events for a promoter."""
        query = """
        query GET_PROMOTER_EVENTS($id: ID!) {
            promoter(id: $id) {
                id
                name
                events(limit: 50, type: LATEST) {
                    id
                    title
                    date
                    startTime
                    endTime
                    contentUrl
                    cost
                    isTicketed
                    isFestival
                    isMultiDayEvent
                    attending
                    interestedCount
                    pick {
                        id
                        blurb
                    }
                    setTimes {
                        status
                        lineup
                    }
                    tickets {
                        id
                        title
                        priceRetail
                        currency {
                            code
                            symbol
                        }
                        onSaleFrom
                        onSaleUntil
                        status
                    }
                    venue {
                        id
                        name
                    }
                    area {
                        id
                        name
                    }
                    artists {
                        id
                        name
                        contentUrl
                    }
                    promoters {
                        id
                        name
                    }
                }
            }
        }
        """

        data = self._execute(query, {"id": str(promoter_id)})
        promoter = data.get("promoter")
        if not promoter:
            logger.warning(f"Promoter {promoter_id} not found")
            return []

        events = []
        for event_data in promoter.get("events") or []:
            event = self._parse_event(event_data)
            if event and event.date and event.date >= date.today():
                events.append(event)

        logger.info(f"Found {len(events)} upcoming events for promoter {promoter.get('name')}")
        return events

    def search_artists(self, query: str, limit: int = 10) -> List[RAArtist]:
        """Search for artists by name."""
        gql_query = """
        query SEARCH($searchTerm: String!, $limit: Int) {
            search(searchTerm: $searchTerm, indices: [ARTIST], limit: $limit) {
                id
                value
            }
        }
        """

        try:
            data = self._execute(gql_query, {"searchTerm": query, "limit": limit})
            results = data.get("search", [])
            return [
                RAArtist(id=int(r["id"]), name=r["value"])
                for r in results
                if r.get("id") and r.get("value")
            ]
        except Exception as e:
            logger.warning(f"Artist search failed: {e}")
            return []

    def search_venues(self, query: str, limit: int = 10) -> List[RAVenue]:
        """Search for venues by name."""
        gql_query = """
        query SEARCH($searchTerm: String!, $limit: Int) {
            search(searchTerm: $searchTerm, indices: [CLUB], limit: $limit) {
                id
                value
            }
        }
        """

        try:
            data = self._execute(gql_query, {"searchTerm": query, "limit": limit})
            results = data.get("search", [])
            return [
                RAVenue(id=int(r["id"]), name=r["value"])
                for r in results
                if r.get("id") and r.get("value")
            ]
        except Exception as e:
            logger.warning(f"Venue search failed: {e}")
            return []

    def search_promoters(self, query: str, limit: int = 10) -> List[RAPromoter]:
        """Search for promoters by name."""
        gql_query = """
        query SEARCH($searchTerm: String!, $limit: Int) {
            search(searchTerm: $searchTerm, indices: [PROMOTER], limit: $limit) {
                id
                value
            }
        }
        """

        try:
            data = self._execute(gql_query, {"searchTerm": query, "limit": limit})
            results = data.get("search", [])
            return [
                RAPromoter(id=int(r["id"]), name=r["value"])
                for r in results
                if r.get("id") and r.get("value")
            ]
        except Exception as e:
            logger.warning(f"Promoter search failed: {e}")
            return []

    def search_areas(self, query: str, limit: int = 10) -> List[RAArea]:
        """Search for areas/cities by name."""
        gql_query = """
        query SEARCH($searchTerm: String!, $limit: Int) {
            search(searchTerm: $searchTerm, indices: [AREA], limit: $limit) {
                id
                value
            }
        }
        """

        try:
            data = self._execute(gql_query, {"searchTerm": query, "limit": limit})
            results = data.get("search", [])
            return [
                RAArea(id=int(r["id"]), name=r["value"])
                for r in results
                if r.get("id") and r.get("value")
            ]
        except Exception as e:
            logger.warning(f"Area search failed: {e}")
            return []

    def get_artist(self, artist_id: int) -> Optional[RAArtist]:
        """Get artist by ID."""
        query = """
        query GET_ARTIST($id: ID!) {
            artist(id: $id) {
                id
                name
            }
        }
        """
        try:
            data = self._execute(query, {"id": str(artist_id)})
            artist = data.get("artist")
            if artist:
                return RAArtist(id=int(artist["id"]), name=artist["name"])
        except Exception as e:
            logger.warning(f"Get artist failed: {e}")
        return None

    def get_venue(self, venue_id: int) -> Optional[RAVenue]:
        """Get venue by ID."""
        query = """
        query GET_VENUE($id: ID!) {
            venue(id: $id) {
                id
                name
            }
        }
        """
        try:
            data = self._execute(query, {"id": str(venue_id)})
            venue = data.get("venue")
            if venue:
                return RAVenue(id=int(venue["id"]), name=venue["name"])
        except Exception as e:
            logger.warning(f"Get venue failed: {e}")
        return None

    def get_promoter(self, promoter_id: int) -> Optional[RAPromoter]:
        """Get promoter by ID."""
        query = """
        query GET_PROMOTER($id: ID!) {
            promoter(id: $id) {
                id
                name
            }
        }
        """
        try:
            data = self._execute(query, {"id": str(promoter_id)})
            promoter = data.get("promoter")
            if promoter:
                return RAPromoter(id=int(promoter["id"]), name=promoter["name"])
        except Exception as e:
            logger.warning(f"Get promoter failed: {e}")
        return None


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    client = RAClient()

    print("Testing targeted queries...\n")

    # Test artist events
    print("Artist events (Maya Jane Coles - ID 11019):")
    events = client.get_artist_events(11019)
    for e in events[:3]:
        print(f"  {e.date} | {e.title} @ {e.venue_name}")

    print("\nVenue events (OHM Berlin - ID 75457):")
    events = client.get_venue_events(75457)
    for e in events[:3]:
        print(f"  {e.date} | {e.title}")

    print("\nPromoter events (OstGut GmbH - ID 1039):")
    events = client.get_promoter_events(1039)
    for e in events[:3]:
        print(f"  {e.date} | {e.title} @ {e.venue_name}")
