"""Admin routes for RA Tracker - view-only oversight."""

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
            "all_users": all_users,
            "total_users": len(all_users),
        },
    )
