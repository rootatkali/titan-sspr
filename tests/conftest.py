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
    "RATELIMIT_ENABLED": False,
    "RATELIMIT_OTP_SEND": "1000 per hour",
    "RATELIMIT_STORAGE_URI": "memory://",
    "TWILIO_ACCOUNT_SID": "ACtest000000000000000000000000000",
    "TWILIO_AUTH_TOKEN": "test_auth_token",
    "TWILIO_VERIFY_SERVICE_SID": "VAtest000000000000000000000000000",
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
def mock_sms(monkeypatch):
    """Patch sms_service so no real Twilio or LDAP calls happen."""
    fake_user = {"phone": "+15550001234", "displayName": "Test User"}
    monkeypatch.setattr("app.services.sms_service.lookup_user", lambda u: fake_user)
    monkeypatch.setattr("app.services.sms_service.start_verification", lambda phone: None)
    return fake_user


@pytest.fixture()
def mock_ad(monkeypatch):
    """Patch ad_service so no real LDAP calls happen."""
    monkeypatch.setattr("app.blueprints.sspr.routes.reset_password", lambda username, pw: None)


ADMIN_CREDENTIALS = (_ADMIN_PASS, "admin")
