"""Route-level tests for verification and password-reset send failures
(Phase 20.1, plan 20.1-02).

Success Criteria 2 and 3 from ROADMAP.md Phase 20.1: a failed send must surface to the
user instead of claiming success, and must be distinguishable in the audit log. The send
functions are monkeypatched, so no mail is ever attempted.
"""

import pytest

from tests.conftest import VERIFIED_EMAIL, PASSWORD

FAILURE_TEXT = "verification email just now"  # Jinja2 autoescapes the apostrophe in
# VERIFICATION_SEND_FAILED_MESSAGE ("couldn't" -> "couldn&#39;t"), so this substring
# avoids the apostrophe while still uniquely identifying the failure copy.
SUCCESS_TEXT = "Verification email sent!"
RESET_TEXT = "If an account exists with that email"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """POST /verify-email/resend is 3/hour and /forgot-password is 3/hour per email,
    both held in module-level singletons that outlive a single test."""
    from ra_tracker.web.rate_limit import limiter, reset_limiter
    limiter.reset()
    reset_limiter._attempts.clear()
    yield
    limiter.reset()
    reset_limiter._attempts.clear()


async def _send_false(*args, **kwargs):
    return False


async def _send_true(*args, **kwargs):
    return True


def _csrf_post(client, get_path, post_path, data):
    """GET to seed the csrftoken cookie, then POST it back (double-submit CSRF)."""
    client.get(get_path)
    token = client.cookies.get("csrftoken")
    assert token, "CSRF middleware did not set a csrftoken cookie"
    return client.post(post_path, data={**data, "csrf_token": token})


# --- Criterion 2: the user is told the truth ---

def test_resend_success_shows_sent_message(monkeypatch, unverified_client):
    monkeypatch.setattr("ra_tracker.web.routes.send_verification_email", _send_true)
    response = _csrf_post(unverified_client, "/verify-email", "/verify-email/resend", {})
    assert SUCCESS_TEXT in response.text


def test_resend_failure_does_not_claim_success(monkeypatch, unverified_client):
    monkeypatch.setattr("ra_tracker.web.routes.send_verification_email", _send_false)
    response = _csrf_post(unverified_client, "/verify-email", "/verify-email/resend", {})
    assert SUCCESS_TEXT not in response.text


def test_resend_failure_shows_error_text(monkeypatch, unverified_client):
    monkeypatch.setattr("ra_tracker.web.routes.send_verification_email", _send_false)
    response = _csrf_post(unverified_client, "/verify-email", "/verify-email/resend", {})
    assert FAILURE_TEXT in response.text


def test_verify_email_page_shows_error_only_with_send_failed_param(unverified_client):
    assert FAILURE_TEXT in unverified_client.get("/verify-email?send_failed=1").text
    assert FAILURE_TEXT not in unverified_client.get("/verify-email").text


def test_registration_send_failure_redirects_with_send_failed_param(monkeypatch, client):
    monkeypatch.setattr("ra_tracker.web.routes.send_verification_email", _send_false)
    response = _csrf_post(client, "/register", "/register", {
        "email": "brand-new@example.test",
        "password": "correct-horse-battery-staple-9",
        "display_name": "New Tester",
        "consent": "on",
    })
    assert response.status_code == 303
    assert response.headers["location"] == "/verify-email?send_failed=1"


def test_registration_send_success_redirects_without_param(monkeypatch, client):
    monkeypatch.setattr("ra_tracker.web.routes.send_verification_email", _send_true)
    response = _csrf_post(client, "/register", "/register", {
        "email": "another-new@example.test",
        "password": "correct-horse-battery-staple-9",
        "display_name": "New Tester Two",
        "consent": "on",
    })
    assert response.status_code == 303
    assert response.headers["location"] == "/verify-email"


# --- Criterion 3: the audit log distinguishes the two outcomes ---

def test_resend_failure_logs_only_the_failure_event(monkeypatch, unverified_client, db):
    monkeypatch.setattr("ra_tracker.web.routes.send_verification_email", _send_false)
    _csrf_post(unverified_client, "/verify-email", "/verify-email/resend", {})
    assert db.get_audit_logs(event_type="auth.verification_send_failed")
    assert db.get_audit_logs(event_type="auth.verification_sent") == []


def test_resend_success_logs_only_the_sent_event(monkeypatch, unverified_client, db):
    monkeypatch.setattr("ra_tracker.web.routes.send_verification_email", _send_true)
    _csrf_post(unverified_client, "/verify-email", "/verify-email/resend", {})
    assert db.get_audit_logs(event_type="auth.verification_sent")
    assert db.get_audit_logs(event_type="auth.verification_send_failed") == []


def test_password_reset_send_failure_is_silent_to_user_but_logged(
    monkeypatch, client, verified_user, db
):
    monkeypatch.setattr("ra_tracker.web.routes.send_password_reset_email", _send_false)
    response = _csrf_post(client, "/forgot-password", "/forgot-password", {
        "email": VERIFIED_EMAIL,
    })
    assert RESET_TEXT in response.text
    assert FAILURE_TEXT not in response.text
    assert db.get_audit_logs(event_type="password.reset_send_failed")
    assert db.get_audit_logs(event_type="password.reset_requested") == []
