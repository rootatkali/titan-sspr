"""SSPR blueprint routes — the core user-facing flow."""
from __future__ import annotations

import logging

from flask import flash, redirect, render_template, request, session, url_for

from app.blueprints.sspr import sspr_bp
from app.blueprints.sspr.forms import (
    OTPForm,
    PasswordResetForm,
    UsernameForm,
    validate_password_complexity,
)
from app.extensions import limiter
from app.models.audit_log import Action, Outcome
from app.services import audit_service, graph_service, otp_service
from app.services.ad_service import ADError, reset_password
from app.services.otp_service import OTPResult

logger = logging.getLogger(__name__)


@sspr_bp.route("/", methods=["GET", "POST"])
def index():
    form = UsernameForm()
    if form.validate_on_submit():
        return redirect(url_for("sspr.send_otp_post", _method="POST"))
    return render_template("sspr/index.html", form=form)


@sspr_bp.route("/send-otp", methods=["POST"])
@limiter.limit(
    lambda: _get_rate_limit(),
    error_message="Too many password reset requests. Please try again in an hour.",
)
def send_otp_post():
    form = UsernameForm()
    if not form.validate_on_submit():
        return render_template("sspr/index.html", form=form)

    username = form.username.data.strip().lower()
    ip = request.remote_addr

    # Look up user in M365 (Graph)
    try:
        user = graph_service.lookup_user(username)
    except Exception as exc:
        logger.error("Graph lookup failed: %s", exc)
        audit_service.log(Action.SEND_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail=str(exc))
        flash("An error occurred. Please try again later.", "danger")
        return redirect(url_for("sspr.index"))

    if user is None:
        # Generic message — no user enumeration
        audit_service.log(Action.SEND_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail="user not found")
        flash("Could not send OTP. Please verify your username.", "warning")
        return redirect(url_for("sspr.index"))

    # Generate and send OTP
    cfg = _get_cfg()
    otp = otp_service.generate_otp()
    otp_service.store_otp(session, otp, cfg["OTP_EXPIRY_SECONDS"], cfg["OTP_MAX_ATTEMPTS"])

    try:
        graph_service.send_otp_via_teams(user["id"], otp)
    except Exception as exc:
        logger.error("Teams message failed: %s", exc)
        otp_service.clear_otp(session)
        audit_service.log(Action.SEND_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail=str(exc))
        flash("Failed to send OTP via Teams. Please contact IT support.", "danger")
        return redirect(url_for("sspr.index"))

    # Lock username in session — never updated again
    session["username"] = username
    session.modified = True

    audit_service.log(Action.SEND_OTP, Outcome.SUCCESS, username=username, ip_address=ip)
    flash("A 6-digit code has been sent to your Teams chat.", "info")
    return redirect(url_for("sspr.verify"))


@sspr_bp.route("/verify", methods=["GET", "POST"])
def verify():
    if not session.get("username"):
        flash("Session expired. Please start over.", "warning")
        return redirect(url_for("sspr.index"))

    form = OTPForm()
    if not form.validate_on_submit():
        return render_template("sspr/verify.html", form=form)

    candidate = form.otp.data.strip()
    cfg = _get_cfg()
    result = otp_service.validate_otp(session, candidate)
    ip = request.remote_addr
    username = session.get("username")

    if result == OTPResult.VALID:
        session["otp_verified"] = True
        session.modified = True
        audit_service.log(Action.VERIFY_OTP, Outcome.SUCCESS, username=username, ip_address=ip)
        return redirect(url_for("sspr.reset"))

    if result == OTPResult.EXPIRED:
        audit_service.log(Action.VERIFY_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail="expired")
        session.clear()
        flash("Your code has expired. Please start over.", "warning")
        return redirect(url_for("sspr.index"))

    if result == OTPResult.MAX_ATTEMPTS:
        audit_service.log(Action.VERIFY_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail="max_attempts")
        session.clear()
        flash("Too many incorrect attempts. Please start over.", "danger")
        return redirect(url_for("sspr.index"))

    # INVALID
    audit_service.log(Action.VERIFY_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail="invalid_otp")
    flash("Incorrect code. Please try again.", "danger")
    return render_template("sspr/verify.html", form=form)


@sspr_bp.route("/reset", methods=["GET", "POST"])
def reset():
    if not session.get("username") or not session.get("otp_verified"):
        flash("Session expired or verification incomplete. Please start over.", "warning")
        return redirect(url_for("sspr.index"))

    form = PasswordResetForm()
    if not form.validate_on_submit():
        return render_template("sspr/reset.html", form=form)

    new_password = form.new_password.data
    complexity_errors = validate_password_complexity(new_password)
    if complexity_errors:
        return render_template("sspr/reset.html", form=form, complexity_errors=complexity_errors)

    username = session["username"]  # read from session — never from form input
    ip = request.remote_addr

    try:
        reset_password(username, new_password)
    except ADError as exc:
        logger.error("AD reset failed for %s: %s", username, exc)
        audit_service.log(Action.RESET_PASSWORD, Outcome.FAILURE, username=username, ip_address=ip, detail=str(exc))
        flash("Password reset failed. Please contact IT support.", "danger")
        return render_template("sspr/reset.html", form=form)

    audit_service.log(Action.RESET_PASSWORD, Outcome.SUCCESS, username=username, ip_address=ip)
    session.clear()
    flash("Your password has been reset successfully.", "success")
    return render_template("sspr/index.html", form=UsernameForm(), success=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_cfg() -> dict:
    from flask import current_app
    return current_app.config


def _get_rate_limit() -> str:
    return _get_cfg().get("RATELIMIT_OTP_SEND", "5 per hour")
