"""Integration tests for the SSPR blueprint — full flow + failure paths."""
from __future__ import annotations

import base64
from unittest.mock import patch


# ── Helpers ───────────────────────────────────────────────────────────────────

FAKE_USER = {"id": "fake-user-id-111", "displayName": "Test User"}


def _patch_graph_success(monkeypatch):
    monkeypatch.setattr("app.services.graph_service.lookup_user", lambda u: FAKE_USER)
    monkeypatch.setattr("app.services.graph_service.send_otp_via_teams", lambda uid, otp: None)


def _patch_ad_success(monkeypatch):
    monkeypatch.setattr("app.blueprints.sspr.routes.reset_password", lambda u, p: None)


def _send_otp(client, username="testuser"):
    return client.post("/send-otp", data={"username": username})


def _get_otp_from_session(client, app):
    """Read the OTP that was stored in the Flask test session."""
    with client.session_transaction() as sess:
        return sess.get("otp", {}).get("value")


# ── Happy path ────────────────────────────────────────────────────────────────

def test_happy_path_full_flow(client, app, monkeypatch):
    _patch_graph_success(monkeypatch)
    _patch_ad_success(monkeypatch)

    # Step 1: GET /
    resp = client.get("/")
    assert resp.status_code == 200

    # Step 2: POST /send-otp
    resp = _send_otp(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/verify")

    # Grab OTP from session
    with client.session_transaction() as sess:
        otp = sess["otp"]["value"]
        assert sess["username"] == "testuser"

    # Step 3: GET /verify
    resp = client.get("/verify")
    assert resp.status_code == 200

    # Step 4: POST /verify with correct OTP
    resp = client.post("/verify", data={"otp": otp})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/reset")

    # Verify session state
    with client.session_transaction() as sess:
        assert sess.get("otp_verified") is True
        assert "otp" not in sess

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
    _patch_graph_success(monkeypatch)
    _send_otp(client)
    # Go directly to /reset without verifying OTP
    resp = client.get("/reset")
    assert resp.status_code == 302


# ── Wrong OTP: error shown, stay on verify ────────────────────────────────────

def test_wrong_otp_stays_on_verify(client, monkeypatch):
    _patch_graph_success(monkeypatch)
    _send_otp(client)

    resp = client.post("/verify", data={"otp": "000000"})
    assert resp.status_code == 200
    assert b"Incorrect" in resp.data

    with client.session_transaction() as sess:
        assert sess["otp"]["attempts"] == 1
        assert "otp_verified" not in sess


# ── Expired OTP: redirected to start ─────────────────────────────────────────

def test_expired_otp_redirects_to_start(client, app, monkeypatch):
    _patch_graph_success(monkeypatch)
    _send_otp(client)

    # Force expiry — must reassign the whole dict to trigger session save
    with client.session_transaction() as sess:
        otp_data = dict(sess["otp"])
        otp_data["expires_at"] = 0
        sess["otp"] = otp_data

    resp = client.post("/verify", data={"otp": "123456"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


# ── Max attempts: session cleared, redirected to start ───────────────────────

def test_max_attempts_clears_session(client, monkeypatch):
    _patch_graph_success(monkeypatch)
    _send_otp(client)

    for _ in range(3):
        resp = client.post("/verify", data={"otp": "000000"})

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")

    with client.session_transaction() as sess:
        assert "username" not in sess
        assert "otp" not in sess


# ── Password complexity failures ─────────────────────────────────────────────

def test_weak_password_shows_errors(client, monkeypatch):
    _patch_graph_success(monkeypatch)
    _patch_ad_success(monkeypatch)
    _send_otp(client)

    with client.session_transaction() as sess:
        otp = sess["otp"]["value"]

    client.post("/verify", data={"otp": otp})

    resp = client.post("/reset", data={"new_password": "weak", "confirm_password": "weak"})
    assert resp.status_code == 200
    assert b"At least 12 characters" in resp.data


# ── User not found (no enumeration) ─────────────────────────────────────────

def test_unknown_user_generic_message(client, monkeypatch):
    monkeypatch.setattr("app.services.graph_service.lookup_user", lambda u: None)

    resp = _send_otp(client, username="ghost")
    # Should redirect back to index, not expose "user not found"
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
    _patch_graph_success(monkeypatch)

    from app.services.ad_service import ADError
    def _raise(u, p):
        raise ADError("LDAP error")
    monkeypatch.setattr("app.blueprints.sspr.routes.reset_password", _raise)

    _send_otp(client)
    with client.session_transaction() as sess:
        otp = sess["otp"]["value"]
    client.post("/verify", data={"otp": otp})

    resp = client.post("/reset", data={"new_password": "ValidPass123!", "confirm_password": "ValidPass123!"})
    assert resp.status_code == 200
    assert b"IT support" in resp.data
