import logging
from flask import request
from models import db
from models.audit_log import AuditLog
from datetime import datetime

logger = logging.getLogger(__name__)

def log_audit_event(user_id=None, team_id=None, action=None, details=None):
    """
    Log an event to the AuditLog table.

    Uses a savepoint (begin_nested) so that a failure here never rolls back
    the parent transaction that triggered the audit (e.g. a login commit).
    """
    try:
        ip_address = request.remote_addr or '0.0.0.0'
        user_agent = request.headers.get('User-Agent', '')[:255]

        log = AuditLog(
            user_id=user_id,
            team_id=team_id,
            ip_address=ip_address,
            action=action,
            details=details,
            user_agent=user_agent,
            timestamp=datetime.utcnow()
        )

        # Use a savepoint so only this write is rolled back on failure,
        # leaving any parent transaction (e.g. login, team join) intact.
        with db.session.begin_nested():
            db.session.add(log)

    except Exception as e:
        logger.error(f"Failed to log audit event [action={action}]: {e}")
