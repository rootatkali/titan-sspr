"""OTP generation, storage, and validation operating on Flask session."""
from __future__ import annotations

import enum
import secrets
from time import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import session as FlaskSession


class OTPResult(str, enum.Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"
    MAX_ATTEMPTS = "MAX_ATTEMPTS"
    NOT_FOUND = "NOT_FOUND"


def generate_otp() -> str:
    """Return a 6-digit OTP string (zero-padded)."""
    return str(secrets.randbelow(1_000_000)).zfill(6)


def store_otp(session: dict, otp: str, expiry_seconds: int, max_attempts: int) -> None:
    """Store OTP and metadata in the session."""
    session["otp"] = {
        "value": otp,
        "expires_at": time() + expiry_seconds,
        "attempts": 0,
        "max_attempts": max_attempts,
    }


def validate_otp(session: dict, candidate: str) -> OTPResult:
    """
    Validate the candidate OTP against the session.
    Mutates session state (attempt counter / clears OTP on success).
    Returns an OTPResult enum value.
    """
    otp_data = session.get("otp")
    if not otp_data:
        return OTPResult.NOT_FOUND

    if time() > otp_data["expires_at"]:
        session.pop("otp", None)
        return OTPResult.EXPIRED

    if otp_data["attempts"] >= otp_data["max_attempts"]:
        session.pop("otp", None)
        return OTPResult.MAX_ATTEMPTS

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(otp_data["value"], candidate.strip()):
        otp_data["attempts"] += 1
        session["otp"] = otp_data  # re-assign to trigger session save
        if otp_data["attempts"] >= otp_data["max_attempts"]:
            session.pop("otp", None)
            return OTPResult.MAX_ATTEMPTS
        return OTPResult.INVALID

    # Valid — clear OTP, mark verified
    session.pop("otp", None)
    return OTPResult.VALID


def clear_otp(session: dict) -> None:
    session.pop("otp", None)
