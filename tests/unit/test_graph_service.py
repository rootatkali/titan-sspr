"""Unit tests for graph_service (all external calls mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_lookup_user_returns_user(app):
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"id": "abc123", "displayName": "Alice"}
    fake_resp.raise_for_status = MagicMock()

    with app.app_context():
        with patch("app.services.graph_service.get_access_token", return_value="tok"):
            with patch("requests.get", return_value=fake_resp):
                from app.services.graph_service import lookup_user
                result = lookup_user("alice")
                assert result["id"] == "abc123"


def test_lookup_user_returns_none_on_404(app):
    fake_resp = MagicMock()
    fake_resp.status_code = 404

    with app.app_context():
        with patch("app.services.graph_service.get_access_token", return_value="tok"):
            with patch("requests.get", return_value=fake_resp):
                from app.services.graph_service import lookup_user
                result = lookup_user("nobody")
                assert result is None


def test_send_otp_via_teams(app):
    fake_chat_resp = MagicMock()
    fake_chat_resp.status_code = 201
    fake_chat_resp.json.return_value = {"id": "chat-id-1"}
    fake_chat_resp.raise_for_status = MagicMock()

    fake_msg_resp = MagicMock()
    fake_msg_resp.status_code = 201
    fake_msg_resp.raise_for_status = MagicMock()

    with app.app_context():
        with patch("app.services.graph_service.get_access_token", return_value="tok"):
            with patch("requests.post", side_effect=[fake_chat_resp, fake_msg_resp]):
                from app.services.graph_service import send_otp_via_teams
                send_otp_via_teams("user-id-1", "123456")  # should not raise
