"""Configuration management for RA Tracker."""

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
    fetch_interval_hours: int = 6
    event_horizon_days: int = 30


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass
class DatabaseConfig:
    path: str = "./data/ra_tracker.db"


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


@dataclass
class AppConfig:
    secret_key: str = ""  # For signing tokens (unsubscribe links)
    base_url: str = "http://localhost:8080"  # For email links


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
                config.scheduler = SchedulerConfig(**data["scheduler"])
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

        # App environment variable overrides
        # Supports both APP_* and shorter naming conventions
        if os.environ.get("SECRET_KEY") or os.environ.get("APP_SECRET_KEY"):
            config.app.secret_key = os.environ.get("SECRET_KEY") or os.environ["APP_SECRET_KEY"]
        if os.environ.get("BASE_URL") or os.environ.get("APP_BASE_URL"):
            config.app.base_url = os.environ.get("BASE_URL") or os.environ["APP_BASE_URL"]

        # Validate required secrets
        config._validate_required_secrets()

        return config

    def save(self, config_path: str = "config.yaml") -> None:
        """Save configuration to YAML file."""
        data = {
            "telegram": {
                "bot_token": self.telegram.bot_token,
                "chat_id": self.telegram.chat_id,
                "webhook_secret": self.telegram.webhook_secret,
                "use_webhook": self.telegram.use_webhook,
                "webhook_url": self.telegram.webhook_url,
            },
            "scheduler": {
                "fetch_interval_hours": self.scheduler.fetch_interval_hours,
                "event_horizon_days": self.scheduler.event_horizon_days,
            },
            "web": {
                "host": self.web.host,
                "port": self.web.port,
            },
            "database": {
                "path": self.database.path,
            },
            "user": {
                "local_area_id": self.user.local_area_id,
                "local_area_name": self.user.local_area_name,
            },
            "session": {
                "timeout_days": self.session.timeout_days,
                "secure_cookies": self.session.secure_cookies,
            },
            "email": {
                "server": self.email.server,
                "port": self.email.port,
                "username": self.email.username,
                "password": self.email.password,
                "from_address": self.email.from_address,
                "from_name": self.email.from_name,
                "starttls": self.email.starttls,
                "ssl_tls": self.email.ssl_tls,
            },
            "app": {
                "secret_key": self.app.secret_key,
                "base_url": self.app.base_url,
            },
        }

        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)


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
