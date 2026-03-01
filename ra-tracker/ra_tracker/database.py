"""Database models and connection management for RA Tracker - Simplified."""

import hashlib
import json
import logging
import os
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.pool
    import psycopg2.extras
except ImportError:
    psycopg2 = None

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import get_config

# Password hashing using Argon2id (OWASP 2025 recommended)
_password_hasher = PasswordHasher()

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
    user_id INTEGER,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    queued_for_digest BOOLEAN DEFAULT 0,
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
    telegram_enabled BOOLEAN DEFAULT 0,
    email_enabled BOOLEAN DEFAULT 1,
    onboarding_completed BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Telegram link codes (temporary, for linking flow)
CREATE TABLE IF NOT EXISTS telegram_link_codes (
    code TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    used_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Sessions (user authentication tokens)
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Audit logs (security event tracking)
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,           -- 'auth.login', 'auth.logout', 'rule.create', etc.
    user_id INTEGER,                     -- NULL for anonymous/failed auth
    ip_address TEXT,                     -- Client IP
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    details TEXT,                        -- JSON blob for flexible context
    target_type TEXT,                    -- 'rule', 'user', 'settings', etc.
    target_id INTEGER                    -- ID of affected resource
);

-- Scraper health log (for error tracking and circuit breaker diagnostics)
CREATE TABLE IF NOT EXISTS scraper_health_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status_code INTEGER,
    error_message TEXT,
    error_type TEXT,
    circuit_breaker_state TEXT,
    rule_target TEXT
);

-- Scraper fetch log (persist fetch cycle state across worker restarts)
CREATE TABLE IF NOT EXISTS scraper_fetch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at DATETIME NOT NULL,
    completed_at DATETIME,
    duration_seconds REAL,
    events_found INTEGER DEFAULT 0,
    rules_processed INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'RUNNING',
    error_message TEXT,
    circuit_breaker_state TEXT
);
CREATE INDEX IF NOT EXISTS idx_scraper_fetch_started ON scraper_fetch_log(started_at DESC);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(is_active);
CREATE INDEX IF NOT EXISTS idx_rules_type ON rules(rule_type, target_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_link_codes_user ON telegram_link_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_link_codes_expires ON telegram_link_codes(expires_at);

-- Audit log indexes
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_logs(target_type, target_id);

-- Scraper health log indexes
CREATE INDEX IF NOT EXISTS idx_scraper_health_timestamp ON scraper_health_log(timestamp DESC);

-- Scraper alert state (singleton row — persists alert state across worker restarts)
CREATE TABLE IF NOT EXISTS scraper_alert_state (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    alert_sent INTEGER DEFAULT 0,
    alert_sent_at DATETIME,
    consecutive_failures INTEGER DEFAULT 0,
    last_alert_message TEXT
);
INSERT OR IGNORE INTO scraper_alert_state (id) VALUES (1);
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
    # Migration 6: Add telegram_enabled to users (default 0 = off)
    """
    ALTER TABLE users ADD COLUMN telegram_enabled BOOLEAN DEFAULT 0;
    """,
    # Migration 7: Add email_enabled to users (default 1 = on)
    """
    ALTER TABLE users ADD COLUMN email_enabled BOOLEAN DEFAULT 1;
    """,
    # Migration 8: Add dashboard_mode to rules (default 'local' = show local events)
    """
    ALTER TABLE rules ADD COLUMN dashboard_mode TEXT DEFAULT 'local';
    """,
    # Migration 9: Auto-verify admin users to prevent lockout after email verification requirement
    """
    UPDATE users SET email_verified = 1 WHERE is_admin = 1;
    """,
    # Migration 10: Add soft delete columns for account deletion with 30-day grace period
    """
    ALTER TABLE users ADD COLUMN deleted_at DATETIME;
    """,
    """
    ALTER TABLE users ADD COLUMN scheduled_purge_at DATETIME;
    """,
    # Migration 11: Add local_area_id for per-user local area preference
    """
    ALTER TABLE users ADD COLUMN local_area_id INTEGER;
    """,
    # Migration 12: Add local_area_name for per-user local area preference
    """
    ALTER TABLE users ADD COLUMN local_area_name TEXT DEFAULT '';
    """,
    # Migration 13: Add queued_for_digest to notifications for daily digest mode
    """
    ALTER TABLE notifications ADD COLUMN queued_for_digest BOOLEAN DEFAULT 0;
    """,
    # Migration 14: Add onboarding_completed for v3.4 wizard gating
    """
    ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0;
    """,
    # Migration 14b: Backfill — existing users with area or Telegram configured are already onboarded
    """
    UPDATE users SET onboarding_completed = 1
    WHERE local_area_id IS NOT NULL OR telegram_chat_id IS NOT NULL;
    """,
]

# PostgreSQL-compatible schema (for fresh databases)
PG_SCHEMA = """
-- Tracking rules (artist, venue, or promoter)
CREATE TABLE IF NOT EXISTS rules (
    id SERIAL PRIMARY KEY,
    rule_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    target_name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    notify_mode TEXT DEFAULT 'local',
    dashboard_mode TEXT DEFAULT 'local',
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cached events (only events matching rules)
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    date DATE NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
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
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Event to rule mapping
CREATE TABLE IF NOT EXISTS event_rules (
    event_id INTEGER,
    rule_id INTEGER,
    PRIMARY KEY (event_id, rule_id)
);

-- Event artists
CREATE TABLE IF NOT EXISTS event_artists (
    event_id INTEGER,
    artist_id INTEGER,
    artist_name TEXT,
    artist_url TEXT,
    PRIMARY KEY (event_id, artist_id)
);

-- Event promoters
CREATE TABLE IF NOT EXISTS event_promoters (
    event_id INTEGER,
    promoter_id INTEGER,
    promoter_name TEXT,
    PRIMARY KEY (event_id, promoter_id)
);

-- Sent notifications
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL,
    rule_id INTEGER NOT NULL,
    user_id INTEGER,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    queued_for_digest BOOLEAN DEFAULT FALSE,
    UNIQUE(event_id, rule_id)
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    email_verified BOOLEAN DEFAULT FALSE,
    telegram_chat_id INTEGER,
    telegram_enabled BOOLEAN DEFAULT FALSE,
    email_enabled BOOLEAN DEFAULT TRUE,
    local_area_id INTEGER,
    local_area_name TEXT DEFAULT '',
    deleted_at TIMESTAMP,
    scheduled_purge_at TIMESTAMP,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Telegram link codes
CREATE TABLE IF NOT EXISTS telegram_link_codes (
    code TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Audit logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id INTEGER,
    ip_address TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    target_type TEXT,
    target_id INTEGER
);

-- Scraper health log
CREATE TABLE IF NOT EXISTS scraper_health_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status_code INTEGER,
    error_message TEXT,
    error_type TEXT,
    circuit_breaker_state TEXT,
    rule_target TEXT
);

-- Scraper fetch log (persist fetch cycle state across worker restarts)
CREATE TABLE IF NOT EXISTS scraper_fetch_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds REAL,
    events_found INTEGER DEFAULT 0,
    rules_processed INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'RUNNING',
    error_message TEXT,
    circuit_breaker_state TEXT
);
CREATE INDEX IF NOT EXISTS idx_scraper_fetch_started ON scraper_fetch_log(started_at DESC);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(is_active);
CREATE INDEX IF NOT EXISTS idx_rules_type ON rules(rule_type, target_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_link_codes_user ON telegram_link_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_link_codes_expires ON telegram_link_codes(expires_at);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_logs(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_scraper_health_timestamp ON scraper_health_log(timestamp DESC);

-- Scraper alert state (singleton row — persists alert state across worker restarts)
CREATE TABLE IF NOT EXISTS scraper_alert_state (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    alert_sent BOOLEAN DEFAULT FALSE,
    alert_sent_at TIMESTAMP,
    consecutive_failures INTEGER DEFAULT 0,
    last_alert_message TEXT
);
INSERT INTO scraper_alert_state (id) VALUES (1) ON CONFLICT DO NOTHING;
"""


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
    telegram_enabled: bool = False  # Telegram notifications on/off
    email_enabled: bool = True  # Email notifications on/off (default enabled)
    local_area_id: Optional[int] = None  # User's preferred local area for filtering
    local_area_name: str = ""  # Display name of local area
    created_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None  # Soft delete timestamp (NULL = active)
    scheduled_purge_at: Optional[datetime] = None  # When hard purge will occur
    onboarding_completed: bool = False  # Set True after wizard completion or backfill


@dataclass
class Session:
    """User session for authentication."""
    id: str  # Secure token
    user_id: int
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


@dataclass
class Rule:
    """Tracking rule for artist, venue, or promoter."""
    id: Optional[int]
    rule_type: str  # 'artist', 'venue', 'promoter'
    target_id: int  # RA ID
    target_name: str  # Display name
    is_active: bool = True  # Deprecated: use dashboard_mode='none' and notify_mode='none' instead
    notify_mode: str = 'local'  # 'all', 'local', 'none' - controls notifications
    dashboard_mode: str = 'local'  # 'all', 'local', 'none' - controls dashboard visibility
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


class _PgConnectionWrapper:
    """Wrapper around psycopg2 connection providing execute()/executemany()
    with RealDictCursor. Needed because psycopg2 C extension connections
    don't allow attribute assignment for monkey-patching."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, query, params=None):
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def executemany(self, query, params_list):
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.executemany(query, params_list)
        return cursor

    def cursor(self):
        return self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)


class Database:
    """Dual-mode database manager (SQLite or PostgreSQL)."""

    def __init__(self, db_path: Optional[str] = None, db_url: Optional[str] = None):
        config = get_config()

        # Check if PostgreSQL URL is provided
        if db_url is None:
            db_url = config.database.url

        if db_url:
            # PostgreSQL mode
            if psycopg2 is None:
                raise ImportError("psycopg2 is required for PostgreSQL mode. Install with: pip install psycopg2")

            self.db_url = db_url
            self.db_path = None
            self._use_postgres = True

            # Create connection pool
            # Pool size = WEB_CONCURRENCY (workers) + 2 for scheduler/background tasks
            max_connections = int(os.environ.get("WEB_CONCURRENCY", "4")) + 2
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=max_connections,
                dsn=db_url
            )
        else:
            # SQLite fallback mode
            if db_path is None:
                db_path = config.database.path
            self.db_path = db_path
            self.db_url = None
            self._use_postgres = False
            self._pool = None
            self._ensure_db_directory()

    def _row_has_key(self, row, key: str) -> bool:
        """Check if row has a key (works for both dict and sqlite3.Row)."""
        if isinstance(row, dict):
            return key in row
        else:
            return key in row.keys()

    def _row_to_rule(self, row) -> Rule:
        """Convert a database row to a Rule object."""
        return Rule(
            id=row["id"],
            rule_type=row["rule_type"],
            target_id=row["target_id"],
            target_name=row["target_name"],
            is_active=bool(row["is_active"]),
            notify_mode=row["notify_mode"] or "local",
            dashboard_mode=row["dashboard_mode"] if self._row_has_key(row, "dashboard_mode") and row["dashboard_mode"] else "local",
            created_at=self._parse_datetime(row["created_at"]),
            user_id=row["user_id"] if self._row_has_key(row, "user_id") else None,
        )

    def _parse_datetime(self, val) -> Optional[datetime]:
        """Parse datetime value (handles both string and native datetime)."""
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            return datetime.fromisoformat(val)
        return None

    def _parse_date(self, val) -> Optional[date]:
        """Parse date value (handles both string and native date)."""
        if val is None:
            return None
        if isinstance(val, date):
            return val
        if isinstance(val, str):
            return date.fromisoformat(val)
        return None

    @property
    def ph(self) -> str:
        """Return the parameter placeholder for the current database backend."""
        return "%s" if self._use_postgres else "?"

    @property
    def _true_val(self) -> str:
        """Return TRUE literal for current database backend."""
        return "TRUE" if self._use_postgres else "1"

    @property
    def _false_val(self) -> str:
        """Return FALSE literal for current database backend."""
        return "FALSE" if self._use_postgres else "0"

    def _ensure_db_directory(self):
        """Ensure the database directory exists."""
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """Get a database connection context manager.

        For PostgreSQL, yields a wrapper providing execute()/executemany()
        with RealDictCursor for dict-like row access.
        """
        if self._use_postgres:
            # PostgreSQL mode: get connection from pool
            conn = self._pool.getconn()
            try:
                # Validate connection is alive (handles stale SSL connections)
                try:
                    conn.cursor().execute("SELECT 1")
                except (psycopg2.OperationalError, psycopg2.InterfaceError):
                    # Connection is stale — discard and get fresh one
                    logger.warning("Stale PostgreSQL connection detected, reconnecting")
                    self._pool.putconn(conn, close=True)
                    conn = self._pool.getconn()
                wrapper = _PgConnectionWrapper(conn)
                yield wrapper
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except (psycopg2.InterfaceError, psycopg2.OperationalError):
                    pass  # Connection already closed
                raise
            finally:
                self._pool.putconn(conn)
        else:
            # SQLite mode: traditional connection
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
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
        if self._use_postgres:
            # Step 1: Create tables (transactional)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for statement in PG_SCHEMA.split(';'):
                    statement = statement.strip()
                    if statement:
                        cursor.execute(statement)

            # Step 2: Run migrations in a separate autocommit connection so
            # each statement is fully isolated — a failed migration cannot put
            # the connection into an aborted-transaction state and block the rest.
            raw_conn = self._pool.getconn()
            try:
                raw_conn.autocommit = True
                cur = raw_conn.cursor()
                for i, migration in enumerate(MIGRATIONS):
                    migration = migration.strip()
                    if not migration:
                        continue
                    # Transform for PostgreSQL compatibility:
                    # - ADD COLUMN → ADD COLUMN IF NOT EXISTS (idempotent)
                    # - DATETIME → TIMESTAMP (SQLite type not valid in PG)
                    # - DEFAULT 0/1 → DEFAULT FALSE/TRUE (PG boolean literals)
                    pg_migration = (
                        migration
                        .replace("ADD COLUMN ", "ADD COLUMN IF NOT EXISTS ")
                        .replace("DATETIME", "TIMESTAMP")
                        .replace("DEFAULT 0", "DEFAULT FALSE")
                        .replace("DEFAULT 1", "DEFAULT TRUE")
                    )
                    try:
                        cur.execute(pg_migration)
                    except Exception as e:
                        logger.debug(f"PostgreSQL migration {i + 1} skipped: {e}")
            finally:
                self._pool.putconn(raw_conn)
        else:
            # SQLite mode
            with self.get_connection() as conn:
                conn.executescript(SCHEMA)
                for migration in MIGRATIONS:
                    try:
                        conn.execute(migration)
                    except sqlite3.OperationalError:
                        # Column already exists, skip
                        pass

    # User operations
    def has_users(self) -> bool:
        """Check if any users exist. Used for anonymous mode detection."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT EXISTS(SELECT 1 FROM users LIMIT 1)")
            return bool(cursor.fetchone()[0])

    def is_anonymous_mode(self) -> bool:
        """App is in anonymous mode until first user registers."""
        return not self.has_users()

    def create_user(self, email: str, password: str, display_name: str) -> int:
        """Create user. First user becomes admin and receives legacy data.

        Returns the new user ID.
        Raises sqlite3.IntegrityError if email already exists.
        """
        password_hash = _password_hasher.hash(password)

        with self.get_connection() as conn:
            # Check if this is first user (will become admin)
            is_first = not conn.execute(
                "SELECT EXISTS(SELECT 1 FROM users LIMIT 1)"
            ).fetchone()[0]

            if self._use_postgres:
                # PostgreSQL: use RETURNING id
                cursor = conn.execute(
                    f"""
                    INSERT INTO users (email, password_hash, display_name, is_admin, local_area_id, local_area_name)
                    VALUES ({self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph})
                    RETURNING id
                    """,
                    (email, password_hash, display_name, is_first, 34, "Berlin")
                )
                user_id = cursor.fetchone()["id"]
            else:
                # SQLite: use lastrowid
                cursor = conn.execute(
                    f"""
                    INSERT INTO users (email, password_hash, display_name, is_admin, local_area_id, local_area_name)
                    VALUES ({self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph})
                    """,
                    (email, password_hash, display_name, is_first, 34, "Berlin")
                )
                user_id = cursor.lastrowid

            # If first user, assign all legacy data (rules/notifications with NULL user_id)
            if is_first:
                conn.execute(f"UPDATE rules SET user_id = {self.ph} WHERE user_id IS NULL", (user_id,))
                conn.execute(f"UPDATE notifications SET user_id = {self.ph} WHERE user_id IS NULL", (user_id,))

            return user_id

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM users WHERE email = {self.ph}", (email,))
            row = cursor.fetchone()
            if row is None:
                return None
            return User(
                id=row["id"],
                email=row["email"],
                password_hash=row["password_hash"],
                display_name=row["display_name"],
                is_admin=bool(row["is_admin"]),
                email_verified=bool(row["email_verified"]),
                telegram_chat_id=row["telegram_chat_id"],
                telegram_enabled=bool(row["telegram_enabled"]) if row["telegram_enabled"] is not None else False,
                email_enabled=bool(row["email_enabled"]) if row["email_enabled"] is not None else True,
                local_area_id=row["local_area_id"] if row["local_area_id"] is not None else None,
                local_area_name=row["local_area_name"] or "",
                created_at=self._parse_datetime(row["created_at"]),
                deleted_at=self._parse_datetime(row["deleted_at"]),
                scheduled_purge_at=self._parse_datetime(row["scheduled_purge_at"]),
            )

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get a user by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM users WHERE id = {self.ph}", (user_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return User(
                id=row["id"],
                email=row["email"],
                password_hash=row["password_hash"],
                display_name=row["display_name"],
                is_admin=bool(row["is_admin"]),
                email_verified=bool(row["email_verified"]),
                telegram_chat_id=row["telegram_chat_id"],
                telegram_enabled=bool(row["telegram_enabled"]) if row["telegram_enabled"] is not None else False,
                email_enabled=bool(row["email_enabled"]) if row["email_enabled"] is not None else True,
                local_area_id=row["local_area_id"] if row["local_area_id"] is not None else None,
                local_area_name=row["local_area_name"] or "",
                created_at=self._parse_datetime(row["created_at"]),
                deleted_at=self._parse_datetime(row["deleted_at"]),
                scheduled_purge_at=self._parse_datetime(row["scheduled_purge_at"]),
            )

    def verify_password(self, stored_hash: str, password: str) -> tuple[bool, Optional[str]]:
        """Verify password against stored hash.

        Returns (success, new_hash_if_rehash_needed).
        If new_hash is returned, caller should update the stored hash.
        """
        try:
            _password_hasher.verify(stored_hash, password)
            # Check if hash needs upgrade (e.g., algorithm parameters changed)
            if _password_hasher.check_needs_rehash(stored_hash):
                return True, _password_hasher.hash(password)
            return True, None
        except VerifyMismatchError:
            return False, None

    def update_user_password_hash(self, user_id: int, new_hash: str) -> None:
        """Update a user's password hash (used for rehashing)."""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE users SET password_hash = {self.ph} WHERE id = {self.ph}",
                (new_hash, user_id)
            )

    def update_user_telegram(self, user_id: int, telegram_chat_id: Optional[int]) -> None:
        """Update a user's Telegram chat ID.

        Args:
            user_id: User ID to update
            telegram_chat_id: Telegram chat ID, or None to unlink
        f"""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE users SET telegram_chat_id = {self.ph} WHERE id = {self.ph}",
                (telegram_chat_id, user_id)
            )

    def set_email_verified(self, user_id: int, verified: bool = True) -> None:
        """Set a user's email verification status.

        Args:
            user_id: User ID to update
            verified: Verification status (default True)
        f"""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE users SET email_verified = {self.ph} WHERE id = {self.ph}",
                (verified, user_id)
            )

    def get_unverified_user_by_email(self, email: str) -> Optional[User]:
        """Get user only if email is not verified.

        Used for resend verification flow to prevent spam to verified users.

        Args:
            email: User's email address

        Returns:
            User if found and not verified, None otherwise
        f"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM users WHERE email = {self.ph} AND email_verified = {self._false_val}",
                (email,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return User(
                id=row["id"],
                email=row["email"],
                password_hash=row["password_hash"],
                display_name=row["display_name"],
                is_admin=bool(row["is_admin"]),
                email_verified=bool(row["email_verified"]),
                telegram_chat_id=row["telegram_chat_id"],
                telegram_enabled=bool(row["telegram_enabled"]) if row["telegram_enabled"] is not None else False,
                email_enabled=bool(row["email_enabled"]) if row["email_enabled"] is not None else True,
                local_area_id=row["local_area_id"] if row["local_area_id"] is not None else None,
                local_area_name=row["local_area_name"] or "",
                created_at=self._parse_datetime(row["created_at"]),
                deleted_at=self._parse_datetime(row["deleted_at"]),
                scheduled_purge_at=self._parse_datetime(row["scheduled_purge_at"]),
            )

    def get_user_by_telegram_chat_id(self, chat_id: int) -> Optional[User]:
        """Get a user by their Telegram chat ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM users WHERE telegram_chat_id = {self.ph}", (chat_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return User(
                id=row["id"],
                email=row["email"],
                password_hash=row["password_hash"],
                display_name=row["display_name"],
                is_admin=bool(row["is_admin"]),
                email_verified=bool(row["email_verified"]),
                telegram_chat_id=row["telegram_chat_id"],
                telegram_enabled=bool(row["telegram_enabled"]) if row["telegram_enabled"] is not None else False,
                email_enabled=bool(row["email_enabled"]) if row["email_enabled"] is not None else True,
                local_area_id=row["local_area_id"] if row["local_area_id"] is not None else None,
                local_area_name=row["local_area_name"] or "",
                created_at=self._parse_datetime(row["created_at"]),
                deleted_at=self._parse_datetime(row["deleted_at"]),
                scheduled_purge_at=self._parse_datetime(row["scheduled_purge_at"]),
            )

    def set_user_telegram_enabled(self, user_id: int, enabled: bool) -> None:
        """Set whether Telegram notifications are enabled for a user."""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE users SET telegram_enabled = {self.ph} WHERE id = {self.ph}",
                (enabled, user_id)
            )

    def set_user_email_enabled(self, user_id: int, enabled: bool) -> None:
        """Set whether email notifications are enabled for a user."""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE users SET email_enabled = {self.ph} WHERE id = {self.ph}",
                (enabled, user_id)
            )

    def update_user_local_area(self, user_id: int, local_area_id: Optional[int], local_area_name: str) -> None:
        """Update a user's local area preference."""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE users SET local_area_id = {self.ph}, local_area_name = {self.ph} WHERE id = {self.ph}",
                (local_area_id, local_area_name, user_id)
            )

    # Telegram link code operations
    def create_telegram_link_code(self, user_id: int, code: str, expires_at: datetime) -> None:
        """Create a new Telegram link code for a user."""
        with self.get_connection() as conn:
            conn.execute(
                f"""
                INSERT INTO telegram_link_codes (code, user_id, expires_at)
                VALUES ({self.ph}, {self.ph}, {self.ph})
                """,
                (code, user_id, expires_at.isoformat())
            )

    def get_telegram_link_code(self, code: str) -> Optional[dict]:
        """Get a Telegram link code by code string.

        Returns dict with user_id, expires_at, used_at, created_at or None if not found.
        f"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM telegram_link_codes WHERE code = {self.ph}",
                (code,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return {
                "code": row["code"],
                "user_id": row["user_id"],
                "created_at": self._parse_datetime(row["created_at"]),
                "expires_at": self._parse_datetime(row["expires_at"]),
                "used_at": self._parse_datetime(row["used_at"]),
            }

    def mark_link_code_used(self, code: str) -> None:
        """Mark a link code as used."""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE telegram_link_codes SET used_at = {self.ph} WHERE code = {self.ph}",
                (datetime.now().isoformat(), code)
            )

    def cleanup_expired_link_codes(self) -> int:
        """Delete expired link codes. Returns count of deleted codes."""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM telegram_link_codes WHERE expires_at <= {self.ph}",
                (now,)
            )
            return cursor.rowcount

    # Session operations
    def create_session(self, user_id: int, token: str, expires_at: datetime) -> None:
        """Insert a new session."""
        with self.get_connection() as conn:
            conn.execute(
                f"""
                INSERT INTO sessions (id, user_id, expires_at)
                VALUES ({self.ph}, {self.ph}, {self.ph})
                """,
                (token, user_id, expires_at.isoformat())
            )

    def get_session(self, token: str) -> Optional[Session]:
        """Get session by token (no expiry check)."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM sessions WHERE id = {self.ph}", (token,))
            row = cursor.fetchone()
            if row is None:
                return None
            return Session(
                id=row["id"],
                user_id=row["user_id"],
                created_at=self._parse_datetime(row["created_at"]),
                expires_at=self._parse_datetime(row["expires_at"]),
            )

    def get_valid_session(self, token: str) -> Optional[Session]:
        """Get session only if not expired. Uses constant-time comparison for token."""
        with self.get_connection() as conn:
            # Get all sessions and use constant-time comparison for token
            cursor = conn.execute("SELECT * FROM sessions")
            now = datetime.now()
            for row in cursor.fetchall():
                # Use constant-time comparison to prevent timing attacks
                if secrets.compare_digest(row["id"], token):
                    expires_at = self._parse_datetime(row["expires_at"])
                    # Check expiry using Python datetime for consistent timezone handling
                    if expires_at and expires_at > now:
                        return Session(
                            id=row["id"],
                            user_id=row["user_id"],
                            created_at=self._parse_datetime(row["created_at"]),
                            expires_at=expires_at,
                        )
                    return None  # Token found but expired
            return None

    def delete_session(self, token: str) -> None:
        """Delete a specific session."""
        with self.get_connection() as conn:
            conn.execute(f"DELETE FROM sessions WHERE id = {self.ph}", (token,))

    def delete_user_sessions(self, user_id: int) -> None:
        """Delete all sessions for a user."""
        with self.get_connection() as conn:
            conn.execute(f"DELETE FROM sessions WHERE user_id = {self.ph}", (user_id,))

    def update_session_expiry(self, token: str, expires_at: datetime) -> None:
        """Update expiry for sliding sessions."""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE sessions SET expires_at = {self.ph} WHERE id = {self.ph}",
                (expires_at.isoformat(), token)
            )

    def cleanup_expired_sessions(self) -> int:
        """Delete all expired sessions. Returns count of deleted sessions."""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM sessions WHERE expires_at <= {self.ph}",
                (now,)
            )
            return cursor.rowcount

    # Soft delete operations
    def soft_delete_user(self, user_id: int, scheduled_purge_at: datetime) -> bool:
        """Soft delete a user account with scheduled purge date.

        Sets deleted_at to current time and scheduled_purge_at to provided date.
        User cannot log in while soft-deleted but can recover during grace period.

        Args:
            user_id: User ID to soft delete
            scheduled_purge_at: When the hard purge will occur (typically 30 days)

        Returns:
            True if user found and updated, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"""
                UPDATE users
                SET deleted_at = {self.ph}, scheduled_purge_at = {self.ph}
                WHERE id = {self.ph}
                """,
                (datetime.utcnow().isoformat(), scheduled_purge_at.isoformat(), user_id)
            )
            return cursor.rowcount > 0

    def recover_user(self, user_id: int) -> bool:
        """Recover a soft-deleted user account.

        Clears deleted_at and scheduled_purge_at to restore account access.

        Args:
            user_id: User ID to recover

        Returns:
            True if user found and updated, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"""
                UPDATE users
                SET deleted_at = NULL, scheduled_purge_at = NULL
                WHERE id = {self.ph}
                """,
                (user_id,)
            )
            return cursor.rowcount > 0

    def get_users_pending_purge(self, before: datetime) -> List[User]:
        """Get users whose scheduled_purge_at is before the given time.

        Used by the daily purge cron job to find accounts past grace period.

        Args:
            before: Get users scheduled for purge before this time

        Returns:
            List of User objects pending purge
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"""
                SELECT * FROM users
                WHERE deleted_at IS NOT NULL
                AND scheduled_purge_at <= {self.ph}
                """,
                (before.isoformat(),)
            )
            return [
                User(
                    id=row["id"],
                    email=row["email"],
                    password_hash=row["password_hash"],
                    display_name=row["display_name"],
                    is_admin=bool(row["is_admin"]),
                    email_verified=bool(row["email_verified"]),
                    telegram_chat_id=row["telegram_chat_id"],
                    telegram_enabled=bool(row["telegram_enabled"]) if row["telegram_enabled"] is not None else False,
                    email_enabled=bool(row["email_enabled"]) if row["email_enabled"] is not None else True,
                    local_area_id=row["local_area_id"] if row["local_area_id"] is not None else None,
                    local_area_name=row["local_area_name"] or "",
                    created_at=self._parse_datetime(row["created_at"]),
                    deleted_at=self._parse_datetime(row["deleted_at"]),
                    scheduled_purge_at=self._parse_datetime(row["scheduled_purge_at"]),
                )
                for row in cursor.fetchall()
            ]

    def anonymize_audit_logs_for_user(self, user_id: int) -> int:
        """Anonymize audit logs for a purged user.

        Sets user_id to NULL and adds anonymization metadata to details JSON.
        Stores first 8 chars of SHA256 hash of original user_id for correlation.

        Args:
            user_id: User ID whose audit logs should be anonymized

        Returns:
            Count of rows updated
        """
        # Hash the user_id for correlation (first 8 chars of SHA256)
        user_id_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:8]

        with self.get_connection() as conn:
            if self._use_postgres:
                # PostgreSQL: use jsonb_set
                cursor = conn.execute(
                    f"""
                    UPDATE audit_logs
                    SET user_id = NULL,
                        details = jsonb_set(
                            jsonb_set(
                                COALESCE(details::jsonb, '{{}}'),
                                '{{anonymized}}', '1'
                            ),
                            '{{original_user_id_hash}}', to_jsonb({self.ph}::text)
                        )::text
                    WHERE user_id = {self.ph}
                    """,
                    (user_id_hash, user_id)
                )
            else:
                # SQLite: use json_set
                cursor = conn.execute(
                    f"""
                    UPDATE audit_logs
                    SET user_id = NULL,
                        details = json_set(
                            COALESCE(details, '{{}}'),
                            '$.anonymized', 1,
                            '$.original_user_id_hash', {self.ph}
                        )
                    WHERE user_id = {self.ph}
                    """,
                    (user_id_hash, user_id)
                )
            return cursor.rowcount

    def hard_delete_user(self, user_id: int) -> bool:
        """Permanently delete a user and all their data.

        Deletes in order to respect foreign keys:
        1. event_rules (for user's rules)
        2. notifications
        3. rules
        4. sessions
        5. telegram_link_codes
        6. user record

        Args:
            user_id: User ID to permanently delete

        Returns:
            True if user was deleted, False if user not found
        f"""
        with self.get_connection() as conn:
            # Check if user exists
            cursor = conn.execute(f"SELECT 1 FROM users WHERE id = {self.ph}", (user_id,))
            if cursor.fetchone() is None:
                return False

            # Delete event_rules for user's rules
            conn.execute(
                f"""
                DELETE FROM event_rules
                WHERE rule_id IN (SELECT id FROM rules WHERE user_id = {self.ph})
                """,
                (user_id,)
            )

            # Delete notifications for user
            conn.execute(f"DELETE FROM notifications WHERE user_id = {self.ph}", (user_id,))

            # Delete rules for user
            conn.execute(f"DELETE FROM rules WHERE user_id = {self.ph}", (user_id,))

            # Delete sessions for user
            conn.execute(f"DELETE FROM sessions WHERE user_id = {self.ph}", (user_id,))

            # Delete telegram link codes for user
            conn.execute(f"DELETE FROM telegram_link_codes WHERE user_id = {self.ph}", (user_id,))

            # Finally delete the user
            conn.execute(f"DELETE FROM users WHERE id = {self.ph}", (user_id,))

            return True

    def is_user_deleted(self, user_id: int) -> Optional[datetime]:
        """Check if a user is soft-deleted.

        Used by login flow to detect pending deletion and show recovery prompt.

        Args:
            user_id: User ID to check

        Returns:
            scheduled_purge_at datetime if user is soft-deleted, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"""
                SELECT scheduled_purge_at FROM users
                WHERE id = {self.ph} AND deleted_at IS NOT NULL
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._parse_datetime(row["scheduled_purge_at"])

    # Rule operations
    def add_rule(self, rule: Rule, user_id: Optional[int] = None) -> int:
        """Add a new rule and return its ID."""
        with self.get_connection() as conn:
            if self._use_postgres:
                # PostgreSQL: use RETURNING id
                cursor = conn.execute(
                    f"""
                    INSERT INTO rules (rule_type, target_id, target_name, is_active, notify_mode, dashboard_mode, user_id)
                    VALUES ({self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph})
                    RETURNING id
                    """,
                    (rule.rule_type, rule.target_id, rule.target_name, rule.is_active, rule.notify_mode, rule.dashboard_mode, user_id),
                )
                return cursor.fetchone()["id"]
            else:
                # SQLite: use lastrowid
                cursor = conn.execute(
                    f"""
                    INSERT INTO rules (rule_type, target_id, target_name, is_active, notify_mode, dashboard_mode, user_id)
                    VALUES ({self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph})
                    """,
                    (rule.rule_type, rule.target_id, rule.target_name, rule.is_active, rule.notify_mode, rule.dashboard_mode, user_id),
                )
                return cursor.lastrowid

    def get_rule(self, rule_id: int) -> Optional[Rule]:
        """Get a rule by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM rules WHERE id = {self.ph}", (rule_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_rule(row)

    def get_rule_for_user(self, rule_id: int, user_id: int) -> Optional[Rule]:
        """Get a rule only if it belongs to the specified user.

        Used for ownership verification before mutations.
        Returns None if rule doesn't exist or belongs to different user.
        f"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM rules WHERE id = {self.ph} AND user_id = {self.ph}",
                (rule_id, user_id)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_rule(row)

    def get_active_rules(self, user_id: Optional[int] = None) -> List[Rule]:
        """Get all active rules, optionally filtered by user.

        Args:
            user_id: If provided, filter to rules owned by this user.
                    If None, returns all active rules (for scheduler).
        f"""
        with self.get_connection() as conn:
            if user_id is not None:
                cursor = conn.execute(
                    f"SELECT * FROM rules WHERE is_active = {self._true_val} AND user_id = {self.ph} ORDER BY rule_type, target_name",
                    (user_id,)
                )
            else:
                cursor = conn.execute(
                    f"SELECT * FROM rules WHERE is_active = {self._true_val} ORDER BY rule_type, target_name"
                )
            return [self._row_to_rule(row) for row in cursor.fetchall()]

    def get_all_rules(self, user_id: Optional[int] = None) -> List[Rule]:
        """Get all rules, optionally filtered by user.

        Args:
            user_id: If provided, filter to rules owned by this user.
                    If None, returns all rules (for admin/scheduler).
        f"""
        with self.get_connection() as conn:
            if user_id is not None:
                cursor = conn.execute(
                    f"SELECT * FROM rules WHERE user_id = {self.ph} ORDER BY rule_type, target_name",
                    (user_id,)
                )
            else:
                cursor = conn.execute("SELECT * FROM rules ORDER BY rule_type, target_name")
            return [self._row_to_rule(row) for row in cursor.fetchall()]

    def delete_rule(self, rule_id: int) -> None:
        """Delete a rule."""
        with self.get_connection() as conn:
            conn.execute(f"DELETE FROM rules WHERE id = {self.ph}", (rule_id,))
            conn.execute(f"DELETE FROM notifications WHERE rule_id = {self.ph}", (rule_id,))

    def set_rule_active(self, rule_id: int, is_active: bool) -> None:
        """Set rule active status."""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE rules SET is_active = {self.ph} WHERE id = {self.ph}",
                (is_active, rule_id),
            )

    def set_rule_notify_mode(self, rule_id: int, notify_mode: str) -> None:
        """Set rule notification mode ('all', 'local', 'none')."""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE rules SET notify_mode = {self.ph} WHERE id = {self.ph}",
                (notify_mode, rule_id),
            )

    def set_rule_dashboard_mode(self, rule_id: int, dashboard_mode: str) -> None:
        """Set rule dashboard mode ('all', 'local', 'none')."""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE rules SET dashboard_mode = {self.ph} WHERE id = {self.ph}",
                (dashboard_mode, rule_id),
            )

    def rule_exists(self, rule_type: str, target_id: int, user_id: Optional[int] = None) -> bool:
        """Check if a rule already exists, optionally for a specific user.

        Args:
            rule_type: Type of rule ('artist', 'venue', 'promoter')
            target_id: RA ID of the target
            user_id: If provided, check only for this user's rules.
                    This allows different users to track the same artist.
                    If None, checks globally (for backward compatibility).
        f"""
        with self.get_connection() as conn:
            if user_id is not None:
                cursor = conn.execute(
                    f"SELECT 1 FROM rules WHERE rule_type = {self.ph} AND target_id = {self.ph} AND user_id = {self.ph}",
                    (rule_type, target_id, user_id),
                )
            else:
                cursor = conn.execute(
                    f"SELECT 1 FROM rules WHERE rule_type = {self.ph} AND target_id = {self.ph}",
                    (rule_type, target_id),
                )
            return cursor.fetchone() is not None

    # Event operations
    def upsert_event(self, event: Event, rule_id: Optional[int] = None) -> None:
        """Insert or update an event, optionally linking it to a rule."""
        with self.get_connection() as conn:
            conn.execute(
                f"""
                INSERT INTO events (id, title, date, start_time, end_time, venue_id, venue_name,
                    area_id, area_name, content_url, cost, is_ticketed, is_festival, is_multi_day,
                    attending, interested_count, pick_blurb, set_times_status, set_times_lineup,
                    tickets_json, fetched_at)
                VALUES ({self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph})
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
                if self._use_postgres:
                    conn.execute(
                        f"INSERT INTO event_rules (event_id, rule_id) VALUES ({self.ph}, {self.ph}) ON CONFLICT DO NOTHING",
                        (event.id, rule_id),
                    )
                else:
                    conn.execute(
                        f"INSERT OR IGNORE INTO event_rules (event_id, rule_id) VALUES ({self.ph}, {self.ph})",
                        (event.id, rule_id),
                    )

            # Update artists (now with artist_url)
            conn.execute(f"DELETE FROM event_artists WHERE event_id = {self.ph}", (event.id,))
            for artist_data in event.artists:
                # Handle both old format (id, name) and new format (id, name, url)
                if len(artist_data) >= 3:
                    artist_id, artist_name, artist_url = artist_data[0], artist_data[1], artist_data[2]
                else:
                    artist_id, artist_name = artist_data[0], artist_data[1]
                    artist_url = None
                if self._use_postgres:
                    conn.execute(
                        f"INSERT INTO event_artists (event_id, artist_id, artist_name, artist_url) VALUES ({self.ph}, {self.ph}, {self.ph}, {self.ph}) ON CONFLICT DO NOTHING",
                        (event.id, artist_id, artist_name, artist_url),
                    )
                else:
                    conn.execute(
                        f"INSERT OR IGNORE INTO event_artists (event_id, artist_id, artist_name, artist_url) VALUES ({self.ph}, {self.ph}, {self.ph}, {self.ph})",
                        (event.id, artist_id, artist_name, artist_url),
                    )

            # Update promoters
            conn.execute(f"DELETE FROM event_promoters WHERE event_id = {self.ph}", (event.id,))
            for promoter_id, promoter_name in event.promoters:
                if self._use_postgres:
                    conn.execute(
                        f"INSERT INTO event_promoters (event_id, promoter_id, promoter_name) VALUES ({self.ph}, {self.ph}, {self.ph}) ON CONFLICT DO NOTHING",
                        (event.id, promoter_id, promoter_name),
                    )
                else:
                    conn.execute(
                        f"INSERT OR IGNORE INTO event_promoters (event_id, promoter_id, promoter_name) VALUES ({self.ph}, {self.ph}, {self.ph})",
                        (event.id, promoter_id, promoter_name),
                    )

    def get_event(self, event_id: int) -> Optional[Event]:
        """Get an event by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM events WHERE id = {self.ph}", (event_id,))
            row = cursor.fetchone()
            if row is None:
                return None

            event = Event(
                id=row["id"],
                title=row["title"],
                date=self._parse_date(row["date"]),
                start_time=self._parse_datetime(row["start_time"]),
                end_time=self._parse_datetime(row["end_time"]),
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
                fetched_at=self._parse_datetime(row["fetched_at"]),
            )

            # Get artists (now with artist_url)
            artist_cursor = conn.execute(
                f"SELECT artist_id, artist_name, artist_url FROM event_artists WHERE event_id = {self.ph}",
                (event_id,),
            )
            event.artists = [(r["artist_id"], r["artist_name"], r["artist_url"]) for r in artist_cursor.fetchall()]

            # Get promoters
            promoter_cursor = conn.execute(
                f"SELECT promoter_id, promoter_name FROM event_promoters WHERE event_id = {self.ph}",
                (event_id,),
            )
            event.promoters = [(r["promoter_id"], r["promoter_name"]) for r in promoter_cursor.fetchall()]

            # Get matched rules
            rule_cursor = conn.execute(
                f"""
                SELECT r.* FROM rules r
                JOIN event_rules er ON r.id = er.rule_id
                WHERE er.event_id = {self.ph}
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
                    f"SELECT * FROM events WHERE date >= {self.ph} AND area_id = {self.ph} ORDER BY date, start_time",
                    (today, area_id),
                )
            else:
                cursor = conn.execute(
                    f"SELECT * FROM events WHERE date >= {self.ph} ORDER BY date, start_time",
                    (today,),
                )

            events = []
            for row in cursor.fetchall():
                event = Event(
                    id=row["id"],
                    title=row["title"],
                    date=self._parse_date(row["date"]),
                    start_time=self._parse_datetime(row["start_time"]),
                    end_time=self._parse_datetime(row["end_time"]),
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
                    fetched_at=self._parse_datetime(row["fetched_at"]),
                )

                # Get artists (now with artist_url)
                artist_cursor = conn.execute(
                    f"SELECT artist_id, artist_name, artist_url FROM event_artists WHERE event_id = {self.ph}",
                    (event.id,),
                )
                event.artists = [(r["artist_id"], r["artist_name"], r["artist_url"]) for r in artist_cursor.fetchall()]

                # Get promoters
                promoter_cursor = conn.execute(
                    f"SELECT promoter_id, promoter_name FROM event_promoters WHERE event_id = {self.ph}",
                    (event.id,),
                )
                event.promoters = [(r["promoter_id"], r["promoter_name"]) for r in promoter_cursor.fetchall()]

                # Get matched rules
                rule_cursor = conn.execute(
                    f"""
                    SELECT r.* FROM rules r
                    JOIN event_rules er ON r.id = er.rule_id
                    WHERE er.event_id = {self.ph}
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
            cursor = conn.execute(f"SELECT 1 FROM events WHERE id = {self.ph}", (event_id,))
            return cursor.fetchone() is not None

    def cleanup_past_events(self) -> int:
        """Remove events that have passed. Returns count of deleted events."""
        with self.get_connection() as conn:
            today = date.today().isoformat()
            cursor = conn.execute(f"DELETE FROM events WHERE date < {self.ph}", (today,))
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
    def add_notification(self, event_id: int, rule_id: int, user_id: Optional[int] = None) -> bool:
        """Add a notification record. Returns False if already exists.

        Args:
            event_id: ID of the event
            rule_id: ID of the rule that matched
            user_id: Optional user ID for per-user notification filtering
        f"""
        with self.get_connection() as conn:
            try:
                conn.execute(
                    f"INSERT INTO notifications (event_id, rule_id, user_id) VALUES ({self.ph}, {self.ph}, {self.ph})",
                    (event_id, rule_id, user_id),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def has_notification(self, event_id: int, rule_id: int) -> bool:
        """Check if a notification has been sent."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT 1 FROM notifications WHERE event_id = {self.ph} AND rule_id = {self.ph}",
                (event_id, rule_id),
            )
            return cursor.fetchone() is not None

    def has_event_notification(self, event_id: int) -> bool:
        """Check if any notification has been sent for this event (per-event dedup)."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT 1 FROM notifications WHERE event_id = {self.ph}",
                (event_id,),
            )
            return cursor.fetchone() is not None

    def add_event_notification(self, event_id: int) -> bool:
        """Mark an event as notified (using rule_id=0 for per-event tracking)."""
        with self.get_connection() as conn:
            try:
                conn.execute(
                    f"INSERT INTO notifications (event_id, rule_id) VALUES ({self.ph}, 0)",
                    (event_id,),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def queue_event_for_digest(self, event_id: int, user_id: int) -> bool:
        """Queue an event for the daily digest (digest mode only).

        Inserts a notification record with queued_for_digest=True and no sent_at.
        If a record already exists for this event+user, does nothing (idempotent).

        Returns True if inserted, False if already queued/sent.
        """
        with self.get_connection() as conn:
            try:
                if self._use_postgres:
                    conn.execute(
                        f"""
                        INSERT INTO notifications (event_id, rule_id, user_id, queued_for_digest, sent_at)
                        VALUES ({self.ph}, 0, {self.ph}, {self._true_val}, NULL)
                        ON CONFLICT (event_id, rule_id) DO NOTHING
                        """,
                        (event_id, user_id),
                    )
                else:
                    conn.execute(
                        f"""
                        INSERT OR IGNORE INTO notifications (event_id, rule_id, user_id, queued_for_digest, sent_at)
                        VALUES ({self.ph}, 0, {self.ph}, 1, NULL)
                        """,
                        (event_id, user_id),
                    )
                return True
            except Exception:
                return False

    def get_queued_digest_events(self, user_id: int):
        """Return all event_ids queued for digest for a given user (not yet sent).

        Returns list of event_id integers.
        """
        with self.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT DISTINCT event_id FROM notifications
                WHERE user_id = {self.ph} AND queued_for_digest = {self._true_val} AND sent_at IS NULL
                """,
                (user_id,),
            ).fetchall()
            return [row[0] for row in rows]

    def mark_digest_sent(self, event_ids: list, user_id: int) -> int:
        """Mark digest-queued notifications as sent by setting sent_at = now.

        Returns count of rows updated.
        """
        if not event_ids:
            return 0
        now = datetime.utcnow().isoformat()
        updated = 0
        with self.get_connection() as conn:
            for event_id in event_ids:
                cursor = conn.execute(
                    f"""
                    UPDATE notifications
                    SET sent_at = {self.ph}, queued_for_digest = {self._false_val}
                    WHERE event_id = {self.ph} AND user_id = {self.ph}
                      AND queued_for_digest = {self._true_val} AND sent_at IS NULL
                    """,
                    (now, event_id, user_id),
                )
                updated += cursor.rowcount if hasattr(cursor, 'rowcount') else 0
        return updated

    def get_rules_for_event_and_user(self, event_id: int, user_id: int) -> List[Rule]:
        """Get all rules belonging to a user that matched a given event."""
        with self.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT r.* FROM rules r
                JOIN event_rules er ON er.rule_id = r.id
                WHERE er.event_id = {self.ph} AND r.user_id = {self.ph}
                """,
                (event_id, user_id),
            ).fetchall()
            return [self._row_to_rule(row) for row in rows]

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self.get_connection() as conn:
            rules = conn.execute(f"SELECT COUNT(*) FROM rules WHERE is_active = {self._true_val}").fetchone()[0]
            events = conn.execute(
                f"SELECT COUNT(*) FROM events WHERE date >= {self.ph}",
                (date.today().isoformat(),)
            ).fetchone()[0]
            notifications = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]

            return {
                "active_rules": rules,
                "upcoming_events": events,
                "notifications_sent": notifications,
            }

    def get_upcoming_events_for_user(self, user_id: int, local_area_id: Optional[int] = None) -> List[Event]:
        """Get upcoming events that match the user's rules, filtered by dashboard_mode.

        Returns events linked to the user's rules via the event_rules table.
        Each event includes only the matched_rules belonging to this user.
        Artists and promoters are shared data (not user-scoped).

        Filtering by dashboard_mode:
        - 'all': Always show event
        - 'local': Only show if event.area_id matches local_area_id
        - 'none': Don't show event for this rule

        An event shows if ANY matching rule would show it.

        Args:
            user_id: User ID to get events for
            local_area_id: User's local area ID (for 'local' dashboard_mode filtering)
        """
        with self.get_connection() as conn:
            today = date.today().isoformat()

            # Get events that have at least one rule belonging to this user
            # with dashboard_mode that would show the event
            if local_area_id:
                cursor = conn.execute(
                    f"""
                    SELECT DISTINCT e.* FROM events e
                    INNER JOIN event_rules er ON e.id = er.event_id
                    INNER JOIN rules r ON er.rule_id = r.id
                    WHERE r.user_id = {self.ph} AND e.date >= {self.ph}
                    AND (
                        r.dashboard_mode = 'all'
                        OR (r.dashboard_mode = 'local' AND e.area_id = {self.ph})
                    )
                    ORDER BY e.date, e.start_time
                    """,
                    (user_id, today, local_area_id)
                )
            else:
                # No local area configured - 'local' mode shows nothing
                cursor = conn.execute(
                    f"""
                    SELECT DISTINCT e.* FROM events e
                    INNER JOIN event_rules er ON e.id = er.event_id
                    INNER JOIN rules r ON er.rule_id = r.id
                    WHERE r.user_id = {self.ph} AND e.date >= {self.ph}
                    AND r.dashboard_mode = 'all'
                    ORDER BY e.date, e.start_time
                    """,
                    (user_id, today)
                )

            events = []
            for row in cursor.fetchall():
                event = Event(
                    id=row["id"],
                    title=row["title"],
                    date=self._parse_date(row["date"]),
                    start_time=self._parse_datetime(row["start_time"]),
                    end_time=self._parse_datetime(row["end_time"]),
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
                    fetched_at=self._parse_datetime(row["fetched_at"]),
                )

                # Get artists (shared data, not user-scoped)
                artist_cursor = conn.execute(
                    f"SELECT artist_id, artist_name, artist_url FROM event_artists WHERE event_id = {self.ph}",
                    (event.id,),
                )
                event.artists = [(r["artist_id"], r["artist_name"], r["artist_url"]) for r in artist_cursor.fetchall()]

                # Get promoters (shared data, not user-scoped)
                promoter_cursor = conn.execute(
                    f"SELECT promoter_id, promoter_name FROM event_promoters WHERE event_id = {self.ph}",
                    (event.id,),
                )
                event.promoters = [(r["promoter_id"], r["promoter_name"]) for r in promoter_cursor.fetchall()]

                # Get ONLY this user's matched rules
                rule_cursor = conn.execute(
                    f"""
                    SELECT r.* FROM rules r
                    JOIN event_rules er ON r.id = er.rule_id
                    WHERE er.event_id = {self.ph} AND r.user_id = {self.ph}
                    """,
                    (event.id, user_id),
                )
                event.matched_rules = [self._row_to_rule(r) for r in rule_cursor.fetchall()]

                events.append(event)

            return events

    def get_user_stats(self, user_id: int, local_area_id: int | None = None) -> dict:
        """Get user-scoped statistics.

        Returns:
            dict with keys:
                - active_rules: Count of user's active rules
                - upcoming_events: Count of events matching user's rules (respects dashboard_mode)
                - notifications_sent: Count of notifications for user's rules
        """
        with self.get_connection() as conn:
            today = date.today().isoformat()

            # Active rules for this user
            rules = conn.execute(
                f"SELECT COUNT(*) FROM rules WHERE is_active = {self._true_val} AND user_id = {self.ph}",
                (user_id,)
            ).fetchone()[0]

            # Upcoming events — same dashboard_mode filter as the events list
            if local_area_id:
                events = conn.execute(
                    f"""
                    SELECT COUNT(DISTINCT e.id) FROM events e
                    INNER JOIN event_rules er ON e.id = er.event_id
                    INNER JOIN rules r ON er.rule_id = r.id
                    WHERE r.user_id = {self.ph} AND e.date >= {self.ph}
                    AND (
                        r.dashboard_mode = 'all'
                        OR (r.dashboard_mode = 'local' AND e.area_id = {self.ph})
                    )
                    """,
                    (user_id, today, local_area_id)
                ).fetchone()[0]
            else:
                events = conn.execute(
                    f"""
                    SELECT COUNT(DISTINCT e.id) FROM events e
                    INNER JOIN event_rules er ON e.id = er.event_id
                    INNER JOIN rules r ON er.rule_id = r.id
                    WHERE r.user_id = {self.ph} AND e.date >= {self.ph}
                    AND r.dashboard_mode = 'all'
                    """,
                    (user_id, today)
                ).fetchone()[0]

            # Notifications for user's rules
            notifications = conn.execute(
                f"SELECT COUNT(*) FROM notifications WHERE user_id = {self.ph}",
                (user_id,)
            ).fetchone()[0]

            return {
                "active_rules": rules,
                "upcoming_events": events,
                "notifications_sent": notifications,
            }

    def count_legacy_data(self, user_id: int) -> dict:
        """Count rules and notifications that were migrated to this user.

        Legacy data = records that existed before the user's account was created.
        Used for dashboard welcome message to inform first user about inherited data.

        Returns:
            dict with keys:
                - rules: Count of migrated rules
                - notifications: Count of migrated notifications
        f"""
        with self.get_connection() as conn:
            # Get user's created_at timestamp
            user_row = conn.execute(
                f"SELECT created_at FROM users WHERE id = {self.ph}",
                (user_id,)
            ).fetchone()

            if not user_row or not user_row["created_at"]:
                return {"rules": 0, "notifications": 0}

            user_created_at = user_row["created_at"]

            # Count rules created before user's account
            legacy_rules = conn.execute(
                f"SELECT COUNT(*) FROM rules WHERE user_id = {self.ph} AND created_at < {self.ph}",
                (user_id, user_created_at)
            ).fetchone()[0]

            # Count notifications created before user's account
            legacy_notifications = conn.execute(
                f"SELECT COUNT(*) FROM notifications WHERE user_id = {self.ph} AND sent_at < {self.ph}",
                (user_id, user_created_at)
            ).fetchone()[0]

            return {
                "rules": legacy_rules,
                "notifications": legacy_notifications,
            }

    def get_all_rules_with_users(self) -> List[dict]:
        """Get all rules with owner information for admin view.

        Returns list of dicts (not Rule objects) since we're adding owner info.
        Ordered by owner display_name, then rule_type, then target_name.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT r.*, u.display_name as owner_name, u.email as owner_email
                FROM rules r
                LEFT JOIN users u ON r.user_id = u.id
                ORDER BY u.display_name, r.rule_type, r.target_name
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_users(self) -> List[User]:
        """Get all registered users for admin view.

        Returns all users ordered by created_at DESC (newest first).
        """
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users ORDER BY created_at DESC")
            return [
                User(
                    id=row["id"],
                    email=row["email"],
                    password_hash=row["password_hash"],
                    display_name=row["display_name"],
                    is_admin=bool(row["is_admin"]),
                    email_verified=bool(row["email_verified"]),
                    telegram_chat_id=row["telegram_chat_id"],
                    telegram_enabled=bool(row["telegram_enabled"]) if row["telegram_enabled"] is not None else False,
                    email_enabled=bool(row["email_enabled"]) if row["email_enabled"] is not None else True,
                    local_area_id=row["local_area_id"] if row["local_area_id"] is not None else None,
                    local_area_name=row["local_area_name"] or "",
                    created_at=self._parse_datetime(row["created_at"]),
                    deleted_at=self._parse_datetime(row["deleted_at"]),
                    scheduled_purge_at=self._parse_datetime(row["scheduled_purge_at"]),
                )
                for row in cursor.fetchall()
            ]

    # Audit log operations
    def add_audit_log(
        self,
        event_type: str,
        user_id: Optional[int],
        ip_address: Optional[str],
        details: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
    ) -> int:
        """Add an audit log entry. Returns the log ID.

        Args:
            event_type: Category.action format (e.g., 'auth.login', 'rule.create')
            user_id: User who triggered event (None for anonymous/failed auth)
            ip_address: Client IP address
            details: JSON string with additional context
            target_type: Type of resource affected (e.g., 'rule', 'user')
            target_id: ID of affected resource

        Returns:
            ID of the created audit log entry
        """
        with self.get_connection() as conn:
            if self._use_postgres:
                # PostgreSQL: use RETURNING id
                cursor = conn.execute(
                    f"""
                    INSERT INTO audit_logs (event_type, user_id, ip_address, details, target_type, target_id)
                    VALUES ({self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph})
                    RETURNING id
                    """,
                    (event_type, user_id, ip_address, details, target_type, target_id),
                )
                return cursor.fetchone()["id"]
            else:
                # SQLite: use lastrowid
                cursor = conn.execute(
                    f"""
                    INSERT INTO audit_logs (event_type, user_id, ip_address, details, target_type, target_id)
                    VALUES ({self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph})
                    """,
                    (event_type, user_id, ip_address, details, target_type, target_id),
                )
                return cursor.lastrowid

    def get_audit_logs_filtered(
        self,
        user_search: Optional[str] = None,
        event_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        start_date: Optional[str] = None,  # ISO format YYYY-MM-DD
        end_date: Optional[str] = None,    # ISO format YYYY-MM-DD
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[dict], int]:
        """Query audit logs with filters. Returns (logs, total_count).

        Args:
            user_search: Search by email or display_name (partial match)
            event_type: Filter by event type (prefix match)
            ip_address: Filter by IP address (prefix match)
            start_date: Filter by date >= start_date (ISO format YYYY-MM-DD)
            end_date: Filter by date <= end_date (ISO format YYYY-MM-DD)
            limit: Maximum number of results (default 50)
            offset: Number of results to skip (default 0)

        Returns:
            Tuple of (logs list, total count for pagination)
        f"""
        with self.get_connection() as conn:
            # Build query dynamically
            where_clauses = ["1=1"]
            params = []

            if user_search:
                # Search by email or display_name (join with users table)
                where_clauses.append(f"(u.email LIKE {self.ph} OR u.display_name LIKE {self.ph})")
                params.extend([f"%{user_search}%", f"%{user_search}%"])

            if event_type:
                where_clauses.append(f"al.event_type LIKE {self.ph}")
                params.append(f"{event_type}%")

            if ip_address:
                where_clauses.append(f"al.ip_address LIKE {self.ph}")
                params.append(f"{ip_address}%")

            if start_date:
                where_clauses.append(f"DATE(al.timestamp) >= {self.ph}")
                params.append(start_date)

            if end_date:
                where_clauses.append(f"DATE(al.timestamp) <= {self.ph}")
                params.append(end_date)

            where_sql = " AND ".join(where_clauses)

            # Count total
            count = conn.execute(
                f"""SELECT COUNT(*) FROM audit_logs al
                    LEFT JOIN users u ON al.user_id = u.id
                    WHERE {where_sql}""",
                params
            ).fetchone()[0]

            # Fetch page with user info
            query = f"""
                SELECT al.*, u.email as user_email, u.display_name as user_display_name
                FROM audit_logs al
                LEFT JOIN users u ON al.user_id = u.id
                WHERE {where_sql}
                ORDER BY al.timestamp DESC
                LIMIT {self.ph} OFFSET {self.ph}
            """
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            logs = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # Parse JSON details for each log
            for log in logs:
                if log.get('details'):
                    try:
                        log['details'] = json.loads(log['details'])
                    except (json.JSONDecodeError, TypeError):
                        pass

            return logs, count

    def get_distinct_event_types(self) -> List[str]:
        """Get list of distinct event types for filter dropdown."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT event_type FROM audit_logs ORDER BY event_type"
            )
            return [row[0] for row in cursor.fetchall()]

    def get_audit_logs(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        """Query audit logs with optional filters.

        Args:
            event_type: Filter by event type (exact match)
            user_id: Filter by user ID
            limit: Maximum number of results (default 100)
            offset: Number of results to skip (default 0)

        Returns:
            List of audit log entries as dicts, ordered by timestamp DESC
        f"""
        with self.get_connection() as conn:
            query = "SELECT * FROM audit_logs WHERE 1=1"
            params = []

            if event_type is not None:
                query += f" AND event_type = {self.ph}"
                params.append(event_type)

            if user_id is not None:
                query += f" AND user_id = {self.ph}"
                params.append(user_id)

            query += f" ORDER BY timestamp DESC LIMIT {self.ph} OFFSET {self.ph}"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # Scraper health log operations
    def log_scraper_error(
        self,
        status_code: Optional[int],
        error_message: str,
        error_type: str,
        circuit_breaker_state: str,
        rule_target: Optional[str] = None
    ) -> None:
        """Log a scraper error to the health log.

        Args:
            status_code: HTTP status code (e.g., 403, 429, 500), None for non-HTTP errors
            error_message: Error description
            error_type: Error category ('HTTP', 'EXCEPTION', etc.)
            circuit_breaker_state: Current circuit breaker state ('CLOSED', 'OPEN', 'HALF_OPEN')
            rule_target: Name of the rule target being fetched (optional)
        """
        with self.get_connection() as conn:
            conn.execute(
                f"""INSERT INTO scraper_health_log
                   (status_code, error_message, error_type, circuit_breaker_state, rule_target)
                   VALUES ({self.ph}, {self.ph}, {self.ph}, {self.ph}, {self.ph})""",
                (status_code, error_message, error_type, circuit_breaker_state, rule_target)
            )

    def get_recent_scraper_errors(self, limit: int = 10) -> List[dict]:
        """Get recent scraper errors from health log.

        Args:
            limit: Maximum number of errors to return (default 10)

        Returns:
            List of error records as dicts with keys: id, timestamp, status_code,
            error_message, error_type, circuit_breaker_state, rule_target
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM scraper_health_log ORDER BY timestamp DESC LIMIT {self.ph}",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_scraper_logs(self, days: int = 30) -> int:
        """Delete scraper health log entries older than specified days.

        Args:
            days: Delete logs older than this many days (default 30)

        Returns:
            Number of rows deleted
        """
        from datetime import timedelta

        with self.get_connection() as conn:
            cutoff = datetime.now() - timedelta(days=days)
            cursor = conn.execute(
                f"DELETE FROM scraper_health_log WHERE timestamp < {self.ph}",
                (cutoff,)
            )
            deleted = cursor.rowcount
            logger.info(f"Cleaned up {deleted} old scraper health log entries (older than {days} days)")
            return deleted

    # Scraper fetch log operations
    def start_scraper_fetch(self) -> int:
        """Record the start of a scraper fetch cycle.

        Returns:
            The inserted row ID (fetch_id), used to update the row on completion.
        """
        started_at = datetime.utcnow()
        with self.get_connection() as conn:
            if self._use_postgres:
                cursor = conn.execute(
                    f"""INSERT INTO scraper_fetch_log (started_at, status)
                        VALUES ({self.ph}, {self.ph})
                        RETURNING id""",
                    (started_at, 'RUNNING')
                )
                return cursor.fetchone()["id"]
            else:
                cursor = conn.execute(
                    f"""INSERT INTO scraper_fetch_log (started_at, status)
                        VALUES ({self.ph}, {self.ph})""",
                    (started_at, 'RUNNING')
                )
                return cursor.lastrowid

    def complete_scraper_fetch(
        self,
        fetch_id: int,
        events_found: int,
        rules_processed: int,
        status: str,
        error_message: Optional[str] = None,
        circuit_breaker_state: Optional[str] = None
    ) -> None:
        """Record the completion of a scraper fetch cycle.

        Args:
            fetch_id: Row ID returned by start_scraper_fetch()
            events_found: Number of events fetched
            rules_processed: Number of rules processed
            status: 'SUCCESS', 'FAILURE', or 'SKIPPED'
            error_message: Error description if status is FAILURE (optional)
            circuit_breaker_state: Circuit breaker state string (optional, from caller)
        """
        completed_at = datetime.utcnow()
        cb_state = circuit_breaker_state

        # Calculate duration from stored started_at
        duration_seconds = None
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT started_at FROM scraper_fetch_log WHERE id = {self.ph}",
                (fetch_id,)
            )
            row = cursor.fetchone()
            if row:
                started_at = self._parse_datetime(row["started_at"])
                if started_at:
                    duration_seconds = (completed_at - started_at).total_seconds()

            conn.execute(
                f"""UPDATE scraper_fetch_log
                    SET completed_at = {self.ph},
                        duration_seconds = {self.ph},
                        events_found = {self.ph},
                        rules_processed = {self.ph},
                        status = {self.ph},
                        error_message = {self.ph},
                        circuit_breaker_state = {self.ph}
                    WHERE id = {self.ph}""",
                (completed_at, duration_seconds, events_found, rules_processed,
                 status, error_message, cb_state, fetch_id)
            )

    def get_scraper_health_summary(self, days: int = 7) -> dict:
        """Get aggregate scraper health stats over the last N days.

        Args:
            days: Number of days to look back (default 7)

        Returns:
            Dict with keys: total_fetches, successful, failed, avg_duration_seconds,
            total_events_found, last_successful_fetch (datetime or None)
        """
        with self.get_connection() as conn:
            if self._use_postgres:
                date_filter = f"started_at > NOW() - INTERVAL '{days} days'"
            else:
                date_filter = f"started_at > datetime('now', '-{days} days')"

            cursor = conn.execute(
                f"""SELECT
                        COUNT(*) as total_fetches,
                        SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN status = 'FAILURE' THEN 1 ELSE 0 END) as failed,
                        AVG(duration_seconds) as avg_duration_seconds,
                        SUM(events_found) as total_events_found,
                        MAX(CASE WHEN status = 'SUCCESS' THEN started_at ELSE NULL END) as last_successful_fetch
                    FROM scraper_fetch_log
                    WHERE {date_filter}"""
            )
            row = cursor.fetchone()
            if row is None:
                return {
                    "total_fetches": 0,
                    "successful": 0,
                    "failed": 0,
                    "avg_duration_seconds": None,
                    "total_events_found": 0,
                    "last_successful_fetch": None,
                }

            return {
                "total_fetches": row["total_fetches"] or 0,
                "successful": row["successful"] or 0,
                "failed": row["failed"] or 0,
                "avg_duration_seconds": row["avg_duration_seconds"],
                "total_events_found": row["total_events_found"] or 0,
                "last_successful_fetch": self._parse_datetime(row["last_successful_fetch"]),
            }

    def get_recent_fetch_history(self, limit: int = 20) -> list:
        """Get recent fetch cycles ordered by most recent first.

        Args:
            limit: Maximum number of records to return (default 20)

        Returns:
            List of dicts with keys: id, started_at, completed_at, duration_seconds,
            events_found, rules_processed, status, error_message, circuit_breaker_state
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM scraper_fetch_log ORDER BY started_at DESC LIMIT {self.ph}",
                (limit,)
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                r = dict(row)
                r["started_at"] = self._parse_datetime(r["started_at"])
                r["completed_at"] = self._parse_datetime(r["completed_at"])
                result.append(r)
            return result

    def get_fetch_success_rate_trend(self, days: int = 7) -> list:
        """Get daily success rate over last N days.

        Args:
            days: Number of days to look back (default 7)

        Returns:
            List of dicts: [{date, total, successful, success_rate}], ordered by date ASC
        """
        with self.get_connection() as conn:
            if self._use_postgres:
                date_filter = f"started_at > NOW() - INTERVAL '{days} days'"
            else:
                date_filter = f"started_at > datetime('now', '-{days} days')"

            cursor = conn.execute(
                f"""SELECT
                        DATE(started_at) as date,
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful
                    FROM scraper_fetch_log
                    WHERE {date_filter}
                    GROUP BY DATE(started_at)
                    ORDER BY DATE(started_at) ASC"""
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                total = row["total"] or 0
                successful = row["successful"] or 0
                success_rate = (successful / total * 100) if total > 0 else 0
                result.append({
                    "date": row["date"],
                    "total": total,
                    "successful": successful,
                    "success_rate": success_rate,
                })
            return result

    def get_scraper_alert_state(self) -> dict:
        """Get the singleton scraper alert state row.

        Returns:
            Dict with keys: alert_sent (bool), alert_sent_at (datetime|None),
            consecutive_failures (int), last_alert_message (str|None)
        """
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM scraper_alert_state WHERE id = 1")
            row = cursor.fetchone()
            if row is None:
                return {
                    "alert_sent": False,
                    "alert_sent_at": None,
                    "consecutive_failures": 0,
                    "last_alert_message": None,
                }
            return {
                "alert_sent": bool(row["alert_sent"]),
                "alert_sent_at": self._parse_datetime(row["alert_sent_at"]),
                "consecutive_failures": row["consecutive_failures"] or 0,
                "last_alert_message": row["last_alert_message"],
            }

    def set_scraper_alert_sent(self, sent: bool, message: str = None) -> None:
        """Update alert_sent flag and related fields.

        Args:
            sent: True when alert was just sent, False on recovery
            message: Optional message describing the alert
        """
        with self.get_connection() as conn:
            if sent:
                conn.execute(
                    f"""UPDATE scraper_alert_state
                        SET alert_sent = {self.ph},
                            alert_sent_at = CURRENT_TIMESTAMP,
                            last_alert_message = {self.ph}
                        WHERE id = 1""",
                    (True if self._use_postgres else 1, message)
                )
            else:
                # Recovery: clear alert_sent_at
                conn.execute(
                    f"""UPDATE scraper_alert_state
                        SET alert_sent = {self.ph},
                            alert_sent_at = NULL,
                            last_alert_message = {self.ph}
                        WHERE id = 1""",
                    (False if self._use_postgres else 0, message)
                )

    def update_consecutive_failures(self, count: int) -> None:
        """Set the consecutive failure count.

        Args:
            count: New consecutive failure count
        """
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE scraper_alert_state SET consecutive_failures = {self.ph} WHERE id = 1",
                (count,)
            )

    def reset_consecutive_failures(self) -> None:
        """Reset consecutive failure count to 0."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE scraper_alert_state SET consecutive_failures = 0 WHERE id = 1"
            )

    def cleanup_old_fetch_logs(self, days: int = 30) -> int:
        """Delete scraper_fetch_log entries older than specified days.

        Args:
            days: Delete logs older than this many days (default 30)

        Returns:
            Number of rows deleted
        """
        from datetime import timedelta

        with self.get_connection() as conn:
            cutoff = datetime.utcnow() - timedelta(days=days)
            cursor = conn.execute(
                f"DELETE FROM scraper_fetch_log WHERE started_at < {self.ph}",
                (cutoff,)
            )
            deleted = cursor.rowcount
            logger.info(f"Cleaned up {deleted} old scraper fetch log entries (older than {days} days)")
            return deleted


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
