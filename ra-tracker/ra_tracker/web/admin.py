"""Admin routes for RA Tracker - view-only oversight."""

from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from ..database import get_db, User
from .auth import require_admin

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
