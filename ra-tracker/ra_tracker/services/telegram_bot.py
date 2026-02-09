"""Telegram bot service for user linking and notification control."""

import logging
import asyncio
import threading
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..config import get_config
from ..database import get_db

logger = logging.getLogger(__name__)

# Global bot application instance
_bot_app: Optional[Application] = None
_bot_thread: Optional[threading.Thread] = None


async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /link CODE - link Telegram to RA Tracker account."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /link YOUR_CODE\n\n"
            "Get your code from Rave Tracker Settings > Notifications > Link Telegram"
        )
        return

    code = context.args[0]
    chat_id = update.effective_chat.id
    db = get_db()

    # Get and validate link code
    link_record = db.get_telegram_link_code(code)

    if not link_record:
        await update.message.reply_text(
            "Code not found.\n\n"
            "Please check the code and try again, or generate a new one from Settings."
        )
        return

    if link_record.get("used_at"):
        await update.message.reply_text(
            "This code has already been used.\n\n"
            "Please generate a new code from Rave Tracker Settings."
        )
        return

    if link_record["expires_at"] < datetime.now():
        await update.message.reply_text(
            "This code has expired.\n\n"
            "Please generate a new code from Rave Tracker Settings."
        )
        return

    user_id = link_record["user_id"]

    # Check if user already has a telegram linked
    user = db.get_user_by_id(user_id)
    if user and user.telegram_chat_id and user.telegram_chat_id != chat_id:
        await update.message.reply_text(
            "Your Rave Tracker account is already linked to a different Telegram account.\n\n"
            "To change, first unlink from Settings, then link again."
        )
        return

    # Link successful
    db.update_user_telegram(user_id, chat_id)
    db.set_user_telegram_enabled(user_id, True)
    db.mark_link_code_used(code)

    await update.message.reply_text(
        "Linked successfully! You'll receive event notifications here.\n\n"
        "Commands:\n"
        "/stop - Disable notifications\n"
        "/start - Re-enable notifications"
    )
    logger.info(f"User {user_id} linked Telegram chat {chat_id}")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop - disable Telegram notifications."""
    chat_id = update.effective_chat.id
    db = get_db()

    user = db.get_user_by_telegram_chat_id(chat_id)

    if not user:
        await update.message.reply_text(
            "This Telegram account is not linked to any Rave Tracker account.\n\n"
            "To link, visit Rave Tracker Settings > Notifications > Link Telegram"
        )
        return

    db.set_user_telegram_enabled(user.id, False)

    await update.message.reply_text(
        "Telegram notifications disabled.\n\n"
        "To re-enable:\n"
        "- Send /start here, OR\n"
        "- Toggle on in Rave Tracker Settings"
    )
    logger.info(f"User {user.id} disabled Telegram notifications via /stop")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start - re-enable notifications or show welcome."""
    chat_id = update.effective_chat.id
    db = get_db()

    user = db.get_user_by_telegram_chat_id(chat_id)

    if user:
        # Already linked - re-enable notifications
        db.set_user_telegram_enabled(user.id, True)
        await update.message.reply_text(
            "Telegram notifications re-enabled!\n\n"
            "You'll receive event alerts here when matches are found."
        )
        logger.info(f"User {user.id} re-enabled Telegram notifications via /start")
    else:
        # Not linked - show welcome
        await update.message.reply_text(
            "Welcome to Rave Tracker Bot!\n\n"
            "To link your account:\n"
            "1. Log in to Rave Tracker\n"
            "2. Go to Settings > Notifications\n"
            "3. Click 'Link Telegram'\n"
            "4. Send the code here with /link CODE"
        )


def _build_application() -> Application:
    """Build the bot application with handlers."""
    config = get_config()

    if not config.telegram.bot_token:
        raise ValueError("Telegram bot token not configured")

    app = Application.builder().token(config.telegram.bot_token).build()

    # Register command handlers
    app.add_handler(CommandHandler("link", link_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("start", start_command))

    return app


def _run_polling_in_thread():
    """Run bot polling in a new event loop (for thread safety)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        app = _build_application()
        logger.info("Starting Telegram bot polling...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")


def start_bot_polling():
    """Start the bot in polling mode in a background thread."""
    global _bot_thread

    config = get_config()
    if not config.telegram.bot_token:
        logger.warning("Telegram bot token not configured, skipping bot startup")
        return

    if config.telegram.use_webhook:
        logger.info("Webhook mode enabled, not starting polling")
        return

    # Start polling in background thread (daemon=True for clean shutdown)
    _bot_thread = threading.Thread(target=_run_polling_in_thread, daemon=True)
    _bot_thread.start()
    logger.info("Telegram bot polling started in background thread")


def stop_bot():
    """Stop the bot (for clean shutdown)."""
    global _bot_app, _bot_thread

    # Thread will terminate on app shutdown since daemon=True
    _bot_app = None
    _bot_thread = None
    logger.info("Telegram bot stopped")


def get_bot_application() -> Optional[Application]:
    """Get the global bot application (for webhook mode)."""
    global _bot_app
    if _bot_app is None:
        config = get_config()
        if config.telegram.bot_token and config.telegram.use_webhook:
            _bot_app = _build_application()
    return _bot_app
