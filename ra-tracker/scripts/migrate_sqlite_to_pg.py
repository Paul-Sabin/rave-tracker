#!/usr/bin/env python3
"""Migrate RA Tracker data from SQLite to PostgreSQL.

Usage:
    python scripts/migrate_sqlite_to_pg.py --sqlite data/ra_tracker.db --pg-url postgresql://user:pass@host/db

This is a one-time migration script for transitioning from SQLite to PostgreSQL.
Run reset_sequences.sql after migration if running separately.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 is required. Install with: pip install psycopg2")
    sys.exit(1)

# Add ra-tracker to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# PostgreSQL schema (embedded for self-contained script)
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
"""

# Sequence reset SQL (embedded)
SEQUENCE_RESET_SQL = """
SELECT setval('rules_id_seq', COALESCE((SELECT MAX(id) FROM rules), 1));
SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1));
SELECT setval('notifications_id_seq', COALESCE((SELECT MAX(id) FROM notifications), 1));
SELECT setval('audit_logs_id_seq', COALESCE((SELECT MAX(id) FROM audit_logs), 1));
"""

# Boolean column mappings (columns that need int->bool conversion)
BOOLEAN_COLUMNS = {
    'rules': ['is_active'],
    'events': ['is_ticketed', 'is_festival', 'is_multi_day'],
    'users': ['is_admin', 'email_verified', 'telegram_enabled', 'email_enabled'],
}

# Table migration order (FK-safe)
TABLE_ORDER = [
    'users',  # No FKs
    'rules',  # References users but user_id is nullable
    'events',  # No FKs to other tables
    'event_artists',  # References events
    'event_promoters',  # References events
    'event_rules',  # References events, rules
    'notifications',  # References events, rules, users
    'sessions',  # References users
    'telegram_link_codes',  # References users
    'audit_logs',  # References users loosely
]


def convert_row_booleans(table_name, row_dict):
    """Convert INTEGER boolean values (0/1) to Python bool for specified columns."""
    if table_name in BOOLEAN_COLUMNS:
        for col in BOOLEAN_COLUMNS[table_name]:
            if col in row_dict and row_dict[col] is not None:
                row_dict[col] = bool(row_dict[col])
    return row_dict


def migrate_table(sqlite_conn, pg_conn, table_name, dry_run=False, verbose=False):
    """Migrate a single table from SQLite to PostgreSQL.

    Args:
        sqlite_conn: SQLite connection
        pg_conn: PostgreSQL connection
        table_name: Name of table to migrate
        dry_run: If True, only show what would be migrated
        verbose: If True, log each row

    Returns:
        Number of rows migrated
    """
    if verbose:
        print(f"  Migrating table: {table_name}")

    # Get all rows from SQLite
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    if len(rows) == 0:
        if verbose:
            print(f"    No data in {table_name}")
        return 0

    # Get column names
    columns = rows[0].keys()

    if dry_run:
        print(f"    Would migrate {len(rows)} rows from {table_name}")
        if verbose and len(rows) > 0:
            sample = dict(rows[0])
            print(f"    Sample row: {sample}")
        return len(rows)

    # Insert into PostgreSQL
    pg_cursor = pg_conn.cursor()
    migrated = 0

    for row in rows:
        row_dict = dict(row)

        # Convert boolean columns
        row_dict = convert_row_booleans(table_name, row_dict)

        # Build INSERT statement
        placeholders = ', '.join(['%s'] * len(columns))
        cols = ', '.join(columns)
        insert_sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"

        values = tuple(row_dict[col] for col in columns)

        try:
            pg_cursor.execute(insert_sql, values)
            migrated += 1
            if verbose and migrated % 100 == 0:
                print(f"    Migrated {migrated}/{len(rows)} rows...")
        except Exception as e:
            print(f"    ERROR on row {migrated + 1}: {e}")
            print(f"    Row data: {row_dict}")
            raise

    if verbose:
        print(f"    Successfully migrated {migrated} rows from {table_name}")

    return migrated


def main():
    parser = argparse.ArgumentParser(
        description="Migrate RA Tracker data from SQLite to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/migrate_sqlite_to_pg.py --sqlite data/ra_tracker.db --pg-url postgresql://user:pass@localhost/db
  python scripts/migrate_sqlite_to_pg.py --sqlite data/ra_tracker.db --pg-url postgresql://user:pass@localhost/db --drop-existing
  python scripts/migrate_sqlite_to_pg.py --sqlite data/ra_tracker.db --pg-url postgresql://user:pass@localhost/db --dry-run --verbose
        """
    )

    parser.add_argument('--sqlite', required=True, help='Path to SQLite database file')
    parser.add_argument('--pg-url', required=True, help='PostgreSQL connection URL')
    parser.add_argument('--drop-existing', action='store_true',
                        help='Drop and recreate PostgreSQL tables before migration')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be migrated without writing to PostgreSQL')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed progress for each table and row')

    args = parser.parse_args()

    # Validate SQLite file exists
    if not Path(args.sqlite).exists():
        print(f"ERROR: SQLite database not found: {args.sqlite}")
        sys.exit(1)

    print(f"Starting migration:")
    print(f"  Source: {args.sqlite}")
    print(f"  Target: {args.pg_url}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    # Connect to SQLite
    try:
        sqlite_conn = sqlite3.connect(args.sqlite)
        print("[OK] Connected to SQLite")
    except Exception as e:
        print(f"ERROR: Failed to connect to SQLite: {e}")
        sys.exit(1)

    # Connect to PostgreSQL
    try:
        pg_conn = psycopg2.connect(args.pg_url)
        print("[OK] Connected to PostgreSQL")
    except Exception as e:
        print(f"ERROR: Failed to connect to PostgreSQL: {e}")
        print("  Make sure the database exists and credentials are correct")
        sys.exit(1)

    try:
        pg_cursor = pg_conn.cursor()

        # Drop existing tables if requested
        if args.drop_existing and not args.dry_run:
            print("\nDropping existing tables...")
            for table in reversed(TABLE_ORDER):  # Reverse order for FK constraints
                try:
                    pg_cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                    if args.verbose:
                        print(f"  Dropped {table}")
                except Exception as e:
                    print(f"  Warning: Could not drop {table}: {e}")
            pg_conn.commit()
            print("[OK] Dropped existing tables")

        # Create PostgreSQL schema
        if not args.dry_run:
            print("\nCreating PostgreSQL schema...")
            for statement in PG_SCHEMA.split(';'):
                statement = statement.strip()
                if statement:
                    pg_cursor.execute(statement)
            pg_conn.commit()
            print("[OK] Schema created")
        else:
            print("\n[DRY RUN] Would create PostgreSQL schema")

        # Migrate tables
        print("\nMigrating tables:")
        total_rows = 0

        for table in TABLE_ORDER:
            try:
                row_count = migrate_table(
                    sqlite_conn,
                    pg_conn,
                    table,
                    dry_run=args.dry_run,
                    verbose=args.verbose
                )
                total_rows += row_count

                if not args.verbose:
                    print(f"  {table}: {row_count} rows")

            except sqlite3.OperationalError as e:
                if "no such table" in str(e):
                    print(f"  {table}: Table not found in SQLite (skipping)")
                else:
                    raise
            except Exception as e:
                print(f"\nERROR: Migration failed on table {table}: {e}")
                pg_conn.rollback()
                sys.exit(1)

        if not args.dry_run:
            pg_conn.commit()

        print(f"\n[OK] Migrated {total_rows} total rows across {len(TABLE_ORDER)} tables")

        # Reset sequences
        if not args.dry_run:
            print("\nResetting SERIAL sequences...")
            for statement in SEQUENCE_RESET_SQL.strip().split(';'):
                statement = statement.strip()
                if statement:
                    pg_cursor.execute(statement)
                    result = pg_cursor.fetchone()
                    if args.verbose and result:
                        print(f"  {result[0]}")
            pg_conn.commit()
            print("[OK] Sequences reset")
        else:
            print("\n[DRY RUN] Would reset SERIAL sequences")

        # Verify
        if not args.dry_run:
            print("\nVerifying migration:")
            for table in TABLE_ORDER:
                pg_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                pg_count = pg_cursor.fetchone()[0]

                sqlite_cursor = sqlite_conn.cursor()
                try:
                    sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    sqlite_count = sqlite_cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    sqlite_count = 0  # Table doesn't exist in SQLite

                status = "[OK]" if pg_count == sqlite_count else "[FAIL]"
                print(f"  {status} {table}: SQLite={sqlite_count}, PostgreSQL={pg_count}")

        print("\n[OK] Migration complete!")

        if args.dry_run:
            print("\nThis was a dry run. No data was written to PostgreSQL.")
            print("Run without --dry-run to perform the actual migration.")

    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == '__main__':
    main()
