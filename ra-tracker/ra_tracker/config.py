"""Configuration management for RA Tracker."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""  # Kept for backwards compat / admin test
    webhook_secret: str = ""  # For verifying webhook requests
    use_webhook: bool = False  # False = polling, True = webhook
    webhook_url: str = ""  # Required if use_webhook is True


@dataclass
class SchedulerConfig:
    fetch_interval_hours: int = 6          # kept for backward compat; UI removed in Phase 16
    event_horizon_days: int = 30
    fetch_times: list = None               # list of "HH:MM" strings, e.g. ["08:00", "20:00"]
    notification_mode: str = "upon_fetch"  # "upon_fetch" or "daily_digest"
    digest_time: str = "08:00"             # "HH:MM" - when to send daily digest

    def __post_init__(self):
        if self.fetch_times is None:
            self.fetch_times = []


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass
class DatabaseConfig:
    path: str = "./data/ra_tracker.db"
    url: Optional[str] = None


@dataclass
class UserConfig:
    local_area_id: Optional[int] = None
    local_area_name: str = ""


@dataclass
class SessionConfig:
    timeout_days: int = 30
    secure_cookies: bool = True  # Set False for local HTTP dev


@dataclass
class EmailConfig:
    server: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = ""
    from_name: str = "Rave Tracker"
    starttls: bool = True
    ssl_tls: bool = False
    use_api: bool = False  # True = Brevo HTTP API (bypasses SMTP port blocks)
    api_key: str = ""  # Brevo API key (separate from SMTP password)


@dataclass
class AppConfig:
    secret_key: str = ""  # For signing tokens (unsubscribe links)
    base_url: str = "http://localhost:8080"  # For email links


@dataclass
class ObservabilityConfig:
    sentry_dsn: str = ""          # SENTRY_DSN env var
    logtail_token: str = ""       # LOGTAIL_SOURCE_TOKEN env var
    environment: str = "production"  # ENVIRONMENT env var
    log_level: str = "INFO"       # LOG_LEVEL env var


@dataclass
class Config:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    web: WebConfig = field(default_factory=WebConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    user: UserConfig = field(default_factory=UserConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    app: AppConfig = field(default_factory=AppConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)

    def _validate_required_secrets(self) -> None:
        """Validate that required secrets are set.

        Raises:
            ValueError: If any required secrets are missing.
        """
        missing = []

        if not self.telegram.bot_token:
            missing.append(("TELEGRAM_BOT_TOKEN", "telegram bot token"))

        if not self.app.secret_key:
            missing.append(("SECRET_KEY", "application secret key for token signing"))

        if not self.email.password:
            missing.append(("BREVO_SMTP_PASSWORD or EMAIL_SMTP_PASSWORD", "SMTP password for email delivery"))

        if missing:
            missing_list = "\n".join(f"  - {var} ({desc})" for var, desc in missing)
            raise ValueError(
                f"Missing required secrets. Set these environment variables (see .env.example):\n{missing_list}"
            )

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = os.environ.get("RA_TRACKER_CONFIG", "config.yaml")

        config = cls()
        path = Path(config_path)

        if path.exists():
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}

            if "telegram" in data:
                config.telegram = TelegramConfig(**data["telegram"])
            if "scheduler" in data:
                sched_data = data["scheduler"]
                config.scheduler.fetch_interval_hours = sched_data.get("fetch_interval_hours", 6)
                config.scheduler.event_horizon_days = sched_data.get("event_horizon_days", 30)
                config.scheduler.fetch_times = sched_data.get("fetch_times", [])
                config.scheduler.notification_mode = sched_data.get("notification_mode", "upon_fetch")
                config.scheduler.digest_time = sched_data.get("digest_time", "08:00")
            if "web" in data:
                config.web = WebConfig(**data["web"])
            if "database" in data:
                config.database = DatabaseConfig(**data["database"])
            if "user" in data:
                config.user = UserConfig(**data["user"])
            if "session" in data:
                config.session = SessionConfig(**data["session"])
            if "email" in data:
                config.email = EmailConfig(**data["email"])
            if "app" in data:
                config.app = AppConfig(**data["app"])

        # Override with environment variables
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            config.telegram.bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
        if os.environ.get("TELEGRAM_CHAT_ID"):
            config.telegram.chat_id = os.environ["TELEGRAM_CHAT_ID"]
        if os.environ.get("RA_TRACKER_DB_PATH"):
            config.database.path = os.environ["RA_TRACKER_DB_PATH"]

        # Email environment variable overrides
        # Supports both EMAIL_SMTP_* and BREVO_SMTP_* naming conventions
        if os.environ.get("EMAIL_SMTP_SERVER"):
            config.email.server = os.environ["EMAIL_SMTP_SERVER"]
        if os.environ.get("EMAIL_SMTP_PORT"):
            config.email.port = int(os.environ["EMAIL_SMTP_PORT"])
        if os.environ.get("BREVO_SMTP_USERNAME") or os.environ.get("EMAIL_SMTP_USERNAME"):
            config.email.username = os.environ.get("BREVO_SMTP_USERNAME") or os.environ["EMAIL_SMTP_USERNAME"]
        if os.environ.get("BREVO_SMTP_PASSWORD") or os.environ.get("EMAIL_SMTP_PASSWORD"):
            config.email.password = os.environ.get("BREVO_SMTP_PASSWORD") or os.environ["EMAIL_SMTP_PASSWORD"]
        if os.environ.get("EMAIL_FROM_ADDRESS"):
            config.email.from_address = os.environ["EMAIL_FROM_ADDRESS"]
        if os.environ.get("EMAIL_FROM_NAME"):
            config.email.from_name = os.environ["EMAIL_FROM_NAME"]
        if os.environ.get("EMAIL_USE_API", "").lower() in ("true", "1", "yes"):
            config.email.use_api = True
        if os.environ.get("BREVO_API_KEY"):
            config.email.api_key = os.environ["BREVO_API_KEY"]

        # App environment variable overrides
        # Supports both APP_* and shorter naming conventions
        if os.environ.get("SECRET_KEY") or os.environ.get("APP_SECRET_KEY"):
            config.app.secret_key = os.environ.get("SECRET_KEY") or os.environ["APP_SECRET_KEY"]
        if os.environ.get("BASE_URL") or os.environ.get("APP_BASE_URL"):
            config.app.base_url = (os.environ.get("BASE_URL") or os.environ["APP_BASE_URL"]).rstrip("/")

        # Database URL (PostgreSQL)
        if os.environ.get("DATABASE_URL"):
            db_url = os.environ["DATABASE_URL"]
            # Normalize postgres:// to postgresql:// (hosting provider compatibility)
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            config.database.url = db_url

        # Observability environment variable overrides
        if os.environ.get("SENTRY_DSN"):
            config.observability.sentry_dsn = os.environ["SENTRY_DSN"]
        if os.environ.get("LOGTAIL_SOURCE_TOKEN"):
            config.observability.logtail_token = os.environ["LOGTAIL_SOURCE_TOKEN"]
        if os.environ.get("ENVIRONMENT"):
            config.observability.environment = os.environ["ENVIRONMENT"]
        if os.environ.get("LOG_LEVEL"):
            config.observability.log_level = os.environ["LOG_LEVEL"]

        # Validate required secrets
        config._validate_required_secrets()

        return config

    def apply_db_overrides(self, db) -> "Config":
        """Overlay the admin-managed settings stored in the database.

        Precedence is env var > database > config.yaml. The database sits
        between the two because config.yaml ships with the image and holds
        deploy-time defaults, while the database is what the admin UI writes
        and is the only store the web and scheduler containers share.

        Deliberately not folded into load(): Database.__init__ calls
        get_config(), so reading settings from inside load() would recurse.
        Callers apply this explicitly once they have a database.

        Returns self, so it can be chained onto load().
        """
        try:
            settings = db.get_app_settings()
        except Exception as e:  # never let a settings read stop startup
            logging.getLogger(__name__).warning(
                f"Could not apply database settings, using file defaults: {e}"
            )
            return self

        if not settings:
            return self

        if "scheduler.fetch_times" in settings:
            value = settings["scheduler.fetch_times"]
            if isinstance(value, list):
                self.scheduler.fetch_times = value
        if "scheduler.event_horizon_days" in settings:
            self.scheduler.event_horizon_days = int(settings["scheduler.event_horizon_days"])
        if "scheduler.notification_mode" in settings:
            if settings["scheduler.notification_mode"] in ("upon_fetch", "daily_digest"):
                self.scheduler.notification_mode = settings["scheduler.notification_mode"]
        if "scheduler.digest_time" in settings:
            self.scheduler.digest_time = str(settings["scheduler.digest_time"])

        # The env var still wins, per the precedence above. Without this guard
        # a deployment that pins TELEGRAM_CHAT_ID would appear to accept an
        # admin change and then quietly ignore it on the next load.
        if "telegram.chat_id" in settings and not os.environ.get("TELEGRAM_CHAT_ID"):
            self.telegram.chat_id = str(settings["telegram.chat_id"])

        return self

    def db_managed_settings(self) -> dict:
        """The current values of everything the admin UI persists.

        Secrets are excluded on purpose: the bot token, secret key and SMTP
        password come from environment variables and must not be copied into
        the database.
        """
        return {
            "scheduler.fetch_times": list(self.scheduler.fetch_times),
            "scheduler.event_horizon_days": int(self.scheduler.event_horizon_days),
            "scheduler.notification_mode": self.scheduler.notification_mode,
            "scheduler.digest_time": self.scheduler.digest_time,
            "telegram.chat_id": self.telegram.chat_id,
        }

# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
