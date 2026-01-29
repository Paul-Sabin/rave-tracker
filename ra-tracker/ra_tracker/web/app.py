"""FastAPI application for RA Tracker web UI."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routes import router
from .admin import admin_router

logger = logging.getLogger(__name__)

# Get template directory path
TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="RA Tracker",
        description="Track ra.co events and get Telegram notifications",
        version="0.1.0",
    )

    # Set up Jinja2 templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Store templates in app state for access in routes
    app.state.templates = templates

    # Include routes
    app.include_router(router)
    app.include_router(admin_router)

    return app


# Create the app instance
app = create_app()
