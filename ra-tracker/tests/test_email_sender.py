"""Unit tests for the Brevo HTTP API email transport (Phase 20.1, plan 20.1-01).

These cover the transport contract without ever touching the network: requests.post
is patched, so no Brevo credential is needed and no mail can leave the machine.
"""

import asyncio
import logging
from unittest.mock import MagicMock, patch

import pytest

from ra_tracker.config import Config, set_config
from ra_tracker.services import email_sender

API_KEY = "test-brevo-api-key"
SMTP_PASSWORD = "test-smtp-password"


def _config(*, api_key: str) -> Config:
    """A Config with the Brevo HTTP API transport selected."""
    cfg = Config()
    cfg.email.use_api = True
    cfg.email.api_key = api_key
    cfg.email.password = SMTP_PASSWORD       # present, and must never be used as api-key
    cfg.email.from_address = "sender@example.test"
    cfg.email.from_name = "Rave Tracker"
    cfg.app.secret_key = "test-secret-key-not-a-real-secret"
    cfg.app.base_url = "http://testserver"
    return cfg


@pytest.fixture
def api_config():
    """EMAIL_USE_API=true with a real-looking BREVO_API_KEY."""
    set_config(_config(api_key=API_KEY))
    yield
    set_config(None)


@pytest.fixture
def smtp_password_only_config():
    """EMAIL_USE_API=true with NO BREVO_API_KEY - only the SMTP password."""
    set_config(_config(api_key=""))
    yield
    set_config(None)


def _response(status_code: int, text: str = ""):
    return MagicMock(status_code=status_code, text=text)


# --- Criterion SC-4: successful send routes through the Brevo API with the right credential ---

def test_send_via_api_success_returns_true(api_config):
    with patch.object(email_sender.requests, "post", return_value=_response(201)) as post:
        result = email_sender._send_via_api("someone@example.test", "subject", "<p>html</p>")

    assert result is True
    assert post.call_count == 1
    args, kwargs = post.call_args
    assert args[0] == email_sender.BREVO_API_URL
    assert kwargs["headers"]["api-key"] == API_KEY
    assert set(kwargs["json"]) == {"sender", "to", "subject", "htmlContent"}


# --- Criterion SC-2: a failed send returns False, never raises, never reports success ---

def test_send_via_api_non_2xx_returns_false(api_config):
    with patch.object(email_sender.requests, "post", return_value=_response(401, "Unauthorized")):
        result = email_sender._send_via_api("someone@example.test", "subject", "<p>html</p>")

    assert result is False


def test_send_via_api_request_exception_returns_false(api_config):
    with patch.object(email_sender.requests, "post", side_effect=Exception("boom")):
        result = email_sender._send_via_api("someone@example.test", "subject", "<p>html</p>")

    assert result is False


# --- Pitfall 1 proof: the SMTP password must never be used as the Brevo API key ---

def test_send_via_api_without_api_key_does_not_call_brevo(smtp_password_only_config):
    with patch.object(email_sender.requests, "post", return_value=_response(201)) as post:
        result = email_sender._send_via_api("someone@example.test", "subject", "<p>html</p>")

    assert result is False
    assert post.call_count == 0


def test_is_email_configured_false_when_only_smtp_password_set(smtp_password_only_config):
    assert email_sender.is_email_configured() is False


def test_is_email_configured_true_with_api_key(api_config):
    assert email_sender.is_email_configured() is True


# --- Criterion SC-4: all five senders route through the API transport ---

def test_all_senders_use_api_path_when_use_api_true(api_config):
    calls = []

    def _recorder(to_email, subject, html_content):
        calls.append((to_email, subject))
        return True

    with patch.object(email_sender, "_send_via_api", _recorder):
        results = [
            asyncio.run(email_sender.send_verification_email("a@example.test", 1, "Tester")),
            asyncio.run(email_sender.send_password_reset_email("a@example.test", 1)),
            asyncio.run(email_sender.send_deletion_confirmation_email("a@example.test", "Tester", "2026-09-30")),
            asyncio.run(email_sender.send_recovery_confirmation_email("a@example.test", "Tester")),
            asyncio.run(email_sender.send_notification_email("a@example.test", 1, [])),
        ]

    assert len(calls) == 5
    assert all(r is True for r in results)


def test_senders_return_false_when_api_send_fails(api_config):
    calls = []

    def _recorder(to_email, subject, html_content):
        calls.append((to_email, subject))
        return False

    with patch.object(email_sender, "_send_via_api", _recorder):
        results = [
            asyncio.run(email_sender.send_verification_email("a@example.test", 1, "Tester")),
            asyncio.run(email_sender.send_password_reset_email("a@example.test", 1)),
            asyncio.run(email_sender.send_deletion_confirmation_email("a@example.test", "Tester", "2026-09-30")),
            asyncio.run(email_sender.send_recovery_confirmation_email("a@example.test", "Tester")),
            asyncio.run(email_sender.send_notification_email("a@example.test", 1, [])),
        ]

    assert len(calls) == 5
    assert all(r is False for r in results)


# --- Threat T-20.1-01: the Brevo API key must never appear in any log record ---

def test_api_key_never_logged(api_config, caplog):
    with caplog.at_level(logging.ERROR):
        with patch.object(email_sender.requests, "post", return_value=_response(401, "Unauthorized")):
            email_sender._send_via_api("someone@example.test", "subject", "<p>html</p>")

    assert API_KEY not in caplog.text
