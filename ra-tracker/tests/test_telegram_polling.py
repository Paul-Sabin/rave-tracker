"""Telegram polling must actually start, and exactly one process must do it.

Two separate faults, both visible in the production log:

    [ERRO] Bot polling error: set_wakeup_fd only works in main thread of the
           main interpreter
    RuntimeWarning: coroutine 'Updater.start_polling' was never awaited

1. Polling ran in a background thread, and run_polling's default behaviour is
   to install SIGINT/SIGTERM/SIGABRT handlers via loop.add_signal_handler,
   which is main-thread-only. It raised ValueError on every startup, so the
   bot never received a single update and nobody could link an account.

   This was invisible in development: PTB skips the signal block entirely on
   Windows and only builds the handler tuple on other platforms, so the bug
   existed solely on the Linux container.

2. The web app started polling from its FastAPI lifespan, which runs once per
   gunicorn worker. Telegram permits one getUpdates consumer per bot, so even
   with the thread fixed, two workers would knock each other off with 409
   Conflict. Ownership now sits with the process that owns the scheduler.
"""

import ast
import inspect
import platform
import signal
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from telegram._utils.defaultvalue import DEFAULT_NONE, DefaultValue
from telegram.ext import Application

from ra_tracker.services import telegram_bot

REPO = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# The mechanism
# --------------------------------------------------------------------------


def test_set_wakeup_fd_is_main_thread_only():
    """The root cause, pinned. If this ever stops raising, the kwarg below
    stops being necessary and this file can be revisited."""
    captured = {}

    def probe():
        try:
            signal.set_wakeup_fd(-1)
            captured["error"] = None
        except ValueError as e:
            captured["error"] = str(e)

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join()

    assert "main thread" in (captured["error"] or "")


def test_the_stop_signals_default_is_a_sentinel_not_none():
    """stop_signals=None is load-bearing, not a redundant restatement of the
    default. The signature renders the default as "None" because the sentinel
    stringifies that way, which makes the kwarg look safe to delete."""
    default = inspect.signature(Application.run_polling).parameters["stop_signals"].default

    assert default is DEFAULT_NONE
    assert default is not None
    assert isinstance(default, DefaultValue)


def test_the_default_installs_signal_handlers_off_windows():
    """Why production broke and development did not.

    Mirrors the branch in Application.__run: the sentinel survives on Windows
    and is replaced by a real tuple everywhere else, and only a real tuple
    reaches loop.add_signal_handler.
    """
    def would_install(stop_signals, system):
        if stop_signals is DEFAULT_NONE and system != "Windows":
            stop_signals = (signal.SIGINT, signal.SIGTERM, signal.SIGABRT)
        return not isinstance(stop_signals, DefaultValue) and bool(stop_signals)

    assert would_install(DEFAULT_NONE, "Linux") is True      # production
    assert would_install(DEFAULT_NONE, "Windows") is False   # development
    assert would_install(None, "Linux") is False             # the fix


# --------------------------------------------------------------------------
# The call the fix depends on
# --------------------------------------------------------------------------


@pytest.fixture
def built_application():
    """Patch out application construction, returning the mock it hands back."""
    app = MagicMock()
    with patch.object(telegram_bot, "_build_application", return_value=app):
        yield app


def test_polling_disables_ptb_signal_handling(built_application):
    """The fix itself. Without this kwarg the call dies on a Linux container."""
    telegram_bot._run_polling_in_thread()

    _args, kwargs = built_application.run_polling.call_args
    assert kwargs["stop_signals"] is None


def test_polling_still_asks_for_all_update_types(built_application):
    telegram_bot._run_polling_in_thread()

    _args, kwargs = built_application.run_polling.call_args
    assert kwargs["allowed_updates"] is not None


def test_a_polling_failure_is_logged_with_its_traceback(built_application, caplog):
    """The original log gave only the message, which is why this took a
    production log read to spot rather than a stack trace."""
    built_application.run_polling.side_effect = RuntimeError("boom")

    with caplog.at_level("ERROR"):
        telegram_bot._run_polling_in_thread()

    assert "Bot polling error" in caplog.text
    assert "RuntimeError" in caplog.text  # exc_info, not just str(e)


def test_polling_survives_being_started_off_the_main_thread(built_application):
    """End to end for the threading concern: start_bot_polling spawns a thread,
    and nothing in that thread may raise."""
    errors = []
    real_run = built_application.run_polling

    def record(*args, **kwargs):
        try:
            return real_run(*args, **kwargs)
        except Exception as e:  # pragma: no cover - would be the regression
            errors.append(e)
            raise

    built_application.run_polling = record

    thread = threading.Thread(target=telegram_bot._run_polling_in_thread)
    thread.start()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert errors == []


# --------------------------------------------------------------------------
# Who is allowed to poll
# --------------------------------------------------------------------------


def calls_in(path: Path, function_name: str) -> bool:
    """True if the module's source contains a call to the given name.

    Structural rather than behavioural because the invariant is structural:
    the web module must not reach this code path at all. A behavioural test
    would need the FastAPI lifespan, which the suite deliberately never
    enters, so it could pass while the call sat there unexecuted.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == function_name:
                return True
    return False


def test_the_web_app_never_starts_polling():
    """One call per gunicorn worker means several getUpdates consumers, and
    Telegram answers the losers with 409 Conflict."""
    assert calls_in(REPO / "ra_tracker" / "web" / "app.py", "start_bot_polling") is False


def test_the_entry_point_starts_polling():
    """main.py owns the scheduler, runs as a single instance, and so owns the bot."""
    assert calls_in(REPO / "ra_tracker" / "main.py", "start_bot_polling") is True


def test_the_entry_point_stops_the_bot_on_shutdown():
    assert calls_in(REPO / "ra_tracker" / "main.py", "stop_bot") is True


# --------------------------------------------------------------------------
# Existing guards that must keep working
# --------------------------------------------------------------------------


def test_no_polling_without_a_token():
    with patch.object(telegram_bot, "get_config") as get_config, \
            patch.object(telegram_bot, "threading") as fake_threading:
        get_config.return_value.telegram.bot_token = ""

        telegram_bot.start_bot_polling()

    assert fake_threading.Thread.call_count == 0


def test_no_polling_in_webhook_mode():
    """Webhook mode receives updates as HTTP requests; polling as well would
    mean two consumers again."""
    with patch.object(telegram_bot, "get_config") as get_config, \
            patch.object(telegram_bot, "threading") as fake_threading:
        get_config.return_value.telegram.bot_token = "123:abc"
        get_config.return_value.telegram.use_webhook = True

        telegram_bot.start_bot_polling()

    assert fake_threading.Thread.call_count == 0


def test_polling_starts_a_daemon_thread():
    """Daemon so the process can exit; it is also what handles shutdown now
    that PTB's own signal handling is switched off."""
    with patch.object(telegram_bot, "get_config") as get_config, \
            patch.object(telegram_bot, "threading") as fake_threading:
        get_config.return_value.telegram.bot_token = "123:abc"
        get_config.return_value.telegram.use_webhook = False

        telegram_bot.start_bot_polling()

    _args, kwargs = fake_threading.Thread.call_args
    assert kwargs["daemon"] is True
    assert fake_threading.Thread.return_value.start.called
