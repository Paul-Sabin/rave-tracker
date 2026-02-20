"""Centralized logging configuration with JSON formatter, correlation ID filter, and Better Stack handler."""

import atexit
import logging
import logging.config
import logging.handlers
import queue
import sys
from typing import Optional


def setup_logging(
    environment: str = "production",
    log_level: str = "INFO",
    logtail_token: str = "",
) -> Optional[logging.handlers.QueueListener]:
    """Configure application logging with structured JSON output and optional Better Stack shipping.

    Args:
        environment: Deployment environment ("production" or "development").
                     Development uses plain text; production uses JSON.
        log_level: Minimum log level for the ra_tracker logger (e.g. "INFO", "DEBUG").
        logtail_token: Better Stack source token. If provided, logs are shipped via
                       a non-blocking QueueHandler+QueueListener.

    Returns:
        QueueListener instance if Better Stack is configured, else None.
        Caller should stop this listener on application shutdown.
    """
    # Determine formatter for stdout: JSON in production, console text in development
    stdout_formatter = "json" if environment != "development" else "console"

    # Build base config dict
    config: dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "correlation_id": {
                "()": "asgi_correlation_id.CorrelationIdFilter",
                "uuid_length": 32,
                "default_value": "-",
            }
        },
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s",
                "rename_fields": {
                    "asctime": "timestamp",
                    "levelname": "level",
                    "name": "logger",
                    "correlation_id": "request_id",
                },
            },
            "console": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] %(message)s",
            },
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": stdout_formatter,
                "filters": ["correlation_id"],
            }
        },
        "loggers": {
            "ra_tracker": {
                "level": log_level,
                "handlers": ["stdout"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "WARNING",
                "handlers": ["stdout"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["stdout"],
                "propagate": False,
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["stdout"],
        },
    }

    # Set up non-blocking Better Stack log shipping via QueueHandler+QueueListener
    queue_listener: Optional[logging.handlers.QueueListener] = None
    if logtail_token:
        try:
            from logtail import LogtailHandler

            log_queue: queue.Queue = queue.Queue(-1)  # Unlimited size
            logtail_handler = LogtailHandler(source_token=logtail_token)
            logtail_handler.addFilter(
                _build_correlation_filter()
            )
            queue_listener = logging.handlers.QueueListener(
                log_queue,
                logtail_handler,
                respect_handler_level=True,
            )
            queue_listener.start()

            # Register cleanup on process exit
            atexit.register(queue_listener.stop)

            # Add the queue handler to config
            config["handlers"]["logtail_queue"] = {
                "class": "logging.handlers.QueueHandler",
                "queue": log_queue,
                "filters": ["correlation_id"],
            }
            # Add logtail handler to all relevant loggers
            config["loggers"]["ra_tracker"]["handlers"].append("logtail_queue")
            config["root"]["handlers"].append("logtail_queue")
        except Exception as exc:
            # Better Stack setup failed — log to stdout only, don't crash app
            logging.warning(f"Failed to configure Better Stack logging: {exc}")

    logging.config.dictConfig(config)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    return queue_listener


def _build_correlation_filter() -> logging.Filter:
    """Return a CorrelationIdFilter instance for use outside of dictConfig."""
    from asgi_correlation_id import CorrelationIdFilter

    return CorrelationIdFilter(uuid_length=32, default_value="-")
