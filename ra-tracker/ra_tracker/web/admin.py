"""Admin routes for RA Tracker - view-only oversight."""

from typing import Optional
import threading

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import get_db, User
from .auth import require_admin
from ..api.circuit_breaker import circuit_breaker
from ..scheduler.jobs import run_fetch_now, get_last_fetch_time, get_next_fetch_time

admin_router = APIRouter(prefix="/admin", tags=["admin"])


def get_templates(request: Request):
    """Get templates from app state."""
    return request.app.state.templates


@admin_router.get("/rules", response_class=HTMLResponse)
async def admin_rules(request: Request, user: User = Depends(require_admin)):
    """Admin view: All users' rules (read-only)."""
    templates = get_templates(request)
    db = get_db()

    all_rules = db.get_all_rules_with_users()

    # Group rules by owner for display
    rules_by_user = {}
    for rule in all_rules:
        owner = rule.get("owner_name") or "Unknown"
        if owner not in rules_by_user:
            rules_by_user[owner] = []
        rules_by_user[owner].append(rule)

    return templates.TemplateResponse(
        "admin/rules.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "all_rules": all_rules,
            "rules_by_user": rules_by_user,
            "total_rules": len(all_rules),
        },
    )


@admin_router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request, user: User = Depends(require_admin)):
    """Admin view: All registered users."""
    templates = get_templates(request)
    db = get_db()

    all_users = db.get_all_users()

    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "all_users": all_users,
            "total_users": len(all_users),
        },
    )


@admin_router.get("/audit-log", response_class=HTMLResponse)
async def audit_log(
    request: Request,
    user: User = Depends(require_admin),
    user_search: Optional[str] = None,
    event_type: Optional[str] = None,
    ip: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
):
    """Admin audit log with filtering."""
    templates = get_templates(request)
    db = get_db()

    # Calculate pagination
    limit = 50
    offset = (page - 1) * limit

    # Get filtered logs
    logs, total = db.get_audit_logs_filtered(
        user_search=user_search,
        event_type=event_type,
        ip_address=ip,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    # Get event types for dropdown
    event_types = db.get_distinct_event_types()

    # Calculate pagination info
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    has_prev = page > 1
    has_next = page < total_pages

    return templates.TemplateResponse(
        "admin/audit_log.html",
        {
            "request": request,
            "user": user,
            "logs": logs,
            "event_types": event_types,
            "filters": {
                "user": user_search or "",
                "event_type": event_type or "",
                "ip": ip or "",
                "start_date": start_date or "",
                "end_date": end_date or "",
            },
            "pagination": {
                "page": page,
                "total_pages": total_pages,
                "total": total,
                "has_prev": has_prev,
                "has_next": has_next,
            },
            "csrf_token": getattr(request.state, 'csrf_token', ''),
        },
    )


@admin_router.get("/scraper-status", response_class=HTMLResponse)
async def scraper_status(request: Request, user: User = Depends(require_admin)):
    """Admin scraper status and monitoring page."""
    templates = get_templates(request)
    db = get_db()

    # Get circuit breaker status
    cb_status = circuit_breaker.get_status()

    # Get recent errors
    recent_errors = db.get_recent_scraper_errors(limit=10)

    # Get fetch times (DB-backed for cross-worker accuracy)
    next_fetch_time = get_next_fetch_time()

    # Get scraper health data from database
    health_summary = db.get_scraper_health_summary(days=7)
    fetch_history = db.get_recent_fetch_history(limit=20)
    trend_data = db.get_fetch_success_rate_trend(days=7)

    # Calculate success rate (handle division by zero)
    total_fetches = health_summary.get("total_fetches", 0)
    successful = health_summary.get("successful", 0)
    if total_fetches > 0:
        success_rate = round(successful / total_fetches * 100, 1)
    else:
        success_rate = 0

    # Color code success rate
    if success_rate >= 90:
        success_rate_color = "text-success"
    elif success_rate >= 50:
        success_rate_color = "text-warning"
    else:
        success_rate_color = "text-danger"

    # Calculate trend direction from daily data
    if len(trend_data) >= 2:
        last_rate = trend_data[-1]["success_rate"]
        prior_rate = trend_data[-2]["success_rate"]
        if last_rate > prior_rate:
            trend = "improving"
        elif last_rate < prior_rate:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "unknown"

    # Database-backed last fetch time (works across gunicorn workers)
    last_fetch_time = health_summary.get("last_successful_fetch")
    if last_fetch_time is None:
        # Fall back to in-memory variable
        last_fetch_time = get_last_fetch_time()

    # Map circuit breaker state to display labels
    state_display = {
        "CLOSED": "Healthy",
        "OPEN": "Down",
        "HALF_OPEN": "Recovering"
    }

    return templates.TemplateResponse(
        "admin/scraper_status.html",
        {
            "request": request,
            "user": user,
            "csrf_token": getattr(request.state, 'csrf_token', ''),
            "cb_status": cb_status,
            "state_display": state_display.get(cb_status.state, cb_status.state),
            "recent_errors": recent_errors,
            "last_fetch_time": last_fetch_time,
            "next_fetch_time": next_fetch_time,
            "health_summary": health_summary,
            "fetch_history": fetch_history,
            "trend": trend,
            "success_rate": success_rate,
            "success_rate_color": success_rate_color,
        },
    )


@admin_router.post("/scraper/fetch-now")
async def force_fetch(request: Request, user: User = Depends(require_admin)):
    """Force immediate fetch, bypassing circuit breaker."""
    # Bypass circuit breaker
    circuit_breaker.force_close()

    # Run fetch in background thread
    threading.Thread(target=run_fetch_now, daemon=True).start()

    # Redirect back to scraper status page
    return RedirectResponse(url="/admin/scraper-status", status_code=303)
