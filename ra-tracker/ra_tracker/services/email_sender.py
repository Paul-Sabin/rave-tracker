"""Email notification service using fastapi-mail and itsdangerous."""

import logging
from pathlib import Path
from typing import List, Tuple, Optional

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from ..config import get_config
from ..database import Event, Rule

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "web" / "templates" / "email"


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


def is_email_configured() -> bool:
    """Check if email sending is properly configured."""
    return _get_email_config() is not None


async def send_notification_email(
    user_email: str,
    user_id: int,
    events: List[Tuple[Event, List[Rule]]],
) -> bool:
    """Send notification email with event details.

    Args:
        user_email: Recipient email address
        user_id: User ID for unsubscribe token
        events: List of (Event, matching_rules) tuples

    Returns:
        True if sent successfully, False otherwise
    """
    conf = _get_email_config()
    if not conf:
        logger.warning("Email not configured, skipping send")
        return False

    config = get_config()
    unsubscribe_token = generate_unsubscribe_token(user_id)
    unsubscribe_url = f"{config.app.base_url}/unsubscribe?token={unsubscribe_token}"

    # Format events for template
    formatted_events = []
    for event, rules in events:
        # Format date
        date_str = event.date.strftime("%a %d %b %Y") if event.date else "Date TBA"
        time_str = event.start_time.strftime("%H:%M") if event.start_time else ""

        # Format matched rules with icons
        rule_matches = []
        for rule in rules:
            icon = "A" if rule.rule_type == "artist" else "V" if rule.rule_type == "venue" else "P"
            rule_matches.append(f"{icon}: {rule.target_name}")

        # Event URL
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

    # Build subject
    if len(events) == 1:
        subject = f"RA Tracker: New event - {events[0][0].title[:40]}"
    else:
        subject = f"RA Tracker: {len(events)} new event(s) found!"

    message = MessageSchema(
        subject=subject,
        recipients=[user_email],
        template_body={
            "events": formatted_events,
            "event_count": len(events),
            "unsubscribe_url": unsubscribe_url,
            "settings_url": f"{config.app.base_url}/settings",
        },
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
    """Send verification email with secure token link.

    Args:
        user_email: Recipient email address
        user_id: User ID for token generation
        display_name: User's display name for personalization

    Returns:
        True if sent successfully, False otherwise
    """
    conf = _get_email_config()
    if not conf:
        logger.warning("Email not configured, skipping verification send")
        return False

    # Import here to avoid circular imports
    from ..web.verification import generate_verification_token

    config = get_config()
    token = generate_verification_token(user_id)
    verification_url = f"{config.app.base_url}/verify/{token}"

    message = MessageSchema(
        subject="Welcome to RA Tracker - verify your email",
        recipients=[user_email],
        template_body={
            "display_name": display_name,
            "verification_url": verification_url,
        },
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
