# External Integrations

**Analysis Date:** 2026-01-19

## APIs & External Services

**RA.co GraphQL API:**
- Endpoint: `https://ra.co/graphql`
- Client: `ra-tracker/ra_tracker/api/ra_client.py`
- Auth: None (public API, but requires browser-like headers)
- Rate limiting: 1 second minimum between requests (self-imposed)

**Required Headers:**
```python
{
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://ra.co/",
}
```

**GraphQL Operations Used:**
- `GET_ARTIST_EVENTS` - Fetch upcoming events for an artist by ID
- `GET_VENUE_EVENTS` - Fetch upcoming events for a venue by ID
- `GET_PROMOTER_EVENTS` - Fetch upcoming events for a promoter by ID
- `SEARCH` - Search artists, venues, promoters, areas by name
- `GET_ARTIST` / `GET_VENUE` / `GET_PROMOTER` - Get entity by ID

**Telegram Bot API:**
- Service: Telegram messaging platform
- SDK/Client: `python-telegram-bot>=20.0`
- Implementation: `ra-tracker/ra_tracker/services/notifier.py`
- Auth env vars:
  - `TELEGRAM_BOT_TOKEN` (or config: `telegram.bot_token`)
  - `TELEGRAM_CHAT_ID` (or config: `telegram.chat_id`)

**Message Formats:**
- MarkdownV2 formatted event notifications
- Plain text fallback on formatting errors
- Summary notifications for multiple events

## Data Storage

**Databases:**
- SQLite (file-based)
  - Connection: `database.path` in config (default: `./data/ra_tracker.db`)
  - Client: `sqlite3` (Python stdlib)
  - Implementation: `ra-tracker/ra_tracker/database.py`

**Schema Tables:**
- `rules` - Tracking rules (artist/venue/promoter subscriptions)
- `events` - Cached event data
- `event_rules` - Event-to-rule mapping (which rules matched)
- `event_artists` - Event artist relationships
- `event_promoters` - Event promoter relationships
- `notifications` - Sent notification tracking (deduplication)

**File Storage:**
- Local filesystem for SQLite database
- Configuration stored in `config.yaml`

**Caching:**
- Events cached in SQLite database
- Cache cleared and rebuilt on each fetch cycle

## Authentication & Identity

**Auth Provider:**
- None for main application (no user login)
- Telegram bot token for notification service

**Implementation:**
- Bot token stored in `config.yaml` or environment variable
- No user authentication - single-user design

## Monitoring & Observability

**Error Tracking:**
- None (no external error tracking service)

**Logs:**
- Python `logging` module to stdout
- Log levels controlled by `--verbose` flag
- Key loggers suppressed: `httpx`, `httpcore`, `apscheduler`

## CI/CD & Deployment

**Hosting:**
- Self-hosted (runs on user's machine)
- Web UI binds to configurable host/port (default: `0.0.0.0:8080`)

**CI Pipeline:**
- None configured

## Environment Configuration

**Required env vars:**
- None strictly required (can use config file)

**Optional env vars:**
- `TELEGRAM_BOT_TOKEN` - Telegram bot authentication
- `TELEGRAM_CHAT_ID` - Telegram notification target
- `RA_TRACKER_DB_PATH` - Database file location
- `RA_TRACKER_CONFIG` - Config file path

**Secrets location:**
- `config.yaml` (not committed - use `config.example.yaml` as template)
- Note: `config.yaml` contains sensitive bot token in current state

## Webhooks & Callbacks

**Incoming:**
- None - Application polls RA.co on schedule

**Outgoing:**
- Telegram Bot API - Push notifications for new events

## Scheduled Operations

**Background Jobs:**
- APScheduler `BackgroundScheduler`
- Implementation: `ra-tracker/ra_tracker/scheduler/jobs.py`

**Jobs:**
- `fetch_and_notify` - Runs every `fetch_interval_hours` (default: 6)
  - Fetches events for all active rules from RA.co
  - Clears and rebuilds event cache
  - Sends Telegram summary for new events

## API Response Data Structures

**Event Data from RA.co:**
```python
@dataclass
class RAEvent:
    id: int
    title: str
    date: date
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    venue_id: Optional[int]
    venue_name: Optional[str]
    area_id: Optional[int]
    area_name: Optional[str]
    content_url: Optional[str]
    cost: Optional[str]
    is_ticketed: Optional[bool]
    is_festival: Optional[bool]
    is_multi_day: Optional[bool]
    attending: Optional[int]
    interested_count: Optional[int]
    pick_blurb: Optional[str]
    set_times_status: Optional[str]
    set_times_lineup: Optional[str]
    tickets_json: Optional[str]
    artists: List[tuple]  # (artist_id, artist_name, artist_url)
    promoters: List[tuple]  # (promoter_id, promoter_name)
```

**Search Results:**
- Artists, Venues, Promoters, Areas returned as `(id, name)` tuples
- Search indices: `ARTIST`, `CLUB` (venues), `PROMOTER`, `AREA`

## Integration Health

**RA.co API:**
- No official API documentation (undocumented GraphQL)
- Requires browser-like request headers
- May be subject to rate limiting or blocking
- Schema explored via introspection queries

**Telegram:**
- Standard Bot API integration
- Rate limited to 0.5s between messages in batch sends
- Fallback to plain text on markdown formatting errors

---

*Integration audit: 2026-01-19*
