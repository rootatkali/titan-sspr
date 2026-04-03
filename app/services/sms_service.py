"""Twilio Verify SMS delivery — user phone lookup and OTP verification."""
from __future__ import annotations

import logging
import ssl

import requests
from ldap3 import Connection, Server, Tls
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


def _get_config() -> dict:
    from flask import current_app
    return current_app.config


def lookup_user(username: str) -> dict | None:
    """
    Look up a user by sAMAccountName via LDAP and return their phone number.
    Phone priority: mobile → telephoneNumber.
    Returns {"phone": str, "displayName": str} or None if not found / no phone.
    """

    cfg = _get_config()
    tls = Tls(
        ca_certs_file=cfg["LDAP_CA_CERT_PATH"],
        validate=ssl.CERT_REQUIRED,
        version=ssl.PROTOCOL_TLS_CLIENT,
    )
    server = Server(cfg["LDAP_SERVER"], port=cfg["LDAP_PORT"], use_ssl=True, tls=tls)
    conn = Connection(
        server,
        user=cfg["LDAP_SERVICE_ACCOUNT_DN"],
        password=cfg["LDAP_SERVICE_ACCOUNT_PASS"],
        auto_bind=True,
    )
    try:
        search_filter = cfg["LDAP_USER_SEARCH_FILTER"].replace("{username}", username)
        conn.search(
            cfg["LDAP_SEARCH_BASE"],
            search_filter,
            attributes=["mobile", "telephoneNumber", "displayName"],
        )
        if not conn.entries:
            return None

        entry = conn.entries[0]
        mobile = _attr_value(entry, "mobile")
        telephone = _attr_value(entry, "telephoneNumber")
        phone = mobile or telephone
        if not phone:
            return None

        display_name = _attr_value(entry, "displayName") or username
        return {"phone": phone, "displayName": display_name}
    finally:
        try:
            conn.unbind()
        except Exception:
            pass


def _attr_value(entry, attr: str) -> str | None:
    """Return the string value of an ldap3 entry attribute, or None if absent/empty."""
    try:
        val = getattr(entry, attr).value
        return str(val).strip() if val else None
    except Exception:
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
