"""Database models and connection management for RA Tracker - Simplified."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

from .config import get_config

SCHEMA = """
-- Tracking rules (artist, venue, or promoter)
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type TEXT NOT NULL,  -- 'artist', 'venue', 'promoter'
    target_id INTEGER NOT NULL,  -- RA ID
    target_name TEXT NOT NULL,  -- Display name
    is_active BOOLEAN DEFAULT 1,
    notify_mode TEXT DEFAULT 'local',  -- 'all', 'local', 'none' (artists use local/all/none, venues/promoters use all/none)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Cached events (only events matching rules)
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,  -- RA event ID
    title TEXT NOT NULL,
    date DATE NOT NULL,
    start_time DATETIME,
    end_time DATETIME,
    venue_id INTEGER,
    venue_name TEXT,
    area_id INTEGER,
    area_name TEXT,
    content_url TEXT,
    cost TEXT,
    is_ticketed BOOLEAN,
    is_festival BOOLEAN,
    is_multi_day BOOLEAN,
    attending INTEGER,
    interested_count INTEGER,
    pick_blurb TEXT,
    set_times_status TEXT,
    set_times_lineup TEXT,
    tickets_json TEXT,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Event to rule mapping (tracks which rules matched this event)
CREATE TABLE IF NOT EXISTS event_rules (
    event_id INTEGER,
    rule_id INTEGER,
    PRIMARY KEY (event_id, rule_id)
);

-- Event artists (many-to-many)
CREATE TABLE IF NOT EXISTS event_artists (
    event_id INTEGER,
    artist_id INTEGER,
    artist_name TEXT,
    artist_url TEXT,
    PRIMARY KEY (event_id, artist_id)
);

-- Event promoters (many-to-many)
CREATE TABLE IF NOT EXISTS event_promoters (
    event_id INTEGER,
    promoter_id INTEGER,
    promoter_name TEXT,
    PRIMARY KEY (event_id, promoter_id)
);

-- Sent notifications (prevent duplicates)
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    rule_id INTEGER NOT NULL,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, rule_id)
);

-- Users (multi-tenant support)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0,
    email_verified BOOLEAN DEFAULT 0,
    telegram_chat_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(is_active);
CREATE INDEX IF NOT EXISTS idx_rules_type ON rules(rule_type, target_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""

# Migration to add new columns to existing database
MIGRATIONS = [
    # Migration 1: Add new event columns
    """
    ALTER TABLE events ADD COLUMN end_time DATETIME;
    """,
    """
    ALTER TABLE events ADD COLUMN cost TEXT;
    """,
    """
    ALTER TABLE events ADD COLUMN is_ticketed BOOLEAN;
    """,
    """
    ALTER TABLE events ADD COLUMN is_festival BOOLEAN;
    """,
    """
    ALTER TABLE events ADD COLUMN is_multi_day BOOLEAN;
    """,
    """
    ALTER TABLE events ADD COLUMN attending INTEGER;
    """,
    """
    ALTER TABLE events ADD COLUMN interested_count INTEGER;
    """,
    """
    ALTER TABLE events ADD COLUMN pick_blurb TEXT;
    """,
    """
    ALTER TABLE events ADD COLUMN set_times_status TEXT;
    """,
    """
    ALTER TABLE events ADD COLUMN set_times_lineup TEXT;
    """,
    """
    ALTER TABLE events ADD COLUMN tickets_json TEXT;
    """,
    # Migration 2: Add artist_url to event_artists
    """
    ALTER TABLE event_artists ADD COLUMN artist_url TEXT;
    """,
    # Migration 3: Add notify_mode to rules
    """
    ALTER TABLE rules ADD COLUMN notify_mode TEXT DEFAULT 'local';
    """,
    # Migration 4: Add user_id to rules (nullable for existing data)
    """
    ALTER TABLE rules ADD COLUMN user_id INTEGER;
    """,
    # Migration 5: Add user_id to notifications (nullable for existing data)
    """
    ALTER TABLE notifications ADD COLUMN user_id INTEGER;
    """,
]


@dataclass
class User:
    """User account for multi-tenant support."""
    id: Optional[int]
    email: str  # Login identifier, must be unique
    password_hash: str = field(repr=False)  # Argon2id hash, exclude from repr for security
    display_name: str = ""  # Required at registration
    is_admin: bool = False  # First user gets True
    email_verified: bool = False  # For future verification feature
    telegram_chat_id: Optional[int] = None  # For Telegram linking (Phase 4)
    created_at: Optional[datetime] = None


@dataclass
class Rule:
    """Tracking rule for artist, venue, or promoter."""
    id: Optional[int]
    rule_type: str  # 'artist', 'venue', 'promoter'
    target_id: int  # RA ID
    target_name: str  # Display name
    is_active: bool = True
    notify_mode: str = 'local'  # 'all', 'local', 'none'
    created_at: Optional[datetime] = None
    user_id: Optional[int] = None  # Owner of this rule (NULL for legacy data)


@dataclass
class Event:
    """Event data."""
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
    pick_blurb: Optional[str] = None
    set_times_status: Optional[str] = None
    set_times_lineup: Optional[str] = None
    tickets_json: Optional[str] = None
    fetched_at: Optional[datetime] = None
    artists: List[tuple] = None  # List of (artist_id, artist_name, artist_url)
    promoters: List[tuple] = None  # List of (promoter_id, promoter_name)
    matched_rules: List[Rule] = None  # Rules that matched this event

    def __post_init__(self):
        if self.artists is None:
            self.artists = []
        if self.promoters is None:
            self.promoters = []
        if self.matched_rules is None:
            self.matched_rules = []


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = get_config().database.path
        self.db_path = db_path
        self._ensure_db_directory()

    def _ensure_db_directory(self):
        """Ensure the database directory exists."""
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """Get a database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self):
        """Initialize the database schema and run migrations."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA)
            # Run migrations for existing databases
            for migration in MIGRATIONS:
                try:
                    conn.execute(migration)
                except sqlite3.OperationalError:
                    # Column already exists, skip
                    pass

    # Rule operations
    def add_rule(self, rule: Rule) -> int:
        """Add a new rule and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO rules (rule_type, target_id, target_name, is_active, notify_mode)
                VALUES (?, ?, ?, ?, ?)
                """,
                (rule.rule_type, rule.target_id, rule.target_name, rule.is_active, rule.notify_mode),
            )
            return cursor.lastrowid

    def get_rule(self, rule_id: int) -> Optional[Rule]:
        """Get a rule by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return Rule(
                id=row["id"],
                rule_type=row["rule_type"],
                target_id=row["target_id"],
                target_name=row["target_name"],
                is_active=bool(row["is_active"]),
                notify_mode=row["notify_mode"] or "local",
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            )

    def get_active_rules(self) -> List[Rule]:
        """Get all active rules."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM rules WHERE is_active = 1 ORDER BY rule_type, target_name"
            )
            return [
                Rule(
                    id=row["id"],
                    rule_type=row["rule_type"],
                    target_id=row["target_id"],
                    target_name=row["target_name"],
                    is_active=bool(row["is_active"]),
                    notify_mode=row["notify_mode"] or "local",
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                )
                for row in cursor.fetchall()
            ]

    def get_all_rules(self) -> List[Rule]:
        """Get all rules."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM rules ORDER BY rule_type, target_name")
            return [
                Rule(
                    id=row["id"],
                    rule_type=row["rule_type"],
                    target_id=row["target_id"],
                    target_name=row["target_name"],
                    is_active=bool(row["is_active"]),
                    notify_mode=row["notify_mode"] or "local",
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                )
                for row in cursor.fetchall()
            ]

    def delete_rule(self, rule_id: int) -> None:
        """Delete a rule."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            conn.execute("DELETE FROM notifications WHERE rule_id = ?", (rule_id,))

    def set_rule_active(self, rule_id: int, is_active: bool) -> None:
        """Set rule active status."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE rules SET is_active = ? WHERE id = ?",
                (is_active, rule_id),
            )

    def set_rule_notify_mode(self, rule_id: int, notify_mode: str) -> None:
        """Set rule notification mode ('all', 'local', 'none')."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE rules SET notify_mode = ? WHERE id = ?",
                (notify_mode, rule_id),
            )

    def rule_exists(self, rule_type: str, target_id: int) -> bool:
        """Check if a rule already exists."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM rules WHERE rule_type = ? AND target_id = ?",
                (rule_type, target_id),
            )
            return cursor.fetchone() is not None

    # Event operations
    def upsert_event(self, event: Event, rule_id: Optional[int] = None) -> None:
        """Insert or update an event, optionally linking it to a rule."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO events (id, title, date, start_time, end_time, venue_id, venue_name,
                    area_id, area_name, content_url, cost, is_ticketed, is_festival, is_multi_day,
                    attending, interested_count, pick_blurb, set_times_status, set_times_lineup,
                    tickets_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    date = excluded.date,
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    venue_id = excluded.venue_id,
                    venue_name = excluded.venue_name,
                    area_id = excluded.area_id,
                    area_name = excluded.area_name,
                    content_url = excluded.content_url,
                    cost = excluded.cost,
                    is_ticketed = excluded.is_ticketed,
                    is_festival = excluded.is_festival,
                    is_multi_day = excluded.is_multi_day,
                    attending = excluded.attending,
                    interested_count = excluded.interested_count,
                    pick_blurb = excluded.pick_blurb,
                    set_times_status = excluded.set_times_status,
                    set_times_lineup = excluded.set_times_lineup,
                    tickets_json = excluded.tickets_json,
                    fetched_at = excluded.fetched_at
                """,
                (
                    event.id,
                    event.title,
                    event.date.isoformat() if event.date else None,
                    event.start_time.isoformat() if event.start_time else None,
                    event.end_time.isoformat() if event.end_time else None,
                    event.venue_id,
                    event.venue_name,
                    event.area_id,
                    event.area_name,
                    event.content_url,
                    event.cost,
                    event.is_ticketed,
                    event.is_festival,
                    event.is_multi_day,
                    event.attending,
                    event.interested_count,
                    event.pick_blurb,
                    event.set_times_status,
                    event.set_times_lineup,
                    event.tickets_json,
                    datetime.now().isoformat(),
                ),
            )

            # Link event to rule if provided
            if rule_id is not None:
                conn.execute(
                    "INSERT OR IGNORE INTO event_rules (event_id, rule_id) VALUES (?, ?)",
                    (event.id, rule_id),
                )

            # Update artists (now with artist_url)
            conn.execute("DELETE FROM event_artists WHERE event_id = ?", (event.id,))
            for artist_data in event.artists:
                # Handle both old format (id, name) and new format (id, name, url)
                if len(artist_data) >= 3:
                    artist_id, artist_name, artist_url = artist_data[0], artist_data[1], artist_data[2]
                else:
                    artist_id, artist_name = artist_data[0], artist_data[1]
                    artist_url = None
                conn.execute(
                    "INSERT OR IGNORE INTO event_artists (event_id, artist_id, artist_name, artist_url) VALUES (?, ?, ?, ?)",
                    (event.id, artist_id, artist_name, artist_url),
                )

            # Update promoters
            conn.execute("DELETE FROM event_promoters WHERE event_id = ?", (event.id,))
            for promoter_id, promoter_name in event.promoters:
                conn.execute(
                    "INSERT OR IGNORE INTO event_promoters (event_id, promoter_id, promoter_name) VALUES (?, ?, ?)",
                    (event.id, promoter_id, promoter_name),
                )

    def get_event(self, event_id: int) -> Optional[Event]:
        """Get an event by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            if row is None:
                return None

            event = Event(
                id=row["id"],
                title=row["title"],
                date=date.fromisoformat(row["date"]) if row["date"] else None,
                start_time=datetime.fromisoformat(row["start_time"]) if row["start_time"] else None,
                end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
                venue_id=row["venue_id"],
                venue_name=row["venue_name"],
                area_id=row["area_id"],
                area_name=row["area_name"],
                content_url=row["content_url"],
                cost=row["cost"],
                is_ticketed=bool(row["is_ticketed"]) if row["is_ticketed"] is not None else None,
                is_festival=bool(row["is_festival"]) if row["is_festival"] is not None else None,
                is_multi_day=bool(row["is_multi_day"]) if row["is_multi_day"] is not None else None,
                attending=row["attending"],
                interested_count=row["interested_count"],
                pick_blurb=row["pick_blurb"],
                set_times_status=row["set_times_status"],
                set_times_lineup=row["set_times_lineup"],
                tickets_json=row["tickets_json"],
                fetched_at=datetime.fromisoformat(row["fetched_at"]) if row["fetched_at"] else None,
            )

            # Get artists (now with artist_url)
            artist_cursor = conn.execute(
                "SELECT artist_id, artist_name, artist_url FROM event_artists WHERE event_id = ?",
                (event_id,),
            )
            event.artists = [(r["artist_id"], r["artist_name"], r["artist_url"]) for r in artist_cursor.fetchall()]

            # Get promoters
            promoter_cursor = conn.execute(
                "SELECT promoter_id, promoter_name FROM event_promoters WHERE event_id = ?",
                (event_id,),
            )
            event.promoters = [(r["promoter_id"], r["promoter_name"]) for r in promoter_cursor.fetchall()]

            # Get matched rules
            rule_cursor = conn.execute(
                """
                SELECT r.* FROM rules r
                JOIN event_rules er ON r.id = er.rule_id
                WHERE er.event_id = ?
                """,
                (event_id,),
            )
            event.matched_rules = [
                Rule(
                    id=r["id"],
                    rule_type=r["rule_type"],
                    target_id=r["target_id"],
                    target_name=r["target_name"],
                    is_active=bool(r["is_active"]),
                    notify_mode=r["notify_mode"] or "local",
                )
                for r in rule_cursor.fetchall()
            ]

            return event

    def get_upcoming_events(self, area_id: Optional[int] = None) -> List[Event]:
        """Get all upcoming events, optionally filtered by area."""
        with self.get_connection() as conn:
            today = date.today().isoformat()
            if area_id:
                cursor = conn.execute(
                    "SELECT * FROM events WHERE date >= ? AND area_id = ? ORDER BY date, start_time",
                    (today, area_id),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM events WHERE date >= ? ORDER BY date, start_time",
                    (today,),
                )

            events = []
            for row in cursor.fetchall():
                event = Event(
                    id=row["id"],
                    title=row["title"],
                    date=date.fromisoformat(row["date"]) if row["date"] else None,
                    start_time=datetime.fromisoformat(row["start_time"]) if row["start_time"] else None,
                    end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
                    venue_id=row["venue_id"],
                    venue_name=row["venue_name"],
                    area_id=row["area_id"],
                    area_name=row["area_name"],
                    content_url=row["content_url"],
                    cost=row["cost"],
                    is_ticketed=bool(row["is_ticketed"]) if row["is_ticketed"] is not None else None,
                    is_festival=bool(row["is_festival"]) if row["is_festival"] is not None else None,
                    is_multi_day=bool(row["is_multi_day"]) if row["is_multi_day"] is not None else None,
                    attending=row["attending"],
                    interested_count=row["interested_count"],
                    pick_blurb=row["pick_blurb"],
                    set_times_status=row["set_times_status"],
                    set_times_lineup=row["set_times_lineup"],
                    tickets_json=row["tickets_json"],
                    fetched_at=datetime.fromisoformat(row["fetched_at"]) if row["fetched_at"] else None,
                )

                # Get artists (now with artist_url)
                artist_cursor = conn.execute(
                    "SELECT artist_id, artist_name, artist_url FROM event_artists WHERE event_id = ?",
                    (event.id,),
                )
                event.artists = [(r["artist_id"], r["artist_name"], r["artist_url"]) for r in artist_cursor.fetchall()]

                # Get promoters
                promoter_cursor = conn.execute(
                    "SELECT promoter_id, promoter_name FROM event_promoters WHERE event_id = ?",
                    (event.id,),
                )
                event.promoters = [(r["promoter_id"], r["promoter_name"]) for r in promoter_cursor.fetchall()]

                # Get matched rules
                rule_cursor = conn.execute(
                    """
                    SELECT r.* FROM rules r
                    JOIN event_rules er ON r.id = er.rule_id
                    WHERE er.event_id = ?
                    """,
                    (event.id,),
                )
                event.matched_rules = [
                    Rule(
                        id=r["id"],
                        rule_type=r["rule_type"],
                        target_id=r["target_id"],
                        target_name=r["target_name"],
                        is_active=bool(r["is_active"]),
                        notify_mode=r["notify_mode"] or "local",
                    )
                    for r in rule_cursor.fetchall()
                ]

                events.append(event)

            return events

    def event_exists(self, event_id: int) -> bool:
        """Check if an event exists in the database."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM events WHERE id = ?", (event_id,))
            return cursor.fetchone() is not None

    def cleanup_past_events(self) -> int:
        """Remove events that have passed. Returns count of deleted events."""
        with self.get_connection() as conn:
            today = date.today().isoformat()
            cursor = conn.execute("DELETE FROM events WHERE date < ?", (today,))
            deleted = cursor.rowcount
            # Clean up orphaned artists/promoters
            conn.execute(
                "DELETE FROM event_artists WHERE event_id NOT IN (SELECT id FROM events)"
            )
            conn.execute(
                "DELETE FROM event_promoters WHERE event_id NOT IN (SELECT id FROM events)"
            )
            return deleted

    def clear_all_events(self) -> None:
        """Clear all events and related data. Called before each fetch."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM event_rules")
            conn.execute("DELETE FROM event_artists")
            conn.execute("DELETE FROM event_promoters")
            conn.execute("DELETE FROM events")

    # Notification operations
    def add_notification(self, event_id: int, rule_id: int) -> bool:
        """Add a notification record. Returns False if already exists."""
        with self.get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO notifications (event_id, rule_id) VALUES (?, ?)",
                    (event_id, rule_id),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def has_notification(self, event_id: int, rule_id: int) -> bool:
        """Check if a notification has been sent."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM notifications WHERE event_id = ? AND rule_id = ?",
                (event_id, rule_id),
            )
            return cursor.fetchone() is not None

    def has_event_notification(self, event_id: int) -> bool:
        """Check if any notification has been sent for this event (per-event dedup)."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM notifications WHERE event_id = ?",
                (event_id,),
            )
            return cursor.fetchone() is not None

    def add_event_notification(self, event_id: int) -> bool:
        """Mark an event as notified (using rule_id=0 for per-event tracking)."""
        with self.get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO notifications (event_id, rule_id) VALUES (?, 0)",
                    (event_id,),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self.get_connection() as conn:
            rules = conn.execute("SELECT COUNT(*) FROM rules WHERE is_active = 1").fetchone()[0]
            events = conn.execute(
                "SELECT COUNT(*) FROM events WHERE date >= ?",
                (date.today().isoformat(),)
            ).fetchone()[0]
            notifications = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]

            return {
                "active_rules": rules,
                "upcoming_events": events,
                "notifications_sent": notifications,
            }


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
        _db.init_schema()
    return _db


def set_db(db: Database) -> None:
    """Set the global database instance."""
    global _db
    _db = db
