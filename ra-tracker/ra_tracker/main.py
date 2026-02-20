"""Main entry point for RA Tracker."""

import argparse
import logging
import signal
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from .config import Config, get_config, set_config
from .database import Database, get_db, set_db
from .scheduler.jobs import start_scheduler, stop_scheduler, run_fetch_now

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Set up logging configuration using the observability module.

    Called early in main() before config is fully loaded, so it uses
    environment variables or safe defaults. The lifespan context in app.py
    will reconfigure logging with the full config when gunicorn starts.
    """
    from .observability.logging_config import setup_logging as obs_setup_logging

    try:
        from .config import get_config
        config = get_config()
        environment = config.observability.environment
        log_level = "DEBUG" if verbose else config.observability.log_level
        logtail_token = config.observability.logtail_token
    except Exception:
        # Config not loaded yet — use environment variables or safe defaults
        import os
        environment = os.environ.get("ENVIRONMENT", "development")
        log_level = "DEBUG" if verbose else os.environ.get("LOG_LEVEL", "INFO")
        logtail_token = ""

    obs_setup_logging(
        environment=environment,
        log_level=log_level,
        logtail_token=logtail_token,
    )


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info("Shutdown signal received, stopping...")
    stop_scheduler()
    sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="RA.co Event Tracker")
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Run a single fetch and exit (no web server)",
    )
    parser.add_argument(
        "--no-scheduler",
        action="store_true",
        help="Disable the scheduler (web server only)",
    )
    parser.add_argument(
        "--scheduler-only",
        action="store_true",
        help="Run scheduler only (no web server). Use for dedicated scheduler process.",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Web server host (overrides config)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Web server port (overrides config)",
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.verbose)
    logger.info("Starting RA Tracker")

    # Load environment variables from .env file (if present)
    load_dotenv()

    # Load configuration (env vars override config file values)
    config = Config.load(args.config)
    set_config(config)

    # Override config with command line args
    if args.host:
        config.web.host = args.host
    if args.port:
        config.web.port = args.port

    # Initialize database
    db = Database()
    db.init_schema()
    set_db(db)
    logger.info(f"Database initialized at {config.database.path}")

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Scheduler-only mode (for production: separate scheduler process)
    if args.scheduler_only:
        logger.info("Running in scheduler-only mode (no web server)")
        start_scheduler()
        logger.info(f"Scheduler started (fetch every {config.scheduler.fetch_interval_hours} hours)")
        logger.info("Scheduler running. Press Ctrl+C to stop.")
        # Block until signal received
        try:
            signal.pause()  # Unix only
        except AttributeError:
            # Windows fallback
            import time
            while True:
                time.sleep(3600)
        return

    # Fetch-only mode
    if args.fetch_only:
        logger.info("Running single fetch...")
        run_fetch_now()
        logger.info("Fetch complete")
        return

    # Start scheduler
    if not args.no_scheduler:
        start_scheduler()
        logger.info(f"Scheduler started (fetch every {config.scheduler.fetch_interval_hours} hours)")

    # Start web server
    logger.info(f"Starting web server at http://{config.web.host}:{config.web.port}")

    try:
        uvicorn.run(
            "ra_tracker.web.app:app",
            host=config.web.host,
            port=config.web.port,
            log_level="info" if args.verbose else "warning",
        )
    finally:
        stop_scheduler()


if __name__ == "__main__":
    main()
