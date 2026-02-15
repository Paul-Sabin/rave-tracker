"""Email notification service using fastapi-mail (SMTP) or Brevo HTTP API."""

import logging
from pathlib import Path
from typing import List, Tuple, Optional

import requests
from jinja2 import Environment, FileSystemLoader
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from ..config import get_config
from ..database import Event, Rule

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "web" / "templates" / "email"

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _get_unsubscribe_serializer() -> URLSafeTimedSerializer:
    """Get serializer for unsubscribe tokens."""
    config = get_config()
    secret = config.app.secret_key
    if not secret:
        raise ValueError("app.secret_key not configured - required for email unsubscribe tokens")
    return URLSafeTimedSerializer(secret, salt="email-unsubscribe")


def generate_unsubscribe_token(user_id: int) -> str:
    """Generate a signed unsubscribe token for a user.

    Token is URL-safe and contains user_id. Valid for 30 days by default.
    """
    serializer = _get_unsubscribe_serializer()
    return serializer.dumps({"user_id": user_id})


def verify_unsubscribe_token(token: str, max_age_days: int = 30) -> Optional[dict]:
    """Verify and decode an unsubscribe token.

    Args:
        token: The signed token from URL
        max_age_days: Maximum age in days (default 30)

    Returns:
        Dict with user_id if valid, None if invalid/expired

    Raises:
        SignatureExpired: If token has expired
        BadSignature: If token is tampered
    """
    serializer = _get_unsubscribe_serializer()
    max_age_seconds = max_age_days * 24 * 60 * 60
    return serializer.loads(token, max_age=max_age_seconds)


def _get_email_config() -> Optional[ConnectionConfig]:
    """Get email configuration, or None if not configured."""
    config = get_config()

    if not config.email.server or not config.email.username:
        return None

    return ConnectionConfig(
        MAIL_USERNAME=config.email.username,
        MAIL_PASSWORD=config.email.password,
        MAIL_FROM=config.email.from_address or config.email.username,
        MAIL_PORT=config.email.port,
        MAIL_SERVER=config.email.server,
        MAIL_FROM_NAME=config.email.from_name,
        MAIL_STARTTLS=config.email.starttls,
        MAIL_SSL_TLS=config.email.ssl_tls,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
        TEMPLATE_FOLDER=str(TEMPLATE_DIR),
    )


def _render_template(template_name: str, context: dict) -> str:
    """Render a Jinja2 email template to HTML string."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template(template_name)
    return template.render(**context)


def _send_via_api(to_email: str, subject: str, html_content: str) -> bool:
    """Send email via Brevo HTTP API."""
    config = get_config()
    api_key = config.email.api_key or config.email.password

    if not api_key:
        logger.warning("Brevo API key not configured (set BREVO_API_KEY)")
        return False

    from_email = config.email.from_address or config.email.username
    from_name = config.email.from_name

    payload = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }

    try:
        resp = requests.post(
            BREVO_API_URL,
            json=payload,
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            logger.info(f"Sent email via Brevo API to {to_email}")
            return True
        else:
            logger.error(f"Brevo API error {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send email via Brevo API to {to_email}: {e}")
        return False


def is_email_configured() -> bool:
    """Check if email sending is properly configured."""
    config = get_config()
    if config.email.use_api:
        api_key = config.email.api_key or config.email.password
        return bool(api_key and (config.email.from_address or config.email.username))
    return _get_email_config() is not None


async def send_notification_email(
    user_email: str,
    user_id: int,
    events: List[Tuple[Event, List[Rule]]],
) -> bool:
    """Send notification email with event details."""
    config = get_config()
    unsubscribe_token = generate_unsubscribe_token(user_id)
    unsubscribe_url = f"{config.app.base_url}/unsubscribe?token={unsubscribe_token}"

    # Format events for template
    formatted_events = []
    for event, rules in events:
        date_str = event.date.strftime("%a %d %b %Y") if event.date else "Date TBA"
        time_str = event.start_time.strftime("%H:%M") if event.start_time else ""

        rule_matches = []
        for rule in rules:
            icon = "A" if rule.rule_type == "artist" else "V" if rule.rule_type == "venue" else "P"
            rule_matches.append(f"{icon}: {rule.target_name}")

        url = event.content_url
        if url and not url.startswith("http"):
            url = f"https://ra.co{url}"

        formatted_events.append({
            "title": event.title,
            "date": date_str,
            "time": time_str,
            "venue": event.venue_name or "Venue TBA",
            "area": event.area_name or "",
            "url": url,
            "rules": rule_matches,
        })

    if len(events) == 1:
        subject = f"Rave Tracker: New event - {events[0][0].title[:40]}"
    else:
        subject = f"Rave Tracker: {len(events)} new event(s) found!"

    template_body = {
        "events": formatted_events,
        "event_count": len(events),
        "unsubscribe_url": unsubscribe_url,
        "settings_url": f"{config.app.base_url}/settings",
    }

    if config.email.use_api:
        html = _render_template("notification.html", template_body)
        return _send_via_api(user_email, subject, html)

    # SMTP fallback
    conf = _get_email_config()
    if not conf:
        logger.warning("Email not configured, skipping send")
        return False

    message = MessageSchema(
        subject=subject,
        recipients=[user_email],
        template_body=template_body,
        subtype=MessageType.html,
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message, template_name="notification.html")
        logger.info(f"Sent notification email to {user_email} with {len(events)} events")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {user_email}: {e}")
        return False


async def send_verification_email(
    user_email: str,
    user_id: int,
    display_name: str,
) -> bool:
    """Send verification email with secure token link."""
    from ..web.verification import generate_verification_token

    config = get_config()
    token = generate_verification_token(user_id)
    verification_url = f"{config.app.base_url}/verify/{token}"

    subject = "Welcome to Rave Tracker - verify your email"
    template_body = {
        "display_name": display_name,
        "verification_url": verification_url,
    }

    if config.email.use_api:
        html = _render_template("verification.html", template_body)
        return _send_via_api(user_email, subject, html)

    # SMTP fallback
    conf = _get_email_config()
    if not conf:
        logger.warning("Email not configured, skipping verification send")
        return False

    message = MessageSchema(
        subject=subject,
        recipients=[user_email],
        template_body=template_body,
        subtype=MessageType.html,
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message, template_name="verification.html")
        logger.info(f"Sent verification email to {user_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification to {user_email}: {e}")
        return False


async def send_password_reset_email(
    user_email: str,
    user_id: int,
) -> bool:
    """Send password reset email with secure token link."""
    from ..web.password_reset import generate_reset_token

    config = get_config()
    token = generate_reset_token(user_id)
    reset_url = f"{config.app.base_url}/reset-password/{token}"

    subject = "Reset your password"
    template_body = {"reset_url": reset_url}

    if config.email.use_api:
        html = _render_template("password_reset.html", template_body)
        return _send_via_api(user_email, subject, html)

    # SMTP fallback
    conf = _get_email_config()
    if not conf:
        logger.warning("Email not configured, skipping reset email send")
        return False

    message = MessageSchema(
        subject=subject,
        recipients=[user_email],
        template_body=template_body,
        subtype=MessageType.html,
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message, template_name="password_reset.html")
        logger.info(f"Sent password reset email to {user_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email to {user_email}: {e}")
        return False


async def send_deletion_confirmation_email(
    email: str,
    display_name: Optional[str],
    scheduled_purge_date: str,
) -> bool:
    """Send account deletion confirmation email."""
    subject = "Rave Tracker - Account Deletion Requested"
    template_body = {
        "display_name": display_name,
        "scheduled_purge_date": scheduled_purge_date,
    }

    config = get_config()
    if config.email.use_api:
        html = _render_template("account_deleted.html", template_body)
        return _send_via_api(email, subject, html)

    # SMTP fallback
    conf = _get_email_config()
    if not conf:
        logger.warning("Email not configured, skipping deletion confirmation send")
        return False

    message = MessageSchema(
        subject=subject,
        recipients=[email],
        template_body=template_body,
        subtype=MessageType.html,
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message, template_name="account_deleted.html")
        logger.info(f"Sent deletion confirmation email to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send deletion confirmation to {email}: {e}")
        return False


async def send_recovery_confirmation_email(
    email: str,
    display_name: Optional[str],
) -> bool:
    """Send account recovery confirmation email."""
    subject = "Rave Tracker - Account Recovered"
    template_body = {"display_name": display_name}

    config = get_config()
    if config.email.use_api:
        html = _render_template("account_recovered.html", template_body)
        return _send_via_api(email, subject, html)

    # SMTP fallback
    conf = _get_email_config()
    if not conf:
        logger.warning("Email not configured, skipping recovery confirmation send")
        return False

    message = MessageSchema(
        subject=subject,
        recipients=[email],
        template_body=template_body,
        subtype=MessageType.html,
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message, template_name="account_recovered.html")
        logger.info(f"Sent recovery confirmation email to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send recovery confirmation to {email}: {e}")
        return False
