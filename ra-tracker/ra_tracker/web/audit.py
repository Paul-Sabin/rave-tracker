"""Audit logging service for RA Tracker."""

import json
import logging
from typing import Optional, Dict, Any

from fastapi import Request

from ..database import get_db

logger = logging.getLogger(__name__)


def log_audit_event(
    event_type: str,
    request: Request,
    user_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
) -> int:
    """Log an audit event to the database.

    Args:
        event_type: Category.action format (e.g., 'auth.login', 'rule.create')
        request: FastAPI request for IP extraction
        user_id: User who triggered event (None for anonymous)
        details: Additional context as JSON-serializable dict
        target_type: Type of resource affected (e.g., 'rule', 'user')
        target_id: ID of affected resource

    Returns:
        ID of the created audit log entry

    Event type conventions:
        auth.login_success, auth.login_failure, auth.logout, auth.register
        rule.create, rule.update, rule.delete
        settings.update
        telegram.link, telegram.unlink
    """
    # Extract IP address
    ip_address = None
    if request.client:
        ip_address = request.client.host

    # Serialize details to JSON
    details_json = None
    if details:
        try:
            details_json = json.dumps(details)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize audit details: {e}")
            details_json = json.dumps({"error": "serialization_failed"})

    db = get_db()
    try:
        log_id = db.add_audit_log(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            details=details_json,
            target_type=target_type,
            target_id=target_id,
        )
        logger.debug(f"Audit log {log_id}: {event_type} user={user_id} ip={ip_address}")
        return log_id
    except Exception as e:
        # Log errors but don't fail the request - audit is non-blocking
        logger.error(f"Failed to write audit log: {e}")
        return -1
