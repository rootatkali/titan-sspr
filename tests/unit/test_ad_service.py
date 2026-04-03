"""Unit tests for ad_service (ldap3 mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.ad_service import ADError


def _make_fake_entry(dn: str):
    entry = MagicMock()
    entry.distinguishedName.value = dn
    return entry


def test_reset_password_success(app):
    fake_conn = MagicMock()
    fake_conn.entries = [_make_fake_entry("CN=alice,DC=test,DC=local")]
    fake_conn.extend.microsoft.modify_password.return_value = True

    with app.app_context():
        with patch("app.services.ad_service._build_server"):
            with patch("app.services.ad_service.Connection", return_value=fake_conn):
                from app.services.ad_service import reset_password
                reset_password("alice", "ValidPass123!")  # should not raise


def test_reset_password_user_not_found(app):
    fake_conn = MagicMock()
    fake_conn.entries = []

    with app.app_context():
        with patch("app.services.ad_service._build_server"):
            with patch("app.services.ad_service.Connection", return_value=fake_conn):
                from app.services.ad_service import reset_password
                with pytest.raises(ADError, match="not found"):
                    reset_password("nobody", "ValidPass123!")


def test_reset_password_modify_returns_false(app):
    fake_conn = MagicMock()
    fake_conn.entries = [_make_fake_entry("CN=alice,DC=test,DC=local")]
    fake_conn.extend.microsoft.modify_password.return_value = False
    fake_conn.result = {"description": "insufficientAccessRights"}

    with app.app_context():
        with patch("app.services.ad_service._build_server"):
            with patch("app.services.ad_service.Connection", return_value=fake_conn):
                from app.services.ad_service import reset_password
                with pytest.raises(ADError, match="modify_password returned failure"):
                    reset_password("alice", "WeakPass")


def test_reset_password_unbind_always_called(app):
    fake_conn = MagicMock()
    fake_conn.entries = [_make_fake_entry("CN=alice,DC=test,DC=local")]
    fake_conn.extend.microsoft.modify_password.side_effect = Exception("boom")

    with app.app_context():
        with patch("app.services.ad_service._build_server"):
            with patch("app.services.ad_service.Connection", return_value=fake_conn):
                from app.services.ad_service import reset_password
                with pytest.raises(Exception):
                    reset_password("alice", "ValidPass123!")
                fake_conn.unbind.assert_called_once()
