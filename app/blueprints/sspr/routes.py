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
from app.services import audit_service, sms_service
from app.services.ad_service import ADError, reset_password

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

    # Look up user phone via LDAP
    try:
        user = sms_service.lookup_user(username)
    except Exception as exc:
        logger.error("LDAP lookup failed: %s", exc)
        audit_service.log(Action.SEND_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail=str(exc))
        flash("An error occurred. Please try again later.", "danger")
        return redirect(url_for("sspr.index"))

    if user is None:
        # Generic message — no user enumeration
        audit_service.log(Action.SEND_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail="user not found")
        flash("Could not send OTP. Please verify your username.", "warning")
        return redirect(url_for("sspr.index"))

    # Start Twilio Verify SMS — store the normalized number Twilio returns
    try:
        normalized_phone = sms_service.start_verification(user["phone"])
    except Exception as exc:
        logger.error("Twilio start_verification failed: %s", exc)
        audit_service.log(Action.SEND_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail=str(exc))
        flash("Failed to send verification code. Please contact IT support.", "danger")
        return redirect(url_for("sspr.index"))

    # Lock username and phone in session
    session["username"] = username
    session["phone"] = normalized_phone
    session.modified = True

    audit_service.log(Action.SEND_OTP, Outcome.SUCCESS, username=username, ip_address=ip)
    flash("A 6-digit code has been sent to your mobile phone.", "info")
    return redirect(url_for("sspr.verify"))


@sspr_bp.route("/verify", methods=["GET", "POST"])
def verify():
    phone = session.get("phone")
    if not session.get("username") or not phone:
        flash("Session expired. Please start over.", "warning")
        return redirect(url_for("sspr.index"))

    form = OTPForm()
    if not form.validate_on_submit():
        return render_template("sspr/verify.html", form=form)

    ip = request.remote_addr
    username = session.get("username")

    try:
        status = sms_service.check_verification(phone, form.otp.data.strip())
    except Exception as exc:
        # 404 = expired/used, 429 = too many attempts, other errors
        logger.error("Twilio verify check failed: %s", exc)
        audit_service.log(Action.VERIFY_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail=str(exc))
        session.clear()
        flash("Verification failed or code expired. Please start over.", "danger")
        return redirect(url_for("sspr.index"))

    if status == "approved":
        session["otp_verified"] = True
        session.modified = True
        audit_service.log(Action.VERIFY_OTP, Outcome.SUCCESS, username=username, ip_address=ip)
        return redirect(url_for("sspr.reset"))

    # "pending" = wrong code — Twilio still accepts retries until its own limit
    audit_service.log(Action.VERIFY_OTP, Outcome.FAILURE, username=username, ip_address=ip, detail="wrong_code")
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

def _get_rate_limit() -> str:
    from flask import current_app
    return current_app.config.get("RATELIMIT_OTP_SEND", "5 per hour")
