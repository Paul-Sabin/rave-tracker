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

Edit `config.yaml`:

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
```

Environment variables can also be used:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `RA_TRACKER_DB_PATH`
- `RA_TRACKER_CONFIG` (path to config file)

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
