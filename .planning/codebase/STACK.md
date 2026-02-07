# Technology Stack

**Analysis Date:** 2026-01-19

## Languages

**Primary:**
- Python 3.11+ - All application code

**Secondary:**
- HTML/Jinja2 - Web UI templates in `ra-tracker/ra_tracker/web/templates/`
- SQL - SQLite schema and queries in `ra-tracker/ra_tracker/database.py`
- CSS - Custom inline styles in base.html (migrating to Tailwind CSS in Milestone 2)

## Runtime

**Environment:**
- Python 3.11 (based on `.pyc` files: `__pycache__/*.cpython-311.pyc`)
- Windows platform (development environment)

**Package Manager:**
- pip
- Lockfile: Not present (only `requirements.txt`)

**Virtual Environment:**
- venv located at `venv/` in project root

## Frameworks

**Core:**
- FastAPI 0.109.0+ - Web framework for REST API and UI (`ra-tracker/ra_tracker/web/app.py`)
- Uvicorn 0.27.0+ - ASGI server for running FastAPI (`ra-tracker/ra_tracker/main.py`)

**Testing:**
- None detected - No test framework configured

**Build/Dev:**
- No build tooling detected - Pure Python project

## Key Dependencies

**Critical (ra-tracker/requirements.txt):**
- `fastapi>=0.109.0` - Web framework
- `uvicorn>=0.27.0` - ASGI server
- `jinja2>=3.1.0` - HTML templating
- `python-multipart>=0.0.6` - Form data parsing for FastAPI
- `apscheduler>=3.10.0` - Background job scheduling
- `requests>=2.31.0` - HTTP client for RA.co GraphQL API
- `python-telegram-bot>=20.0` - Telegram Bot API integration
- `pyyaml>=6.0` - YAML configuration file parsing
- `aiosqlite>=0.19.0` - Async SQLite support (listed but not actively used)
- `argon2-cffi>=23.1.0` - Password hashing (Argon2id, OWASP 2025 recommended)
- `python-dotenv>=1.0.0` - Load environment variables from .env file
- `slowapi>=0.1.9` - Rate limiting for FastAPI routes
- `itsdangerous>=2.0.0` - Signed token generation (verification, unsubscribe)
- `fastapi-mail>=1.0.0` - Email sending via SMTP

**Frontend (Milestone 2 - planned):**
- Tailwind CSS - Utility-first CSS framework for responsive mobile-first design

**Exploration Scripts (root level):**
- `requests` - HTTP client for GraphQL API exploration
- `playwright` - Browser automation for scraping tests (in venv)

## Configuration

**Layered Configuration (priority order):**
1. `.env` file - Sensitive secrets (loaded via python-dotenv at startup)
2. Environment variables - Runtime overrides
3. `config.yaml` - Base configuration with non-sensitive defaults

**Files:**
- `ra-tracker/config.yaml` - Main configuration (can use `${VAR}` placeholders)
- `ra-tracker/config.example.yaml` - Template showing all options
- `ra-tracker/.env` - Sensitive secrets (gitignored, never committed)

**Environment Variable Overrides:**
- `SECRET_KEY` / `APP_SECRET_KEY` - Token signing key (required)
- `BASE_URL` / `APP_BASE_URL` - Public URL for email links
- `BREVO_SMTP_USERNAME` / `EMAIL_SMTP_USERNAME` - SMTP username
- `BREVO_SMTP_PASSWORD` / `EMAIL_SMTP_PASSWORD` - SMTP password
- `EMAIL_SMTP_SERVER` - SMTP server hostname
- `EMAIL_SMTP_PORT` - SMTP port
- `EMAIL_FROM_ADDRESS` - From email address
- `EMAIL_FROM_NAME` - From display name
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Legacy chat ID
- `RA_TRACKER_DB_PATH` - Database file path
- `RA_TRACKER_CONFIG` - Alternative config file path

**Configuration Sections:**
- `telegram` - Bot token, chat ID, webhook settings
- `scheduler` - Fetch interval (hours), event horizon (days)
- `web` - Host and port bindings
- `database` - SQLite database path
- `user` - Local area ID and name for filtering
- `session` - Session timeout, secure cookie settings
- `email` - SMTP server, credentials, from address
- `app` - Secret key, base URL

**Build:**
- No build configuration - Runs directly as Python scripts

## Platform Requirements

**Development:**
- Python 3.11+
- pip
- Optional: Playwright for scraping tests

**Production:**
- Python 3.11+
- Network access to ra.co GraphQL API
- Network access to Telegram API (for notifications)
- File system access for SQLite database

## Project Structure

**Main Application:**
- `ra-tracker/` - Primary RA Tracker application
  - `ra_tracker/` - Python package
  - `config.yaml` - Configuration
  - `requirements.txt` - Dependencies
  - `data/` - SQLite database storage

**Exploration/Test Scripts:**
- `explore_api.py` - GraphQL API exploration
- `explore_api_v2.py` - Extended API exploration
- `test_ra_api.py` - GraphQL API connectivity test
- `test_ra_scrape.py` - Playwright scraping feasibility test

## Entry Points

**Main application:**
```bash
cd ra-tracker
python -m ra_tracker.main -c config.yaml
```

**CLI Arguments:**
- `-c, --config` - Config file path (default: config.yaml)
- `-v, --verbose` - Enable verbose logging
- `--fetch-only` - Run single fetch and exit
- `--no-scheduler` - Disable scheduler, web server only
- `--host` - Override web server host
- `--port` - Override web server port

---

*Stack analysis: 2026-01-19*
