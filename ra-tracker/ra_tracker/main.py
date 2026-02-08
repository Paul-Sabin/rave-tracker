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
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Reduce noise from some libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


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
