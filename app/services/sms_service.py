"""Twilio Verify SMS delivery — user phone lookup and OTP verification."""
from __future__ import annotations

import logging

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


def _get_config() -> dict:
    from flask import current_app
    return current_app.config


def lookup_user(username: str) -> dict | None:
    """
    Look up a student by course_username via HAPI and return their phone number.
    Returns {"phone": str} or None if not found / no phone.
    """
    cfg = _get_config()
    resp = requests.get(
        f"{cfg['HAPI_BASE_URL']}/api/students",
        params={"q": username},
        headers={"Authorization": f"Bearer {cfg['HAPI_TOKEN']}"},
        timeout=10,
        verify=False,
    )
    resp.raise_for_status()
    for student in resp.json():
        if student.get("course_username") == username:
            phone = student.get("phone_number") or None
            return {"phone": phone} if phone else None
    return None


def start_verification(phone: str) -> str:
    """
    Initiate a Twilio Verify SMS to the given phone number.
    Returns Twilio's normalized E.164 number — always use this for check_verification.
    """
    cfg = _get_config()
    url = f"https://verify.twilio.com/v2/Services/{cfg['TWILIO_VERIFY_SERVICE_SID']}/Verifications"
    resp = requests.post(
        url,
        data={"To": phone, "Channel": "sms"},
        auth=HTTPBasicAuth(cfg["TWILIO_ACCOUNT_SID"], cfg["TWILIO_AUTH_TOKEN"]),
        timeout=15,
    )
    resp.raise_for_status()
    normalized = resp.json()["to"]
    logger.info("Twilio Verify started for phone ending ...%s", normalized[-4:])
    return normalized


def check_verification(phone: str, code: str) -> str:
    """
    Submit a verification check to Twilio Verify.
    Returns the status string: "approved" or "pending".
    Raises on non-2xx responses (404 = expired/used, 429 = rate limited).
    """
    cfg = _get_config()
    url = f"https://verify.twilio.com/v2/Services/{cfg['TWILIO_VERIFY_SERVICE_SID']}/VerificationCheck"
    resp = requests.post(
        url,
        data={"To": phone, "Code": code},
        auth=HTTPBasicAuth(cfg["TWILIO_ACCOUNT_SID"], cfg["TWILIO_AUTH_TOKEN"]),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["status"]
