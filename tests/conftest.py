"""Shared pytest fixtures."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from argon2 import PasswordHasher

_ph = PasswordHasher()
_ADMIN_PASS = "adminpass123"
_ADMIN_HASH = _ph.hash(_ADMIN_PASS)


TEST_CONFIG = {
    "TESTING": True,
    "WTF_CSRF_ENABLED": False,
    "SECRET_KEY": "test-secret-key-not-for-production",
    "SESSION_TYPE": "null",
    "SESSION_PERMANENT": False,
    "OTP_EXPIRY_SECONDS": 600,
    "OTP_MAX_ATTEMPTS": 3,
    "RATELIMIT_ENABLED": False,
    "RATELIMIT_OTP_SEND": "1000 per hour",
    "RATELIMIT_STORAGE_URI": "memory://",
    "AZURE_TENANT_ID": "test-tenant",
    "AZURE_CLIENT_ID": "test-client",
    "AZURE_CLIENT_SECRET": "test-secret",
    "AZURE_BOT_USER_ID": "bot-user-id",
    "M365_DOMAIN": "test.example.com",
    "LDAP_SERVER": "ldap.test.local",
    "LDAP_PORT": 636,
    "LDAP_CA_CERT_PATH": "/fake/ca.pem",
    "LDAP_SERVICE_ACCOUNT_DN": "CN=svc,DC=test,DC=local",
    "LDAP_SERVICE_ACCOUNT_PASS": "svcpass",
    "LDAP_SEARCH_BASE": "DC=test,DC=local",
    "LDAP_USER_SEARCH_FILTER": "(sAMAccountName={username})",
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD_HASH": _ADMIN_HASH,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "HOST": "127.0.0.1",
    "PORT": 8080,
}


@pytest.fixture()
def app():
    from app import create_app
    flask_app = create_app(test_config=TEST_CONFIG)
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def mock_graph(monkeypatch):
    """Patch graph_service so no real Graph calls happen."""
    fake_user = {"id": "fake-user-id-123", "displayName": "Test User", "userPrincipalName": "testuser@test.example.com"}

    monkeypatch.setattr("app.services.graph_service.lookup_user", lambda username: fake_user)
    monkeypatch.setattr("app.services.graph_service.send_otp_via_teams", lambda user_id, otp: None)
    return fake_user


@pytest.fixture()
def mock_ad(monkeypatch):
    """Patch ad_service so no real LDAP calls happen."""
    monkeypatch.setattr("app.blueprints.sspr.routes.reset_password", lambda username, pw: None)


ADMIN_CREDENTIALS = (_ADMIN_PASS, "admin")
