"""FastAPI routes for RA Tracker web UI - Simplified."""

import hashlib
import logging
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from .audit import log_audit_event
from .rate_limit import login_limiter, limiter, RESEND_RATE_LIMIT, reset_limiter
from .verification import generate_verification_token, verify_verification_token, get_user_id_from_expired_token
from .password_reset import generate_reset_token, verify_reset_token
from .password_validation import validate_password
from ..services.email_sender import send_verification_email, send_password_reset_email

from ..api.ra_client import RAClient
from ..config import get_config
from ..database import get_db, Rule, User, Event
from ..scheduler.jobs import run_fetch_now, get_scheduler_status
from ..services.notifier import Notifier
from ..services.email_sender import verify_unsubscribe_token, is_email_configured, send_notification_email
from itsdangerous import SignatureExpired, BadSignature
from .auth import (
    create_user_session,
    set_session_cookie,
    clear_session_cookie,
    get_current_user,
    require_auth,
    require_verified_email,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_templates(request: Request):
    """Get templates from app state."""
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_verified_email)):
    """Main dashboard showing upcoming events for current user."""
    templates = get_templates(request)
    db = get_db()
    config = get_config()

    # Get user-scoped events, rules, and stats
    # Pass local_area_id for dashboard_mode filtering
    local_area_id = config.user.local_area_id
    events = db.get_upcoming_events_for_user(user.id, local_area_id=local_area_id)
    rules = db.get_all_rules(user_id=user.id)
    stats = db.get_user_stats(user.id)
    legacy_data = db.count_legacy_data(user.id)
    status = get_scheduler_status()

    # Group events by date
    events_by_date = {}
    for event in events:
        date_key = event.date.strftime("%a %d %b") if event.date else "TBA"
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "events": events,
            "events_by_date": events_by_date,
            "rules": rules,
            "stats": stats,
            "legacy_data": legacy_data,
            "scheduler_status": status,
            "local_area_id": config.user.local_area_id,
            "local_area_name": config.user.local_area_name,
            "has_local_area": bool(config.user.local_area_id),
        },
    )


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request, user: User = Depends(require_verified_email)):
    """Rules management page - shows only current user's rules."""
    templates = get_templates(request)
    db = get_db()

    rules = db.get_all_rules(user_id=user.id)

    # Group by type
    artists = [r for r in rules if r.rule_type == "artist"]
    venues = [r for r in rules if r.rule_type == "venue"]
    promoters = [r for r in rules if r.rule_type == "promoter"]

    return templates.TemplateResponse(
        "rules.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "rules": rules,
            "artists": artists,
            "venues": venues,
            "promoters": promoters,
        },
    )


@router.post("/rules/add")
async def add_rule(
    request: Request,
    user: User = Depends(require_verified_email),
    rule_type: str = Form(...),
    target_id: int = Form(...),
    target_name: str = Form(...),
):
    """Add a new tracking rule assigned to current user."""
    db = get_db()

    # Check for duplicate FOR THIS USER
    if db.rule_exists(rule_type, target_id, user_id=user.id):
        # Just redirect back, don't add duplicate
        return RedirectResponse(url="/rules", status_code=303)

    rule = Rule(
        id=None,
        rule_type=rule_type,
        target_id=target_id,
        target_name=target_name,
        is_active=True,
    )

    db.add_rule(rule, user_id=user.id)
    logger.info(f"Added {rule_type} rule for user {user.id}: {target_name} (ID: {target_id})")

    return RedirectResponse(url="/rules", status_code=303)


@router.post("/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: int, user: User = Depends(require_verified_email)):
    """Toggle a rule's active status. Verifies ownership first."""
    db = get_db()
    rule = db.get_rule_for_user(rule_id, user.id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.set_rule_active(rule_id, not rule.is_active)
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/rules/{rule_id}/notify-mode")
async def set_notify_mode(rule_id: int, user: User = Depends(require_verified_email), mode: str = Form(...)):
    """Set a rule's notification mode. Verifies ownership first."""
    db = get_db()
    rule = db.get_rule_for_user(rule_id, user.id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Validate mode
    valid_modes = ['all', 'local', 'none']
    if mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Must be one of: {valid_modes}")

    db.set_rule_notify_mode(rule_id, mode)
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/rules/{rule_id}/dashboard-mode")
async def set_dashboard_mode(rule_id: int, user: User = Depends(require_verified_email), mode: str = Form(...)):
    """Set a rule's dashboard mode. Verifies ownership first."""
    db = get_db()
    rule = db.get_rule_for_user(rule_id, user.id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Validate mode
    valid_modes = ['all', 'local', 'none']
    if mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Must be one of: {valid_modes}")

    db.set_rule_dashboard_mode(rule_id, mode)
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/rules/{rule_id}/delete")
async def delete_rule(rule_id: int, user: User = Depends(require_verified_email)):
    """Delete a rule. Verifies ownership first."""
    db = get_db()
    rule = db.get_rule_for_user(rule_id, user.id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete_rule(rule_id)
    return RedirectResponse(url="/rules", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: User = Depends(require_verified_email)):
    """Settings page."""
    templates = get_templates(request)
    config = get_config()
    db = get_db()

    # Refresh user data (might have been updated)
    user = db.get_user_by_id(user.id)

    # Mask the bot token
    bot_token = config.telegram.bot_token
    masked_token = ""
    if bot_token:
        if len(bot_token) > 10:
            masked_token = bot_token[:5] + "*" * (len(bot_token) - 10) + bot_token[-5:]
        else:
            masked_token = "*" * len(bot_token)

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "config": config,
            "masked_token": masked_token,
            "scheduler_status": get_scheduler_status(),
            "telegram_configured": bool(config.telegram.bot_token),
            "email_configured": is_email_configured(),
        },
    )


@router.post("/settings/save")
async def save_settings(
    request: Request,
    user: User = Depends(require_verified_email),
    bot_token: str = Form(""),
    chat_id: str = Form(""),
    fetch_interval_hours: int = Form(6),
    local_area_id: Optional[int] = Form(None),
    local_area_name: str = Form(""),
):
    """Save settings."""
    config = get_config()

    if bot_token and "*" not in bot_token:
        config.telegram.bot_token = bot_token

    if chat_id:
        config.telegram.chat_id = chat_id

    config.scheduler.fetch_interval_hours = fetch_interval_hours

    # Update local area settings
    config.user.local_area_id = local_area_id if local_area_id else None
    config.user.local_area_name = local_area_name

    config.save()

    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/test-telegram")
async def test_telegram(user: User = Depends(require_verified_email)):
    """Send a test Telegram message."""
    notifier = Notifier()
    try:
        success = notifier.send_test()
        if success:
            return {"status": "success", "message": "Test message sent!"}
        return {"status": "error", "message": "Failed to send"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/settings/telegram/link")
async def generate_telegram_link_code(request: Request, user: User = Depends(require_verified_email)):
    """Generate a new Telegram link code for the current user."""
    db = get_db()
    config = get_config()

    # Check if Telegram bot is configured
    if not config.telegram.bot_token:
        return {"success": False, "error": "Telegram bot not configured by admin"}

    # Check if already linked
    if user.telegram_chat_id:
        return {
            "success": False,
            "error": "Already linked. Unlink first to change Telegram account."
        }

    # Generate code (8 chars, URL-safe)
    code = secrets.token_urlsafe(6)[:8].upper()
    expires_at = datetime.now() + timedelta(hours=1)

    # Store code
    db.create_telegram_link_code(user.id, code, expires_at)

    return {
        "success": True,
        "code": code,
        "expires_in_minutes": 60,
    }


@router.post("/settings/telegram/unlink")
async def unlink_telegram(request: Request, user: User = Depends(require_verified_email)):
    """Unlink Telegram from user account."""
    db = get_db()

    db.update_user_telegram(user.id, None)
    db.set_user_telegram_enabled(user.id, False)

    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/notifications/telegram")
async def toggle_telegram_notifications(
    request: Request,
    user: User = Depends(require_verified_email),
    enabled: str = Form("off"),
):
    """Toggle Telegram notifications for current user."""
    db = get_db()

    # Refresh user to check telegram_chat_id
    user = db.get_user_by_id(user.id)

    # Can only enable if telegram is linked
    is_enabled = enabled == "on"
    if is_enabled and not user.telegram_chat_id:
        return RedirectResponse(url="/settings", status_code=303)

    db.set_user_telegram_enabled(user.id, is_enabled)
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/notifications/email")
async def toggle_email_notifications(
    request: Request,
    user: User = Depends(require_verified_email),
    enabled: str = Form("off"),
):
    """Toggle Email notifications for current user."""
    db = get_db()

    db.set_user_email_enabled(user.id, enabled == "on")
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/notifications/test")
async def test_notifications(request: Request, user: User = Depends(require_verified_email)):
    """Send a test notification to all enabled channels."""
    db = get_db()

    # Refresh user data
    user = db.get_user_by_id(user.id)
    results = []

    # Test Telegram
    if user.telegram_enabled and user.telegram_chat_id:
        notifier = Notifier()
        try:
            # Send test message to user's chat
            await notifier.bot.send_message(
                chat_id=user.telegram_chat_id,
                text="Test notification from RA Tracker - your Telegram is configured correctly!"
            )
            results.append({"channel": "telegram", "success": True})
        except Exception as e:
            results.append({"channel": "telegram", "success": False, "error": str(e)})

    # Test Email
    if user.email_enabled and is_email_configured():
        try:
            # Create a fake event for test
            test_event = Event(
                id=0,
                title="Test Event - RA Tracker Configuration",
                date=datetime.now().date(),
                venue_name="Test Venue",
                area_name="Test Area",
                content_url="https://ra.co",
            )
            test_rule = Rule(
                id=0,
                rule_type="artist",
                target_id=0,
                target_name="Test Artist",
            )
            success = await send_notification_email(
                user.email,
                user.id,
                [(test_event, [test_rule])],
            )
            results.append({"channel": "email", "success": success})
        except Exception as e:
            results.append({"channel": "email", "success": False, "error": str(e)})

    if not results:
        return {"success": False, "message": "No notification channels enabled"}

    all_success = all(r["success"] for r in results)
    return {
        "success": all_success,
        "results": results,
        "message": "Test notifications sent!" if all_success else "Some notifications failed"
    }


@router.post("/actions/fetch-now")
async def trigger_fetch(user: User = Depends(require_verified_email)):
    """Manually trigger a fetch."""
    run_fetch_now()
    return RedirectResponse(url="/", status_code=303)


# Search API endpoints
@router.get("/api/search/artists")
async def search_artists(q: str, user: User = Depends(require_verified_email)):
    """Search for artists on ra.co."""
    if len(q) < 2:
        return {"results": []}

    client = RAClient()
    try:
        artists = client.search_artists(q)
        return {"results": [{"id": a.id, "name": a.name} for a in artists]}
    except Exception as e:
        logger.error(f"Artist search failed: {e}")
        return {"results": [], "error": str(e)}


@router.get("/api/search/venues")
async def search_venues(q: str, user: User = Depends(require_verified_email)):
    """Search for venues on ra.co."""
    if len(q) < 2:
        return {"results": []}

    client = RAClient()
    try:
        venues = client.search_venues(q)
        return {"results": [{"id": v.id, "name": v.name} for v in venues]}
    except Exception as e:
        logger.error(f"Venue search failed: {e}")
        return {"results": [], "error": str(e)}


@router.get("/api/search/promoters")
async def search_promoters(q: str, user: User = Depends(require_verified_email)):
    """Search for promoters on ra.co."""
    if len(q) < 2:
        return {"results": []}

    client = RAClient()
    try:
        promoters = client.search_promoters(q)
        return {"results": [{"id": p.id, "name": p.name} for p in promoters]}
    except Exception as e:
        logger.error(f"Promoter search failed: {e}")
        return {"results": [], "error": str(e)}


@router.get("/api/search/areas")
async def search_areas(q: str, user: User = Depends(require_verified_email)):
    """Search for areas/cities on ra.co."""
    if len(q) < 2:
        return {"results": []}

    client = RAClient()
    try:
        areas = client.search_areas(q)
        return {"results": [{"id": a.id, "name": a.name} for a in areas]}
    except Exception as e:
        logger.error(f"Area search failed: {e}")
        return {"results": [], "error": str(e)}


@router.get("/api/status")
async def get_status(user: User = Depends(require_verified_email)):
    """Get current system status for the user."""
    db = get_db()
    return {
        "scheduler": get_scheduler_status(),
        **db.get_user_stats(user.id),
    }


@router.post("/api/rules/add")
async def api_add_rule(request: Request, user: User = Depends(require_verified_email)):
    """Add a new tracking rule via JSON API assigned to current user."""
    db = get_db()
    data = await request.json()

    rule_type = data.get("rule_type")
    target_id = data.get("target_id")
    target_name = data.get("target_name")

    if not all([rule_type, target_id, target_name]):
        return {"success": False, "error": "Missing required fields"}

    # Check for duplicate FOR THIS USER
    if db.rule_exists(rule_type, int(target_id), user_id=user.id):
        return {"success": False, "error": "You are already tracking this"}

    rule = Rule(
        id=None,
        rule_type=rule_type,
        target_id=int(target_id),
        target_name=target_name,
        is_active=True,
    )

    rule_id = db.add_rule(rule, user_id=user.id)
    logger.info(f"Added {rule_type} rule via API for user {user.id}: {target_name} (ID: {target_id})")

    return {"success": True, "rule_id": rule_id, "message": f"Now tracking {target_name}"}


@router.get("/api/rules/check")
async def api_check_rule(rule_type: str, target_id: int, user: User = Depends(require_verified_email)):
    """Check if a rule already exists for this user."""
    db = get_db()
    exists = db.rule_exists(rule_type, target_id, user_id=user.id)
    return {"exists": exists}


# Authentication routes


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user),
    verified: Optional[str] = None,
    message: Optional[str] = None,
):
    """Login page. Redirect to dashboard if already logged in."""
    if user:
        return RedirectResponse(url="/", status_code=303)
    templates = get_templates(request)

    display_message = message  # From query param (e.g., after password reset)
    if verified == "1":
        display_message = "Email verified! You can now log in."
    elif verified == "already":
        display_message = "Email already verified. Please log in."

    return templates.TemplateResponse("login.html", {
        "request": request,
        "user": user,
        "csrf_token": getattr(request.state, 'csrf_token', ''),
        "message": display_message,
    })


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Process login form with dual IP/email rate limiting."""
    templates = get_templates(request)
    db = get_db()
    config = get_config()

    # Check dual rate limit BEFORE any other processing
    # This runs before password check to prevent timing attacks
    allowed, limit_type = login_limiter.check_rate_limit(request, email)
    if not allowed:
        log_audit_event(
            "auth.login_rate_limited",
            request,
            details={
                "email_hash": hashlib.sha256(email.lower().encode()).hexdigest()[:16],
                "limit_type": limit_type,
            },
        )
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Too many login attempts. Please try again in a few minutes.",
            "email": email,
        }, status_code=429)

    user = db.get_user_by_email(email)
    if not user:
        # Record failed attempt for BOTH IP and email
        login_limiter.record_failed_attempt(request, email)
        log_audit_event(
            "auth.login_failure",
            request,
            details={"email": email, "reason": "unknown_email"},
        )
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Invalid email or password",
            "email": email,
        })

    valid, new_hash = db.verify_password(user.password_hash, password)
    if not valid:
        # Record failed attempt for BOTH IP and email
        login_limiter.record_failed_attempt(request, email)
        log_audit_event(
            "auth.login_failure",
            request,
            user_id=user.id,
            details={"reason": "invalid_password"},
        )
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Invalid email or password",
            "email": email,
        })

    # SUCCESS - clear rate limit counters for this IP and email
    login_limiter.clear_on_success(request, email)
    log_audit_event("auth.login_success", request, user_id=user.id)

    # Rehash if needed (algorithm upgrade)
    if new_hash:
        db.update_user_password_hash(user.id, new_hash)

    # Create new session
    token, expires_at = create_user_session(user.id)

    # Check if email verified
    if not user.email_verified:
        # Send verification email for unverified existing users
        await send_verification_email(user.email, user.id, user.display_name)
        log_audit_event("auth.verification_sent", request, user_id=user.id,
                       details={"trigger": "unverified_login"})
        response = RedirectResponse(url="/verify-email", status_code=303)
    else:
        response = RedirectResponse(url="/", status_code=303)

    set_session_cookie(response, token, expires_at, request=request)
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    """Registration page. Redirect to dashboard if already logged in."""
    if user:
        return RedirectResponse(url="/", status_code=303)
    templates = get_templates(request)
    return templates.TemplateResponse("register.html", {"request": request, "user": user, "csrf_token": getattr(request.state, 'csrf_token', '')})


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(...),
    consent: Optional[str] = Form(None),  # Checkbox value
):
    """Process registration form."""
    templates = get_templates(request)
    db = get_db()
    config = get_config()

    errors = {}

    # Validate consent
    if not consent:
        errors["consent"] = "You must agree to the Privacy Policy"

    # Validate password length
    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"

    # Validate email format (basic check)
    if "@" not in email or "." not in email:
        errors["email"] = "Please enter a valid email address"

    if errors:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "errors": errors,
            "email": email,
            "display_name": display_name,
        })

    try:
        user_id = db.create_user(email, password, display_name)
        log_audit_event(
            "auth.register",
            request,
            user_id=user_id,
            details={"email": email, "display_name": display_name},
        )
    except sqlite3.IntegrityError:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "errors": {"email": "An account with this email already exists"},
            "email": email,
            "display_name": display_name,
        })

    # Send verification email
    await send_verification_email(email, user_id, display_name)
    log_audit_event("auth.verification_sent", request, user_id=user_id,
                   details={"trigger": "registration"})

    # Create session but redirect to verify page (not dashboard)
    token, expires_at = create_user_session(user_id)

    response = RedirectResponse(url="/verify-email", status_code=303)
    set_session_cookie(response, token, expires_at, request=request)
    return response


@router.post("/logout")
async def logout(request: Request):
    """Log out user."""
    db = get_db()
    token = request.cookies.get("session_token")

    if token:
        session = db.get_session(token)
        if session:
            log_audit_event("auth.logout", request, user_id=session.user_id)
        db.delete_session(token)

    response = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(response)
    return response


# Email verification routes


@router.get("/verify-email", response_class=HTMLResponse)
async def verify_email_page(request: Request, user: User = Depends(require_auth)):
    """Show 'check your email' page for unverified users."""
    templates = get_templates(request)

    # If already verified, redirect to dashboard
    if user.email_verified:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse("verify_email.html", {
        "request": request,
        "user": user,
        "user_email": user.email,
        "csrf_token": getattr(request.state, 'csrf_token', ''),
    })


@router.post("/verify-email/resend")
@limiter.limit(RESEND_RATE_LIMIT)
async def resend_verification_email(request: Request, user: User = Depends(require_auth)):
    """Resend verification email. Rate limited to 3 per hour."""
    templates = get_templates(request)

    # If already verified, just redirect
    if user.email_verified:
        return RedirectResponse(url="/", status_code=303)

    # Send verification email
    await send_verification_email(user.email, user.id, user.display_name)
    log_audit_event("auth.verification_sent", request, user_id=user.id,
                    details={"trigger": "manual_resend"})

    return templates.TemplateResponse("verify_email.html", {
        "request": request,
        "user": user,
        "user_email": user.email,
        "csrf_token": getattr(request.state, 'csrf_token', ''),
        "message": "Verification email sent! Check your inbox.",
    })


@router.get("/verify/{token}")
async def verify_email_token(request: Request, token: str):
    """Process verification link from email."""
    templates = get_templates(request)
    db = get_db()

    try:
        data = verify_verification_token(token)
        user_id = data["user_id"]
        user = db.get_user_by_id(user_id)

        if not user:
            return templates.TemplateResponse("verify_expired.html", {
                "request": request,
                "csrf_token": getattr(request.state, 'csrf_token', ''),
                "message": "Invalid verification link. Please register again.",
            })

        # Check if already verified (token reuse is harmless)
        if user.email_verified:
            return RedirectResponse(url="/login?verified=already", status_code=303)

        # Mark as verified
        db.set_email_verified(user_id, True)
        log_audit_event("auth.email_verified", request, user_id=user_id)

        return RedirectResponse(url="/login?verified=1", status_code=303)

    except SignatureExpired:
        # Token expired - try to auto-resend
        try:
            user_id = get_user_id_from_expired_token(token)
            user = db.get_user_by_id(user_id)

            if user and not user.email_verified:
                await send_verification_email(user.email, user.id, user.display_name)
                log_audit_event("auth.verification_resent_auto", request, user_id=user.id,
                               details={"reason": "expired_link"})
                message = "Link expired. We've sent a new one to your inbox."
            else:
                message = "Link expired. Please log in to request a new verification email."

        except Exception:
            message = "Link expired. Please log in to request a new verification email."

        return templates.TemplateResponse("verify_expired.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "message": message,
        })

    except BadSignature:
        return templates.TemplateResponse("verify_expired.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "message": "Invalid verification link.",
        })


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    """Privacy Policy page."""
    templates = get_templates(request)
    return templates.TemplateResponse("privacy.html", {"request": request, "user": user, "csrf_token": getattr(request.state, 'csrf_token', '')})


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(request: Request, token: str):
    """One-click email unsubscribe (no login required)."""
    templates = get_templates(request)
    db = get_db()

    try:
        data = verify_unsubscribe_token(token)
        user_id = data["user_id"]

        # Disable email notifications
        db.set_user_email_enabled(user_id, False)

        return templates.TemplateResponse("unsubscribed.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "user": None,  # No user context for unsubscribe
            "success": True,
        })

    except SignatureExpired:
        return templates.TemplateResponse("unsubscribed.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "user": None,
            "success": False,
            "error": "This unsubscribe link has expired. Please log in to manage notifications.",
        })

    except BadSignature:
        return templates.TemplateResponse("unsubscribed.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "user": None,
            "success": False,
            "error": "Invalid unsubscribe link.",
        })

    except Exception as e:
        logger.error(f"Unsubscribe error: {e}")
        return templates.TemplateResponse("unsubscribed.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "user": None,
            "success": False,
            "error": "An error occurred. Please try again or log in to manage notifications.",
        })


# Password reset routes


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_form(request: Request):
    """Show password reset request form."""
    templates = get_templates(request)
    return templates.TemplateResponse("password_reset_request.html", {
        "request": request,
        "csrf_token": getattr(request.state, 'csrf_token', ''),
    })


@router.post("/forgot-password", response_class=HTMLResponse)
async def request_password_reset(
    request: Request,
    email: str = Form(...),
):
    """Process password reset request."""
    templates = get_templates(request)
    db = get_db()

    # Normalize email
    email = email.lower().strip()

    # Check rate limit BEFORE looking up user (timing attack prevention)
    allowed, reason = reset_limiter.check_rate_limit(email)
    if not allowed:
        log_audit_event("password.reset_rate_limited", request,
                       details={"email_hash": hashlib.sha256(email.encode()).hexdigest()[:16]})
        return templates.TemplateResponse("password_reset_request.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Too many requests. Try again later.",
        })

    # Record request for rate limiting (regardless of user existence)
    reset_limiter.record_request(email)

    # Look up user
    user = db.get_user_by_email(email)

    # Always show success (don't reveal if email exists)
    if user:
        await send_password_reset_email(user.email, user.id)
        log_audit_event("password.reset_requested", request, user_id=user.id)
    else:
        log_audit_event("password.reset_unknown_email", request,
                       details={"email_hash": hashlib.sha256(email.encode()).hexdigest()[:16]})

    return templates.TemplateResponse("password_reset_request.html", {
        "request": request,
        "csrf_token": getattr(request.state, 'csrf_token', ''),
        "success": "If an account exists with that email, we've sent a reset link.",
    })


@router.get("/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_form(request: Request, token: str):
    """Show password reset form."""
    templates = get_templates(request)

    # Validate token early to show appropriate message
    try:
        verify_reset_token(token)
    except SignatureExpired:
        return templates.TemplateResponse("password_reset_form.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "This reset link has expired.",
            "show_request_new": True,
        })
    except BadSignature:
        return templates.TemplateResponse("password_reset_form.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Invalid reset link.",
        })

    return templates.TemplateResponse("password_reset_form.html", {
        "request": request,
        "csrf_token": getattr(request.state, 'csrf_token', ''),
        "token": token,
    })


@router.post("/reset-password/{token}", response_class=HTMLResponse)
async def complete_password_reset(
    request: Request,
    token: str,
    new_password: str = Form(...),
):
    """Complete password reset with new password."""
    templates = get_templates(request)
    db = get_db()

    # Validate token
    try:
        data = verify_reset_token(token)
        user_id = data["user_id"]
    except SignatureExpired:
        return templates.TemplateResponse("password_reset_form.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "This reset link has expired.",
            "show_request_new": True,
        })
    except BadSignature:
        return templates.TemplateResponse("password_reset_form.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Invalid reset link.",
        })

    # Validate password
    is_valid, error_msg = validate_password(new_password)
    if not is_valid:
        return templates.TemplateResponse("password_reset_form.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "token": token,
            "error": error_msg,
        })

    # Get user
    user = db.get_user_by_id(user_id)
    if not user:
        return templates.TemplateResponse("password_reset_form.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "User not found.",
        })

    # Update password
    from argon2 import PasswordHasher
    hasher = PasswordHasher()
    new_hash = hasher.hash(new_password)
    db.update_user_password_hash(user_id, new_hash)

    # CRITICAL: Invalidate ALL sessions (per CONTEXT.md - assume password was compromised)
    db.delete_user_sessions(user_id)

    log_audit_event("password.reset_completed", request, user_id=user_id)

    # Redirect to login with success message
    return RedirectResponse(
        url="/login?message=Password+updated.+Please+log+in.",
        status_code=303,
    )


# Password change routes (authenticated)


@router.get("/settings/change-password", response_class=HTMLResponse)
async def change_password_form(request: Request, user: User = Depends(require_verified_email)):
    """Show change password form."""
    templates = get_templates(request)
    return templates.TemplateResponse("password_change.html", {
        "request": request,
        "csrf_token": getattr(request.state, 'csrf_token', ''),
    })


@router.post("/settings/change-password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    user: User = Depends(require_verified_email),
    current_password: str = Form(...),
    new_password: str = Form(...),
):
    """Change password for authenticated user."""
    templates = get_templates(request)
    db = get_db()

    # Verify current password using argon2
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    hasher = PasswordHasher()

    try:
        hasher.verify(user.password_hash, current_password)
    except VerifyMismatchError:
        log_audit_event("password.change_failure", request, user_id=user.id,
                       details={"reason": "invalid_current_password"})
        return templates.TemplateResponse("password_change.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "Current password is incorrect",
        })

    # Validate new password
    is_valid, error_msg = validate_password(new_password)
    if not is_valid:
        return templates.TemplateResponse("password_change.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": error_msg,
        })

    # Check new password isn't same as current
    try:
        hasher.verify(user.password_hash, new_password)
        # If verification succeeds, passwords match - reject
        return templates.TemplateResponse("password_change.html", {
            "request": request,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "error": "New password must be different from current password",
        })
    except VerifyMismatchError:
        pass  # Good - passwords are different

    # Update password
    new_hash = hasher.hash(new_password)
    db.update_user_password_hash(user.id, new_hash)

    # NOTE: Do NOT invalidate current session on change (user proved identity)
    # Only invalidate on reset (password may have been compromised)

    log_audit_event("password.change_success", request, user_id=user.id)

    return templates.TemplateResponse("password_change.html", {
        "request": request,
        "csrf_token": getattr(request.state, 'csrf_token', ''),
        "success": "Password updated successfully",
    })
