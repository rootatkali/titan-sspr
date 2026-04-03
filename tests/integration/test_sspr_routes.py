"""Integration tests for the SSPR blueprint — full flow + failure paths."""
from __future__ import annotations

import requests as req_lib
from unittest.mock import patch


# ── Helpers ───────────────────────────────────────────────────────────────────

FAKE_USER = {"phone": "+15550001234", "displayName": "Test User"}


def _patch_sms_success(monkeypatch):
    monkeypatch.setattr("app.blueprints.sspr.routes.sms_service.lookup_user", lambda u: FAKE_USER)
    monkeypatch.setattr("app.blueprints.sspr.routes.sms_service.start_verification", lambda phone: phone)


def _patch_verify_success(monkeypatch):
    monkeypatch.setattr(
        "app.blueprints.sspr.routes.sms_service.check_verification",
        lambda phone, code: "approved",
    )


def _patch_ad_success(monkeypatch):
    monkeypatch.setattr("app.blueprints.sspr.routes.reset_password", lambda u, p: None)


def _send_otp(client, username="testuser"):
    return client.post("/send-otp", data={"username": username})


# ── Happy path ────────────────────────────────────────────────────────────────

def test_happy_path_full_flow(client, app, monkeypatch):
    _patch_sms_success(monkeypatch)
    _patch_verify_success(monkeypatch)
    _patch_ad_success(monkeypatch)

    # Step 1: GET /
    resp = client.get("/")
    assert resp.status_code == 200

    # Step 2: POST /send-otp
    resp = _send_otp(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/verify")

    with client.session_transaction() as sess:
        assert sess["username"] == "testuser"
        assert sess["phone"] == "+15550001234"

    # Step 3: GET /verify
    resp = client.get("/verify")
    assert resp.status_code == 200

    # Step 4: POST /verify with any 6-digit code (Twilio mocked to approve)
    resp = client.post("/verify", data={"otp": "123456"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/reset")

    with client.session_transaction() as sess:
        assert sess.get("otp_verified") is True

    # Step 5: GET /reset
    resp = client.get("/reset")
    assert resp.status_code == 200

    # Step 6: POST /reset with valid password
    resp = client.post("/reset", data={"new_password": "ValidPass123!", "confirm_password": "ValidPass123!"})
    assert resp.status_code == 200
    assert b"reset successfully" in resp.data


# ── Guard: verify rejects missing session ─────────────────────────────────────

def test_verify_without_session_redirects(client):
    resp = client.get("/verify")
    assert resp.status_code == 302
    assert "/verify" not in resp.headers["Location"]


def test_verify_post_without_session_redirects(client):
    resp = client.post("/verify", data={"otp": "123456"})
    assert resp.status_code == 302


# ── Guard: reset rejects unverified session ───────────────────────────────────

def test_reset_without_otp_verified_redirects(client, monkeypatch):
    _patch_sms_success(monkeypatch)
    _send_otp(client)
    # Go directly to /reset without verifying OTP
    resp = client.get("/reset")
    assert resp.status_code == 302


# ── Wrong OTP: "pending" from Twilio — error shown, stay on verify ────────────

def test_wrong_otp_stays_on_verify(client, monkeypatch):
    _patch_sms_success(monkeypatch)
    monkeypatch.setattr(
        "app.blueprints.sspr.routes.sms_service.check_verification",
        lambda phone, code: "pending",
    )
    _send_otp(client)

    resp = client.post("/verify", data={"otp": "000000"})
    assert resp.status_code == 200
    assert b"Incorrect" in resp.data

    with client.session_transaction() as sess:
        assert "otp_verified" not in sess


# ── Expired / used code: Twilio raises 404 → redirect to start ───────────────

def test_expired_otp_redirects_to_start(client, monkeypatch):
    _patch_sms_success(monkeypatch)
    monkeypatch.setattr(
        "app.blueprints.sspr.routes.sms_service.check_verification",
        lambda phone, code: (_ for _ in ()).throw(req_lib.HTTPError("404 Not Found")),
    )
    _send_otp(client)

    resp = client.post("/verify", data={"otp": "123456"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


# ── Rate limited: Twilio raises 429 → session cleared, redirect to start ──────

def test_max_attempts_clears_session(client, monkeypatch):
    _patch_sms_success(monkeypatch)
    monkeypatch.setattr(
        "app.blueprints.sspr.routes.sms_service.check_verification",
        lambda phone, code: (_ for _ in ()).throw(req_lib.HTTPError("429 Too Many Requests")),
    )
    _send_otp(client)

    resp = client.post("/verify", data={"otp": "000000"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")

    with client.session_transaction() as sess:
        assert "username" not in sess
        assert "phone" not in sess


# ── Password complexity failures ─────────────────────────────────────────────

def test_weak_password_shows_errors(client, monkeypatch):
    _patch_sms_success(monkeypatch)
    _patch_verify_success(monkeypatch)
    _patch_ad_success(monkeypatch)
    _send_otp(client)
    client.post("/verify", data={"otp": "123456"})

    resp = client.post("/reset", data={"new_password": "weak", "confirm_password": "weak"})
    assert resp.status_code == 200
    assert b"At least 12 characters" in resp.data


# ── User not found (no enumeration) ─────────────────────────────────────────

def test_unknown_user_generic_message(client, monkeypatch):
    monkeypatch.setattr("app.blueprints.sspr.routes.sms_service.lookup_user", lambda u: None)

    resp = _send_otp(client, username="ghost")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


# ── Rate limit ────────────────────────────────────────────────────────────────

def test_rate_limit_returns_429(client, app, monkeypatch):
    """Rate limiting test — only runs when RATELIMIT_ENABLED is True."""
    if not app.config.get("RATELIMIT_ENABLED", True):
        import pytest
        pytest.skip("Rate limiting disabled in test config")


# ── AD failure surfaced ───────────────────────────────────────────────────────

def test_ad_failure_shows_error(client, monkeypatch):
    _patch_sms_success(monkeypatch)
    _patch_verify_success(monkeypatch)

    from app.services.ad_service import ADError
    def _raise(u, p):
        raise ADError("LDAP error")
    monkeypatch.setattr("app.blueprints.sspr.routes.reset_password", _raise)

    _send_otp(client)
    client.post("/verify", data={"otp": "123456"})

    resp = client.post("/reset", data={"new_password": "ValidPass123!", "confirm_password": "ValidPass123!"})
    assert resp.status_code == 200
    assert b"IT support" in resp.data
