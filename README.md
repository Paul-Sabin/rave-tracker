# Rave Tracker

Track the electronic-music events you actually care about. Rave Tracker watches [Resident Advisor](https://ra.co) for club nights and festivals matching your chosen artists, venues and promoters, and pushes them to you by **Telegram and email** — with a web dashboard to manage everything.

**Live demo:** https://ravetracker.whotrustswho.com

> A personal project built to scratch a real itch — never missing a set worth catching in Berlin. It uses Resident Advisor's public GraphQL API and is non-commercial.

<!-- TODO: add a dashboard screenshot here, e.g. ![Rave Tracker dashboard](docs/screenshot.png) — a screenshot/GIF is the single best thing you can add. -->

## What it does

- **Rule-based tracking** — follow specific artists, venues or promoters; search Resident Advisor from the UI to add them.
- **Notifications** — Telegram and email alerts when matching events appear, with per-rule modes (all / local-only / off) and per-event deduplication so you're never pinged twice.
- **Web dashboard** — browse upcoming events in full detail (lineup, set times, cost, attendance), filter by area or rule type, and trigger a fetch on demand.
- **Multi-user** — accounts with authentication, email verification and password reset; each user keeps their own rules and notification preferences over a shared event cache.
- **Scheduled fetching** — a background scheduler refreshes events on a configurable interval.

## Tech stack

**Python** · **FastAPI** + Uvicorn · **Jinja2** · **httpx** (Resident Advisor GraphQL client) · **APScheduler** · **python-telegram-bot** · **SQLite → PostgreSQL** · **Brevo** SMTP · **Sentry** · **Docker** · deployed on **Railway**

## Architecture & design decisions

The interesting part isn't the feature list — it's the choices behind it:

- **Layered configuration.** Non-secret defaults live in `config.yaml`; secrets come from a gitignored `.env` (via `python-dotenv`); environment variables override both. Secrets never touch the repo (see `.env.example`).
- **Resilient API client.** The Resident Advisor GraphQL client sits behind a **circuit breaker**, so transient upstream failures degrade gracefully instead of cascading — plus an alerter that flags when the upstream response shape changes.
- **Clean service separation.** `fetcher` (pull events) → `matcher` (apply rules) → `notifier` / `email_sender` / `telegram_bot` (deliver), coordinated by a `scheduler`. Each piece is independently testable.
- **Grew from single-user to multi-user deliberately.** v1 was a local single-user SQLite app; multi-user added authentication, CSRF protection, rate limiting, password hashing/validation, email verification and an audit log — and a **SQLite → PostgreSQL migration** (`scripts/migrate_sqlite_to_pg.py`) for multi-instance deployment.
- **Observability built in.** Structured logging, request access-log middleware, and Sentry error tracking.
- **Containerised & deployed.** Dockerfile + Railway config; the same app runs locally and in production.

## Running locally

```bash
git clone https://github.com/Paul-Sabin/rave-tracker.git
cd rave-tracker/ra-tracker

pip install -r requirements.txt
cp config.example.yaml config.yaml                            # base config
cp .env.example .env                                          # then fill in your secrets
python -c "import secrets; print(secrets.token_urlsafe(32))"  # generate a SECRET_KEY

python -m ra_tracker.main                                     # web UI at http://localhost:8080
```

Useful flags: `--fetch-only` (single fetch, no server), `--no-scheduler` (server only), `--host` / `--port`. Telegram notifications need a bot token from [@BotFather](https://t.me/BotFather).

## Repository layout

The application lives in [`ra-tracker/`](ra-tracker/) (the `ra_tracker` package); the repository root holds API-exploration scripts and project planning. Fuller internal docs are in [`ra-tracker/PROJECT_STATUS.md`](ra-tracker/PROJECT_STATUS.md).

## Notes

Built iteratively with Claude Code as a coding companion (hence the `CLAUDE.md`). A personal, non-commercial project; not affiliated with Resident Advisor.

## License

[MIT](LICENSE) © 2026 Paul Sabin
