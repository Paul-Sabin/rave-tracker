# RA Tracker

A Python-based event tracking system that monitors ra.co for events matching user-defined rules and sends Telegram notifications. Includes a web UI for managing preferences.

## Features

- **Track Events**: Monitor ra.co for events in specified cities/areas
- **Flexible Rules**: Track by artist, venue, genre, or keyword
- **Telegram Notifications**: Get notified when matching events are found
- **Web UI**: Easy-to-use interface for managing rules and settings
- **Scheduled Fetching**: Automatic background fetching of new events

## Installation

1. Clone or download this repository

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example config and edit it:
   ```bash
   cp config.example.yaml config.yaml
   ```

4. Configure your Telegram bot:
   - Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
   - Copy the bot token to `config.yaml`
   - Get your chat ID (use [@userinfobot](https://t.me/userinfobot))
   - Add the chat ID to `config.yaml`

## Usage

### Start the server

```bash
python -m ra_tracker.main
```

The web UI will be available at http://localhost:8080

### Command line options

```
usage: main.py [-h] [-c CONFIG] [-v] [--fetch-only] [--no-scheduler] [--host HOST] [--port PORT]

options:
  -c, --config      Path to configuration file (default: config.yaml)
  -v, --verbose     Enable verbose logging
  --fetch-only      Run a single fetch and exit (no web server)
  --no-scheduler    Disable the scheduler (web server only)
  --host HOST       Web server host (overrides config)
  --port PORT       Web server port (overrides config)
```

### Examples

Run a one-time fetch:
```bash
python -m ra_tracker.main --fetch-only
```

Start with custom host/port:
```bash
python -m ra_tracker.main --host 127.0.0.1 --port 3000
```

## Configuration

### Quick Start

1. Copy the example config:
   ```bash
   cp config.example.yaml config.yaml
   ```

2. Create a `.env` file for sensitive values:
   ```bash
   # .env (gitignored - never commit this file)
   SECRET_KEY=your-generated-secret-key
   BREVO_SMTP_USERNAME=your-smtp-username
   BREVO_SMTP_PASSWORD=your-smtp-password
   BASE_URL=http://localhost:8080
   ```

3. Generate a secret key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

### How Configuration Works

The app uses a layered configuration approach:

1. **config.yaml** - Base configuration with non-sensitive defaults
2. **.env file** - Sensitive secrets (loaded via python-dotenv)
3. **Environment variables** - Runtime overrides (highest priority)

The `.env` file is loaded at startup before config.yaml is parsed, so environment variables from `.env` override any placeholder values in the YAML.

### config.yaml Structure

```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"

scheduler:
  fetch_interval_hours: 6
  event_horizon_days: 30

web:
  host: "0.0.0.0"
  port: 8080

database:
  path: "./data/ra_tracker.db"

email:
  server: smtp-relay.brevo.com
  port: 587
  username: "${BREVO_SMTP_USERNAME}"  # Placeholder - overridden by .env
  password: "${BREVO_SMTP_PASSWORD}"  # Placeholder - overridden by .env
  from_address: "noreply@yourdomain.com"
  from_name: "RA Tracker"
  starttls: true
  ssl_tls: false

app:
  secret_key: "${SECRET_KEY}"  # Placeholder - overridden by .env
  base_url: "${BASE_URL}"      # Placeholder - overridden by .env
```

### Environment Variables

All settings can be overridden via environment variables:

| Variable | Config Path | Description |
|----------|-------------|-------------|
| `SECRET_KEY` | `app.secret_key` | Required for token signing |
| `BASE_URL` | `app.base_url` | Public URL for email links |
| `BREVO_SMTP_USERNAME` | `email.username` | SMTP username (Brevo shorthand) |
| `BREVO_SMTP_PASSWORD` | `email.password` | SMTP password (Brevo shorthand) |
| `EMAIL_SMTP_SERVER` | `email.server` | SMTP server hostname |
| `EMAIL_SMTP_PORT` | `email.port` | SMTP port |
| `EMAIL_SMTP_USERNAME` | `email.username` | SMTP username (generic) |
| `EMAIL_SMTP_PASSWORD` | `email.password` | SMTP password (generic) |
| `EMAIL_FROM_ADDRESS` | `email.from_address` | From email address |
| `EMAIL_FROM_NAME` | `email.from_name` | From display name |
| `APP_SECRET_KEY` | `app.secret_key` | Alternative to SECRET_KEY |
| `APP_BASE_URL` | `app.base_url` | Alternative to BASE_URL |
| `TELEGRAM_BOT_TOKEN` | `telegram.bot_token` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | `telegram.chat_id` | Legacy chat ID |
| `RA_TRACKER_DB_PATH` | `database.path` | Database file path |
| `RA_TRACKER_CONFIG` | - | Path to config file |

**Priority:** `BREVO_*` and short names (`SECRET_KEY`, `BASE_URL`) take priority over `EMAIL_*` and `APP_*` variants.

## Web UI Pages

### Dashboard
- Overview of matched events
- Quick stats (events, rules, areas)
- Manual fetch trigger

### Rules
- Add tracking rules (artist, venue, genre, keyword)
- Search ra.co for artists and venues
- Enable/disable rules

### Areas
- Add cities to track
- Quick-add common cities (London, Berlin, etc.)
- Enable/disable areas

### Settings
- Telegram configuration
- Scheduler settings
- Test notifications

## Rule Types

- **Artist**: Match events featuring a specific artist (by ID or name)
- **Venue**: Match events at a specific venue
- **Genre**: Match events with a specific genre tag
- **Keyword**: Match events with keyword in title, artists, or venue name

## Common Area IDs

| City | Area ID |
|------|---------|
| London | 13 |
| Berlin | 34 |
| Amsterdam | 29 |
| Paris | 44 |
| New York | 8 |
| Los Angeles | 18 |
| Tokyo | 127 |
| Barcelona | 32 |
| Manchester | 14 |
| Ibiza | 25 |

## API Endpoints

- `GET /api/search/artists?q=<query>` - Search artists
- `GET /api/search/venues?q=<query>` - Search venues
- `GET /api/status` - Get system status

## Project Structure

```
ra-tracker/
├── ra_tracker/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration management
│   ├── database.py          # SQLite models
│   ├── api/
│   │   └── ra_client.py     # GraphQL client for ra.co
│   ├── services/
│   │   ├── fetcher.py       # Fetches events
│   │   ├── matcher.py       # Matches events against rules
│   │   └── notifier.py      # Sends Telegram notifications
│   ├── web/
│   │   ├── app.py           # FastAPI application
│   │   ├── routes.py        # API endpoints
│   │   └── templates/       # Jinja2 templates
│   └── scheduler/
│       └── jobs.py          # Scheduled tasks
├── config.example.yaml
├── requirements.txt
└── README.md
```

## License

MIT
