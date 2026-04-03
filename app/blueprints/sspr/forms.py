"""WTForms definitions for the SSPR flow."""
from __future__ import annotations

import re

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo, Length

_SPECIAL_RE = re.compile(r"[!@#$%^&*()\-_=+\[\]{}|;:',.<>?/`~\"\\]")


class UsernameForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=1, max=64)],
        render_kw={"placeholder": "Your network username", "autocomplete": "off"},
    )


class OTPForm(FlaskForm):
    otp = StringField(
        "One-Time Code",
        validators=[DataRequired(), Length(min=6, max=6)],
        render_kw={"placeholder": "6-digit code", "autocomplete": "one-time-code", "inputmode": "numeric"},
    )


class PasswordResetForm(FlaskForm):
    new_password = PasswordField(
        "New Password",
        validators=[DataRequired(), Length(min=12, max=256)],
        render_kw={"autocomplete": "new-password"},
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
        render_kw={"autocomplete": "new-password"},
    )


def validate_password_complexity(password: str) -> list[str]:
    """
    Return a list of unmet complexity rules.
    Empty list means the password is valid.
    """
    errors: list[str] = []
    if len(password) < 12:
        errors.append("At least 12 characters")
    if not any(c.isupper() for c in password):
        errors.append("At least one uppercase letter")
    if not any(c.islower() for c in password):
        errors.append("At least one lowercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("At least one digit")
    if not _SPECIAL_RE.search(password):
        errors.append("At least one special character (!@#$%^&* etc.)")
    return errors
