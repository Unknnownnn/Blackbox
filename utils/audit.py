import json
import logging
from datetime import datetime

from flask import request
from models import db

logger = logging.getLogger(__name__)


def log_audit_event(user_id=None, team_id=None, action=None, details=None):
    """
    Write a single audit row in its own independent, committed transaction.

    Design rationale
    ----------------
    We use ``db.engine.begin()`` (a raw-engine context manager) instead of
    ``db.session`` for three reasons:

    1. **Always committed** – ``engine.begin()`` auto-commits on exit, so
       LOGIN_FAILED and LOGOUT events (whose callers never call
       ``db.session.commit()``) are reliably persisted.

    2. **Isolated from caller's session** – a failure here cannot roll back
       or corrupt the caller's open SQLAlchemy session.

    3. **No delete-orphan / relationship side-effects** – we bypass the ORM
       completely, so nullable user_id / team_id cause no cascade errors.
    """
    try:
        ip_address = '0.0.0.0'
        user_agent = ''
        try:
            # request context may not exist in background tasks / tests
            ip_address = request.remote_addr or '0.0.0.0'
            user_agent = (request.headers.get('User-Agent') or '')[:255]
        except RuntimeError:
            pass

        # Serialise JSON details manually so we control the output format
        details_json = json.dumps(details, default=str) if details is not None else None

        with db.engine.begin() as conn:
            conn.execute(
                db.text(
                    "INSERT INTO audit_logs "
                    "  (user_id, team_id, ip_address, action, details, user_agent, timestamp) "
                    "VALUES "
                    "  (:user_id, :team_id, :ip_address, :action, :details, :user_agent, :timestamp)"
                ),
                {
                    "user_id":    user_id,
                    "team_id":    team_id,
                    "ip_address": ip_address,
                    "action":     action,
                    "details":    details_json,
                    "user_agent": user_agent,
                    "timestamp":  datetime.utcnow(),
                },
            )
    except Exception as e:
        # Never raise – audit failures must not affect the caller's response.
        logger.error("Failed to log audit event [action=%s]: %s", action, e)
