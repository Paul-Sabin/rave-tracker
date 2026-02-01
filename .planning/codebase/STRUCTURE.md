# Codebase Structure

**Analysis Date:** 2026-01-19

## Directory Layout

```
ra-tips/                           # Repository root (exploration/prototypes)
├── ra-tracker/                    # Main application
│   ├── ra_tracker/                # Python package
│   │   ├── api/                   # External API clients
│   │   ├── scheduler/             # Background job definitions
│   │   ├── services/              # Business logic services
│   │   ├── web/                   # FastAPI web layer
│   │   │   └── templates/         # Jinja2 HTML templates
│   │   ├── __init__.py            # Package init with version
│   │   ├── config.py              # Configuration management
│   │   ├── database.py            # SQLite database layer
│   │   └── main.py                # CLI entry point
│   ├── data/                      # SQLite database files (runtime)
│   ├── config.yaml                # User configuration
│   ├── config.example.yaml        # Configuration template
│   ├── requirements.txt           # Python dependencies
│   └── README.md                  # Project documentation
├── .planning/                     # GSD planning artifacts
│   └── codebase/                  # Codebase analysis docs
├── venv/                          # Python virtual environment
├── explore_api.py                 # API exploration script
├── explore_api_v2.py              # API exploration script v2
├── test_ra_api.py                 # API testing script
├── test_ra_scrape.py              # Scraping test script
└── *.json                         # API exploration outputs
```

## Directory Purposes

**`ra-tracker/ra_tracker/`:**
- Purpose: Main Python package for the RA Tracker application
- Contains: All production source code organized by layer
- Key files: `main.py` (entry), `config.py`, `database.py`

**`ra-tracker/ra_tracker/api/`:**
- Purpose: External API integration code
- Contains: GraphQL client for ra.co
- Key files: `ra_client.py` - RAClient class with all API methods

**`ra-tracker/ra_tracker/services/`:**
- Purpose: Business logic layer
- Contains: Service classes for fetching, matching, notifying
- Key files: `fetcher.py`, `matcher.py`, `notifier.py`

**`ra-tracker/ra_tracker/scheduler/`:**
- Purpose: Background job scheduling
- Contains: APScheduler configuration and job definitions
- Key files: `jobs.py` - fetch_and_notify job, scheduler lifecycle

**`ra-tracker/ra_tracker/web/`:**
- Purpose: Web UI and HTTP API
- Contains: FastAPI app, routes, templates
- Key files: `app.py` (app factory), `routes.py` (all endpoints)

**`ra-tracker/ra_tracker/web/templates/`:**
- Purpose: Jinja2 HTML templates for web UI
- Contains: Base layout and page templates
- Key files: `base.html`, `dashboard.html`, `rules.html`, `settings.html`

**`ra-tracker/data/`:**
- Purpose: Runtime data storage
- Contains: SQLite database file
- Key files: `ra_tracker.db` (created at runtime)

## Key File Locations

**Entry Points:**
- `ra-tracker/ra_tracker/main.py`: CLI entry point, starts scheduler and web server
- `ra-tracker/ra_tracker/web/app.py`: FastAPI app instance for uvicorn

**Configuration:**
- `ra-tracker/config.yaml`: User-editable YAML config (created from example)
- `ra-tracker/config.example.yaml`: Template configuration
- `ra-tracker/ra_tracker/config.py`: Config dataclasses and loading logic

**Core Logic:**
- `ra-tracker/ra_tracker/api/ra_client.py`: GraphQL client (600 lines)
- `ra-tracker/ra_tracker/database.py`: Schema, models, CRUD (663 lines)
- `ra-tracker/ra_tracker/services/fetcher.py`: Event fetching service
- `ra-tracker/ra_tracker/services/notifier.py`: Telegram notification service
- `ra-tracker/ra_tracker/scheduler/jobs.py`: Background job orchestration

**Web UI:**
- `ra-tracker/ra_tracker/web/routes.py`: All HTTP routes and API endpoints
- `ra-tracker/ra_tracker/web/templates/dashboard.html`: Main events view
- `ra-tracker/ra_tracker/web/templates/rules.html`: Rule management
- `ra-tracker/ra_tracker/web/templates/settings.html`: Configuration UI

**Testing:**
- No formal test directory exists in ra-tracker
- Root-level `test_ra_api.py` and `test_ra_scrape.py` are exploration scripts

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `ra_client.py`, `database.py`)
- Templates: `snake_case.html` (e.g., `dashboard.html`)
- Config files: `snake_case.yaml` (e.g., `config.yaml`)

**Directories:**
- Package directories: `snake_case` (e.g., `ra_tracker`, `api`, `services`)
- No pluralization pattern - both `services` (plural) and `api` (singular) used

**Classes:**
- PascalCase with descriptive names (e.g., `RAClient`, `Fetcher`, `Notifier`)
- Dataclasses use PascalCase (e.g., `Rule`, `Event`, `RAEvent`)
- Config dataclasses suffixed with `Config` (e.g., `TelegramConfig`)

**Functions:**
- snake_case verbs (e.g., `fetch_for_rule()`, `get_config()`, `run_fetch_now()`)
- Getters prefixed with `get_` (e.g., `get_db()`, `get_scheduler_status()`)
- Boolean checks use `is_` or `has_` prefix (e.g., `is_configured()`, `has_notification()`)

## Where to Add New Code

**New External API Integration:**
- Add new client class in `ra-tracker/ra_tracker/api/`
- Follow `ra_client.py` pattern: dataclasses for response types, session-based client

**New Business Service:**
- Add new module in `ra-tracker/ra_tracker/services/`
- Follow pattern: class with `__init__` getting db/config, methods for operations
- Export convenience function (e.g., `get_notifier()`)

**New Web Route:**
- Add routes to `ra-tracker/ra_tracker/web/routes.py`
- HTML pages: add template to `ra-tracker/ra_tracker/web/templates/`
- API endpoints: prefix with `/api/`

**New Scheduled Job:**
- Add job function to `ra-tracker/ra_tracker/scheduler/jobs.py`
- Register in `start_scheduler()` with APScheduler trigger

**New Database Table:**
- Add schema in `SCHEMA` constant in `ra-tracker/ra_tracker/database.py`
- Add migration in `MIGRATIONS` list
- Add dataclass model and CRUD methods to `Database` class

**New Configuration Section:**
- Add dataclass in `ra-tracker/ra_tracker/config.py`
- Add as field to main `Config` dataclass
- Update `load()` and `save()` methods

**Tests (when added):**
- Create `ra-tracker/tests/` directory
- Use `test_*.py` naming for test files
- Mirror source structure (e.g., `tests/services/test_fetcher.py`)

## Special Directories

**`venv/`:**
- Purpose: Python virtual environment
- Generated: Yes (via `python -m venv venv`)
- Committed: No (should be in .gitignore)

**`ra-tracker/data/`:**
- Purpose: Runtime SQLite database storage
- Generated: Yes (created by database.py at runtime)
- Committed: No (contains user data)

**`.planning/`:**
- Purpose: GSD planning and analysis documents
- Generated: Yes (by GSD commands)
- Committed: Optional (useful for project context)

**`.claude/`:**
- Purpose: Claude Code configuration
- Generated: Yes
- Committed: Optional

**Root-level `*.py` and `*.json` files:**
- Purpose: API exploration and prototyping (pre-ra-tracker development)
- Generated: No (manual exploration scripts)
- Committed: Optional (not part of main application)

---

*Structure analysis: 2026-01-19*
