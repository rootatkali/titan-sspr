"""Integration tests for the admin blueprint."""
from __future__ import annotations

import base64


def _basic_auth_header(username: str, password: str) -> dict:
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


def test_logs_without_auth_returns_401(client):
    resp = client.get("/admin/logs")
    assert resp.status_code == 401


def test_logs_wrong_password_returns_401(client):
    headers = _basic_auth_header("admin", "wrongpassword")
    resp = client.get("/admin/logs", headers=headers)
    assert resp.status_code == 401


def test_logs_wrong_username_returns_401(client):
    headers = _basic_auth_header("notadmin", "adminpass123")
    resp = client.get("/admin/logs", headers=headers)
    assert resp.status_code == 401


def test_logs_correct_credentials_returns_200(client):
    headers = _basic_auth_header("admin", "adminpass123")
    resp = client.get("/admin/logs", headers=headers)
    assert resp.status_code == 200
    assert b"Audit Log" in resp.data


def test_logs_shows_entries(client, app):
    from app.models.audit_log import Action, Outcome
    from app.services import audit_service

    with app.app_context():
        audit_service.log(Action.SEND_OTP, Outcome.SUCCESS, username="audituser", ip_address="9.9.9.9")

    headers = _basic_auth_header("admin", "adminpass123")
    resp = client.get("/admin/logs", headers=headers)
    assert resp.status_code == 200
    assert b"audituser" in resp.data
