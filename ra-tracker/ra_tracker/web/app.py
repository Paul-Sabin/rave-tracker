"""FastAPI application for RA Tracker web UI."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi.errors import RateLimitExceeded

from telegram import Update

from .rate_limit import limiter

from .routes import router
from .admin import admin_router
from .csrf import CSRFMiddleware
from ..services.telegram_bot import start_bot_polling, stop_bot, get_bot_application
from ..config import get_config

logger = logging.getLogger(__name__)

# Get template directory path
TEMPLATES_DIR = Path(__file__).parent / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - start/stop bot."""
    config = get_config()

    # Start bot polling if not using webhooks
    if config.telegram.bot_token and not config.telegram.use_webhook:
        start_bot_polling()

    # If using webhooks, set up webhook URL
    if config.telegram.bot_token and config.telegram.use_webhook:
        bot_app = get_bot_application()
        if bot_app and config.telegram.webhook_url:
            try:
                await bot_app.bot.set_webhook(
                    url=config.telegram.webhook_url,
                    secret_token=config.telegram.webhook_secret or None
                )
                logger.info(f"Telegram webhook set: {config.telegram.webhook_url}")
            except Exception as e:
                logger.error(f"Failed to set webhook: {e}")

    yield

    # Cleanup
    stop_bot()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Rave Tracker",
        description="Track ra.co events and get Telegram notifications",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CSRF protection middleware
    app.add_middleware(CSRFMiddleware)

    # Set up Jinja2 templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Store templates in app state for access in routes
    app.state.templates = templates

    # Register rate limiter state
    app.state.limiter = limiter

    # Add custom rate limit exceeded handler
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        """Custom handler for rate limit exceeded - return friendly error page."""
        templates = app.state.templates

        # For login page, show user-friendly message
        if "/login" in str(request.url):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "csrf_token": getattr(request.state, 'csrf_token', ''),
                "error": "Too many login attempts. Please try again in a few minutes.",
                "email": "",
            }, status_code=429)

        # For other pages, return JSON error
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": "900"}  # 15 minutes
        )

    # Include routes
    app.include_router(router)
    app.include_router(admin_router)

    # Add webhook endpoint for Telegram (only used if webhook mode enabled)
    @app.post("/telegram/webhook")
    async def telegram_webhook(request: Request):
        """Receive Telegram updates via webhook."""
        config = get_config()

        # Verify secret token if configured
        if config.telegram.webhook_secret:
            secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if secret != config.telegram.webhook_secret:
                logger.warning("Invalid webhook secret token")
                return Response(status_code=403)

        bot_app = get_bot_application()
        if not bot_app:
            return Response(status_code=500)

        try:
            data = await request.json()
            update = Update.de_json(data, bot_app.bot)
            await bot_app.process_update(update)
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")

        return Response(status_code=200)

    return app


# Create the app instance
app = create_app()
