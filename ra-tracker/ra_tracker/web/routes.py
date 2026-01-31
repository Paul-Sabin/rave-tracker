"""FastAPI routes for RA Tracker web UI - Simplified."""

import logging
import sqlite3
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from ..api.ra_client import RAClient
from ..config import get_config
from ..database import get_db, Rule, User
from ..scheduler.jobs import run_fetch_now, get_scheduler_status
from ..services.notifier import Notifier
from ..services.email_sender import verify_unsubscribe_token
from itsdangerous import SignatureExpired, BadSignature
from .auth import (
    create_user_session,
    set_session_cookie,
    clear_session_cookie,
    get_current_user,
    require_auth,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_templates(request: Request):
    """Get templates from app state."""
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_auth)):
    """Main dashboard showing upcoming events for current user."""
    templates = get_templates(request)
    db = get_db()
    config = get_config()

    # Get user-scoped events, rules, and stats
    events = db.get_upcoming_events_for_user(user.id)
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
async def rules_page(request: Request, user: User = Depends(require_auth)):
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
            "rules": rules,
            "artists": artists,
            "venues": venues,
            "promoters": promoters,
        },
    )


@router.post("/rules/add")
async def add_rule(
    request: Request,
    user: User = Depends(require_auth),
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
async def toggle_rule(rule_id: int, user: User = Depends(require_auth)):
    """Toggle a rule's active status. Verifies ownership first."""
    db = get_db()
    rule = db.get_rule_for_user(rule_id, user.id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.set_rule_active(rule_id, not rule.is_active)
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/rules/{rule_id}/notify-mode")
async def set_notify_mode(rule_id: int, user: User = Depends(require_auth), mode: str = Form(...)):
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


@router.post("/rules/{rule_id}/delete")
async def delete_rule(rule_id: int, user: User = Depends(require_auth)):
    """Delete a rule. Verifies ownership first."""
    db = get_db()
    rule = db.get_rule_for_user(rule_id, user.id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete_rule(rule_id)
    return RedirectResponse(url="/rules", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: User = Depends(require_auth)):
    """Settings page."""
    templates = get_templates(request)
    config = get_config()

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
            "config": config,
            "masked_token": masked_token,
            "scheduler_status": get_scheduler_status(),
        },
    )


@router.post("/settings/save")
async def save_settings(
    request: Request,
    user: User = Depends(require_auth),
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
async def test_telegram(user: User = Depends(require_auth)):
    """Send a test Telegram message."""
    notifier = Notifier()
    try:
        success = notifier.send_test()
        if success:
            return {"status": "success", "message": "Test message sent!"}
        return {"status": "error", "message": "Failed to send"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/actions/fetch-now")
async def trigger_fetch(user: User = Depends(require_auth)):
    """Manually trigger a fetch."""
    run_fetch_now()
    return RedirectResponse(url="/", status_code=303)


# Search API endpoints
@router.get("/api/search/artists")
async def search_artists(q: str, user: User = Depends(require_auth)):
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
async def search_venues(q: str, user: User = Depends(require_auth)):
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
async def search_promoters(q: str, user: User = Depends(require_auth)):
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
async def search_areas(q: str, user: User = Depends(require_auth)):
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
async def get_status(user: User = Depends(require_auth)):
    """Get current system status for the user."""
    db = get_db()
    return {
        "scheduler": get_scheduler_status(),
        **db.get_user_stats(user.id),
    }


@router.post("/api/rules/add")
async def api_add_rule(request: Request, user: User = Depends(require_auth)):
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
async def api_check_rule(rule_type: str, target_id: int, user: User = Depends(require_auth)):
    """Check if a rule already exists for this user."""
    db = get_db()
    exists = db.rule_exists(rule_type, target_id, user_id=user.id)
    return {"exists": exists}


# Authentication routes


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    """Login page. Redirect to dashboard if already logged in."""
    if user:
        return RedirectResponse(url="/", status_code=303)
    templates = get_templates(request)
    return templates.TemplateResponse("login.html", {"request": request, "user": user})


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Process login form."""
    templates = get_templates(request)
    db = get_db()
    config = get_config()

    user = db.get_user_by_email(email)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid email or password",
            "email": email,
        })

    valid, new_hash = db.verify_password(user.password_hash, password)
    if not valid:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid email or password",
            "email": email,
        })

    # Rehash if needed (algorithm upgrade)
    if new_hash:
        db.update_user_password_hash(user.id, new_hash)

    # Create new session
    token, expires_at = create_user_session(user.id)

    response = RedirectResponse(url="/", status_code=303)
    set_session_cookie(response, token, expires_at, request=request)
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    """Registration page. Redirect to dashboard if already logged in."""
    if user:
        return RedirectResponse(url="/", status_code=303)
    templates = get_templates(request)
    return templates.TemplateResponse("register.html", {"request": request, "user": user})


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
            "errors": errors,
            "email": email,
            "display_name": display_name,
        })

    try:
        user_id = db.create_user(email, password, display_name)
    except sqlite3.IntegrityError:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "errors": {"email": "An account with this email already exists"},
            "email": email,
            "display_name": display_name,
        })

    # Auto-login after registration
    token, expires_at = create_user_session(user_id)

    response = RedirectResponse(url="/", status_code=303)
    set_session_cookie(response, token, expires_at, request=request)
    return response


@router.post("/logout")
async def logout(request: Request):
    """Log out user."""
    db = get_db()
    token = request.cookies.get("session_token")

    if token:
        db.delete_session(token)

    response = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(response)
    return response


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    """Privacy Policy page."""
    templates = get_templates(request)
    return templates.TemplateResponse("privacy.html", {"request": request, "user": user})


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
            "user": None,  # No user context for unsubscribe
            "success": True,
        })

    except SignatureExpired:
        return templates.TemplateResponse("unsubscribed.html", {
            "request": request,
            "user": None,
            "success": False,
            "error": "This unsubscribe link has expired. Please log in to manage notifications.",
        })

    except BadSignature:
        return templates.TemplateResponse("unsubscribed.html", {
            "request": request,
            "user": None,
            "success": False,
            "error": "Invalid unsubscribe link.",
        })

    except Exception as e:
        logger.error(f"Unsubscribe error: {e}")
        return templates.TemplateResponse("unsubscribed.html", {
            "request": request,
            "user": None,
            "success": False,
            "error": "An error occurred. Please try again or log in to manage notifications.",
        })
