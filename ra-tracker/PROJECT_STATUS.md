# RA Tracker - Project Status

## Milestone 1: Single-User Local App (Complete)
**Date:** 2026-01-18

### What It Does

RA Tracker monitors Resident Advisor (ra.co) for events matching your tracked artists, venues, and promoters. It:
- Fetches event data via RA's GraphQL API on a configurable schedule
- Stores events in a local SQLite database
- Provides a web dashboard to browse upcoming events
- Sends Telegram notifications for new events (with per-rule notification preferences)

### Current Features

1. **Rule-based tracking**
   - Track artists, venues, or promoters by searching RA
   - Enable/disable rules without deleting them
   - Right-click artists on dashboard to add them as new rules

2. **Event data**
   - Full event details: title, date, time, venue, area, cost, lineup
   - Artist names link to their RA profiles
   - Badges for festivals, multi-day events, ticketed events
   - Attendance/interest counts ("peeps")
   - Expandable view with RA editor picks, set times, ticket info

3. **Dashboard filtering**
   - Filter by location: All Areas / Local only (Berlin)
   - Filter by rule type: Artists / Venues / Promoters

4. **Notifications (Telegram)**
   - Per-event deduplication (each event notified only once)
   - Per-rule notification modes:
     - Artists: All / Local / Off
     - Venues & Promoters: On / Off
   - Default is "Local" (only notify for events in configured local area)

5. **Scheduler**
   - Configurable fetch interval (default: every 6 hours)
   - Manual fetch trigger from dashboard
   - Event horizon setting (how far ahead to look, default: 100 days)

### Architecture

```
ra-tracker/
├── ra_tracker/
│   ├── __init__.py
│   ├── main.py              # Entry point (FastAPI + scheduler)
│   ├── config.py            # YAML config management
│   ├── database.py          # SQLite ORM, schema, migrations
│   ├── api/
│   │   └── ra_client.py     # GraphQL client for ra.co
│   ├── services/
│   │   ├── fetcher.py       # Fetches events for rules
│   │   ├── matcher.py       # Matches events to rules
│   │   └── notifier.py      # Telegram notifications
│   ├── scheduler/
│   │   └── jobs.py          # Background fetch scheduling
│   └── web/
│       ├── routes.py        # FastAPI routes
│       └── templates/       # Jinja2 HTML templates
│           ├── base.html
│           ├── dashboard.html
│           ├── rules.html
│           └── settings.html
├── data/
│   └── ra_tracker.db        # SQLite database (created on first run)
├── config.yaml              # User configuration
├── requirements.txt         # Python dependencies
└── PROJECT_STATUS.md        # This file
```

### Database Schema

```sql
-- Tracking rules
rules (
    id INTEGER PRIMARY KEY,
    rule_type TEXT,           -- 'artist', 'venue', 'promoter'
    target_id INTEGER,        -- RA ID
    target_name TEXT,         -- Display name
    is_active BOOLEAN,
    notify_mode TEXT,         -- 'all', 'local', 'none' (default: 'local')
    created_at DATETIME
)

-- Cached events
events (
    id INTEGER PRIMARY KEY,   -- RA event ID
    title TEXT,
    date DATE,
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
    set_times_lineup TEXT,    -- JSON
    tickets_json TEXT,        -- JSON
    fetched_at DATETIME
)

-- Event-to-rule mapping
event_rules (event_id, rule_id)

-- Event artists (with RA profile URLs)
event_artists (event_id, artist_id, artist_name, artist_url)

-- Event promoters
event_promoters (event_id, promoter_id, promoter_name)

-- Notification tracking (per-event deduplication)
notifications (id, event_id, rule_id, sent_at)
```

### Configuration (config.yaml)

```yaml
database:
  path: ./data/ra_tracker.db

scheduler:
  event_horizon_days: 100    # How far ahead to fetch
  fetch_interval_hours: 6    # How often to fetch

telegram:
  bot_token: "your-bot-token"
  chat_id: "your-chat-id"    # Numeric ID, not username

user:
  local_area_id: 34          # RA area ID (34 = Berlin)
  local_area_name: Berlin

web:
  host: 0.0.0.0
  port: 8080
```

### How to Run

```bash
cd ra-tracker

# Install dependencies (first time)
pip install -r requirements.txt

# Start web server with scheduler
python -m ra_tracker.main

# Start without scheduler (no background fetching)
python -m ra_tracker.main --no-scheduler

# Run a single fetch and exit
python -m ra_tracker.main --fetch-only
```

Web UI: `http://127.0.0.1:8080`

### Dependencies

- **FastAPI** + **Uvicorn**: Web framework and server
- **Jinja2**: HTML templating
- **APScheduler**: Background job scheduling
- **python-telegram-bot**: Telegram API client
- **PyYAML**: Config file parsing
- **httpx**: HTTP client for RA API

### Current Limitations (Single-User)

1. **Single configuration** - One config.yaml, one set of preferences
2. **Shared rules** - All rules visible to anyone accessing the web UI
3. **Single Telegram destination** - Notifications go to one chat
4. **No authentication** - Anyone with the URL can access/modify rules
5. **Local database** - SQLite file on disk, not suitable for multi-instance

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | / | Dashboard |
| GET | /rules | Rules management page |
| POST | /rules/add | Add rule (form) |
| POST | /rules/{id}/toggle | Toggle rule active status |
| POST | /rules/{id}/notify-mode | Set notification mode |
| POST | /rules/{id}/delete | Delete rule |
| GET | /settings | Settings page |
| POST | /settings/save | Save settings |
| POST | /settings/test-telegram | Test Telegram config |
| POST | /actions/fetch-now | Trigger manual fetch |
| GET | /api/search/artists | Search RA for artists |
| GET | /api/search/venues | Search RA for venues |
| GET | /api/search/promoters | Search RA for promoters |
| GET | /api/search/areas | Search RA for areas |
| GET | /api/status | Get system status |
| POST | /api/rules/add | Add rule (JSON API) |
| GET | /api/rules/check | Check if rule exists |

---

## Next Milestone: Multi-User Support

**Goal:** Allow friends to use the app with their own rules and notification preferences.

### Requirements to Consider

1. **User accounts & authentication**
   - Login/registration system
   - Session management

2. **Per-user data**
   - Each user has their own rules
   - Each user has their own Telegram config
   - Shared event cache (events are fetched once, visible to all)

3. **Deployment**
   - Cloud hosting (Railway, Render, Fly.io, or VPS)
   - Persistent database (PostgreSQL or managed SQLite)
   - Environment-based configuration (secrets not in files)

4. **Security**
   - Password hashing
   - HTTPS (handled by hosting platform)
   - Rate limiting on API endpoints

### Possible Architecture Changes

- Add `users` table with authentication
- Add `user_id` foreign key to `rules` table
- Add `user_telegram_config` table (per-user bot token/chat ID, or shared bot with per-user chat ID)
- Move from config.yaml to database-stored settings
- Add login/logout routes and session middleware
