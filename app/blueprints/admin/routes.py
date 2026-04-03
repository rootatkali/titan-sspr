"""Admin blueprint — audit log viewer with HTTP Basic Auth."""
from __future__ import annotations

import base64
import functools
import logging

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import current_app, request, Response

from app.blueprints.admin import admin_bp
from app.services import audit_service

logger = logging.getLogger(__name__)
_ph = PasswordHasher()


def _check_auth(username: str, password: str) -> bool:
    cfg = current_app.config
    if username != cfg.get("ADMIN_USERNAME"):
        return False
    try:
        return _ph.verify(cfg["ADMIN_PASSWORD_HASH"], password)
    except (VerifyMismatchError, Exception):
        return False


def _require_basic_auth(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return _unauthorized()
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            uname, _, passwd = decoded.partition(":")
        except Exception:
            return _unauthorized()

        if not _check_auth(uname, passwd):
            return _unauthorized()
        return fn(*args, **kwargs)
    return wrapper


def _unauthorized() -> Response:
    return Response(
        "Authentication required.",
        status=401,
        headers={"WWW-Authenticate": 'Basic realm="Admin"'},
    )


@admin_bp.route("/logs")
@_require_basic_auth
def logs():
    from flask import render_template
    page = request.args.get("page", 1, type=int)
    per_page = 50
    entries, total = audit_service.get_logs(page=page, per_page=per_page)
    total_pages = (total + per_page - 1) // per_page
    return render_template(
        "admin/logs.html",
        entries=entries,
        page=page,
        total_pages=total_pages,
        total=total,
    )
