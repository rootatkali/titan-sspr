"""Audit logging service."""
from __future__ import annotations

import logging

import app.extensions as ext
from app.models.audit_log import Action, AuditLog, Outcome

logger = logging.getLogger(__name__)


def _get_session():
    """Return a new SQLAlchemy ORM session. Deferred to avoid import-time None."""
    if ext.DbSession is None:
        raise RuntimeError("Database not initialised — call create_app() first")
    return ext.DbSession()


def log(
    action: Action,
    outcome: Outcome,
    username: str | None = None,
    ip_address: str | None = None,
    detail: str | None = None,
) -> None:
    """Write an audit log entry. Silently swallows DB errors to avoid masking the main flow."""
    try:
        session = _get_session()
        try:
            entry = AuditLog(
                action=action.value,
                outcome=outcome.value,
                username=username,
                ip_address=ip_address,
                detail=detail,
            )
            session.add(entry)
            session.commit()
        finally:
            session.close()
    except Exception as exc:
        logger.error("Failed to write audit log: %s", exc)


def get_logs(page: int = 1, per_page: int = 50) -> tuple[list[AuditLog], int]:
    """Return (entries, total_count) for paginated admin display."""
    session = _get_session()
    try:
        total = session.query(AuditLog).count()
        entries = (
            session.query(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        # Detach from session so they can be used after session close
        session.expunge_all()
        return entries, total
    finally:
        session.close()
