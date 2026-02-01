# Architecture

**Analysis Date:** 2026-02-01

## Pattern Overview

**Overall:** Layered Service Architecture with Scheduled Background Jobs

**Key Characteristics:**
- Clear separation between API client, business services, web UI, and scheduler
- Global singleton pattern for configuration and database access
- Dataclass-based domain models shared across layers
- GraphQL-based external API integration with rate limiting
- Background scheduler for periodic event fetching with foreground web server

## Layers

**API Layer:**
- Purpose: External API communication with ra.co GraphQL endpoint
- Location: `ra-tracker/ra_tracker/api/`
- Contains: GraphQL client, response parsing, data transfer objects
- Depends on: `requests` library
- Used by: Services layer (fetcher)

**Services Layer:**
- Purpose: Business logic orchestration - fetching, matching, notifying
- Location: `ra-tracker/ra_tracker/services/`
- Contains: Fetcher (event retrieval), Matcher (rule evaluation), Notifier (Telegram integration)
- Depends on: API layer, Database layer, Config
- Used by: Scheduler jobs, Web routes

**Web Layer:**
- Purpose: HTTP API and HTML dashboard for user interaction
- Location: `ra-tracker/ra_tracker/web/`
- Contains: FastAPI app, routes, Jinja2 templates
- Depends on: Services layer, Database layer, Scheduler
- Used by: End users via browser

**Scheduler Layer:**
- Purpose: Background job execution for periodic event fetching
- Location: `ra-tracker/ra_tracker/scheduler/`
- Contains: APScheduler configuration, fetch_and_notify job
- Depends on: Services layer (Fetcher, Notifier), Database
- Used by: Main entry point, runs concurrently with web server

**Database Layer:**
- Purpose: SQLite persistence with domain models
- Location: `ra-tracker/ra_tracker/database.py`
- Contains: Schema definition, migrations, CRUD operations, dataclasses (Rule, Event, User, Session)
- Depends on: Config (for db path)
- Used by: All other layers

**Configuration Layer:**
- Purpose: YAML file and environment variable configuration
- Location: `ra-tracker/ra_tracker/config.py`
- Contains: Dataclass configs (Telegram, Scheduler, Web, Database, User)
- Depends on: PyYAML
- Used by: All other layers

## Database Schema

**Rules Table (`rules`):**
- Purpose: Tracking configuration for artist, venue, or promoter
- Key columns:
  - `id`: Primary key
  - `rule_type`: 'artist', 'venue', 'promoter'
  - `target_id`: RA ID of the entity
  - `target_name`: Display name
  - `user_id`: Owner of this rule (nullable for legacy data)
  - `notify_mode`: 'all', 'local', 'none' - controls which events trigger notifications
  - `dashboard_mode`: 'all', 'local', 'none' - controls which events appear on dashboard
  - `is_active`: Deprecated flag (use modes set to 'none' instead)

**Mode System (notify_mode and dashboard_mode):**
- `'all'`: Apply to all events matching this rule
- `'local'`: Apply only to events in user's local area (filtered by `area_id`)
- `'none'`: Disable this feature for this rule
- Both modes work independently: a rule can notify globally but only show local events on dashboard

**Events Table (`events`):**
- Purpose: Cached event data from ra.co
- Key columns: `id` (RA event ID), `title`, `date`, `venue_id`, `area_id`, `area_name`
- Related tables: `event_artists`, `event_promoters`, `event_rules` (many-to-many)

**Users Table (`users`):**
- Purpose: Multi-tenant user accounts
- Key columns: `id`, `email`, `password_hash`, `telegram_chat_id`, `telegram_enabled`, `email_enabled`

**Notifications Table (`notifications`):**
- Purpose: Track sent notifications to prevent duplicates
- Key columns: `event_id`, `rule_id`, `user_id`

## Data Flow

**Scheduled Fetch Flow:**

1. APScheduler triggers `fetch_and_notify()` at configured interval
2. `Fetcher` loads active rules from Database
3. For each rule, `RAClient` queries ra.co GraphQL API
4. Events are converted from `RAEvent` to `Event` dataclass and upserted to database
5. New events (not previously notified) are identified per-event deduplication
6. `Notifier` sends Telegram summary for new events matching notify_mode
7. Notification records stored to prevent duplicates

**Web Dashboard Flow:**

1. User accesses `/` route in browser
2. `routes.py` calls `get_upcoming_events_for_user(user_id, local_area_id)`
3. Query filters events by:
   - Rules belonging to user
   - Dashboard mode: 'all' shows all, 'local' shows only matching `area_id`, 'none' excludes
4. Events grouped by date, rendered via Jinja2 template
5. Client-side JavaScript handles filtering and interactions

**Rule Management Flow:**

1. User searches ra.co via `/api/search/{type}` endpoints
2. `RAClient.search_*` methods query GraphQL search API
3. User adds rule via POST to `/rules/add` or `/api/rules/add`
4. `Database.add_rule()` persists rule with notify_mode and dashboard_mode settings
5. Next fetch cycle picks up new rule and fetches matching events

**Rule Mode Update Flow:**

1. User clicks mode toggle on rules page (cycles through all/local/none)
2. AJAX POST to `/rules/{rule_id}/notify-mode` or `/rules/{rule_id}/dashboard-mode`
3. Route verifies user ownership via `get_rule_for_user()`
4. `Database.set_rule_notify_mode()` or `set_rule_dashboard_mode()` updates column
5. Returns JSON success, UI updates without page reload

**State Management:**
- Global singletons for Config (`_config`) and Database (`_db`)
- Accessed via `get_config()` and `get_db()` functions
- Initialized in `main.py` via `set_config()` and `set_db()`
- Scheduler state tracked via module-level `_scheduler` and `_last_fetch_time`

## Key Abstractions

**Rule:**
- Purpose: Tracking configuration for artist/venue/promoter with dual-mode filtering
- Examples: `ra-tracker/ra_tracker/database.py` lines 225-236
- Pattern: Dataclass with rule_type discriminator ('artist', 'venue', 'promoter')
- Fields: `notify_mode` (notification filtering), `dashboard_mode` (dashboard visibility)

**Event:**
- Purpose: Cached event data from ra.co with relationship data
- Examples: `ra-tracker/ra_tracker/database.py` lines 239-273
- Pattern: Dataclass with optional fields, post_init for list initialization

**RAEvent:**
- Purpose: API response transfer object before database conversion
- Examples: `ra-tracker/ra_tracker/api/ra_client.py` lines 18-48
- Pattern: Mirrors Event but used for API boundary

**RAClient:**
- Purpose: GraphQL client with rate limiting and error handling
- Examples: `ra-tracker/ra_tracker/api/ra_client.py` lines 78-593
- Pattern: Session-based HTTP client with typed methods per entity type

## Entry Points

**CLI Entry (`main.py`):**
- Location: `ra-tracker/ra_tracker/main.py`
- Triggers: `python -m ra_tracker` or direct execution
- Responsibilities: Parse args, init config/database, start scheduler, run uvicorn

**Web App (`app.py`):**
- Location: `ra-tracker/ra_tracker/web/app.py`
- Triggers: Imported by uvicorn via `ra_tracker.web.app:app`
- Responsibilities: FastAPI app factory, template setup, router inclusion

**Fetch Job (`jobs.py`):**
- Location: `ra-tracker/ra_tracker/scheduler/jobs.py`
- Triggers: APScheduler interval trigger, manual via `run_fetch_now()`
- Responsibilities: Orchestrate fetch -> match -> notify pipeline

## API Routes

**Dashboard:**
- `GET /`: Main dashboard, calls `get_upcoming_events_for_user()` with `local_area_id`

**Rule Management:**
- `POST /rules/add`: Create new rule with notify_mode and dashboard_mode
- `POST /rules/{rule_id}/notify-mode`: Update notification mode ('all'/'local'/'none')
- `POST /rules/{rule_id}/dashboard-mode`: Update dashboard visibility mode ('all'/'local'/'none')
- `POST /rules/{rule_id}/delete`: Delete rule (ownership verified)

**Search API:**
- `GET /api/search/artists`: Search RA for artists
- `GET /api/search/venues`: Search RA for venues
- `GET /api/search/promoters`: Search RA for promoters

## Error Handling

**Strategy:** Log and continue - non-blocking on notification failures

**Patterns:**
- GraphQL errors logged and raised as exceptions in `RAClient._execute()`
- Per-rule fetch errors caught in `fetch_and_notify()`, logged, continue to next rule
- Telegram failures caught and logged, marked as non-blocking
- Database errors use transaction rollback via context manager

## Cross-Cutting Concerns

**Logging:** Python `logging` module with configurable verbosity via `--verbose` flag. Module-level loggers (`logger = logging.getLogger(__name__)`). Noisy libraries (httpx, httpcore, apscheduler) suppressed to WARNING level.

**Validation:** Minimal - relies on GraphQL API returning valid data. Form validation done by FastAPI/Pydantic. Mode validation in route handlers (allowed values: 'all', 'local', 'none').

**Authentication:** Cookie-based sessions via `require_auth` dependency. Telegram bot token stored in config.yaml or env vars. ra.co API is public, no auth required.

**Authorization:** Rule ownership verified via `get_rule_for_user()` before any mutation. Returns 404 if rule doesn't exist or belongs to different user.

---

*Architecture analysis: 2026-02-01*
