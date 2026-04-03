"""Unit tests for sms_service — all mocked, no real Twilio or LDAP calls."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests as req_lib


# ── lookup_user ───────────────────────────────────────────────────────────────

def _make_entry(mobile=None, telephoneNumber=None, displayName="Alice"):
    entry = MagicMock()
    entry.mobile.value = mobile
    entry.telephoneNumber.value = telephoneNumber
    entry.displayName.value = displayName
    return entry


def _make_conn(entries):
    conn = MagicMock()
    conn.entries = entries
    return conn


def test_lookup_user_returns_dict_with_mobile(app):
    entry = _make_entry(mobile="+15550001234", telephoneNumber="+15559999999")
    with app.app_context(), \
         patch("app.services.sms_service.Tls"), \
         patch("app.services.sms_service.Server"), \
         patch("app.services.sms_service.Connection", return_value=_make_conn([entry])):
        from app.services import sms_service
        result = sms_service.lookup_user("alice")
    assert result == {"phone": "+15550001234", "displayName": "Alice"}


def test_lookup_user_falls_back_to_telephoneNumber(app):
    entry = _make_entry(mobile=None, telephoneNumber="+15559999999")
    with app.app_context(), \
         patch("app.services.sms_service.Tls"), \
         patch("app.services.sms_service.Server"), \
         patch("app.services.sms_service.Connection", return_value=_make_conn([entry])):
        from app.services import sms_service
        result = sms_service.lookup_user("alice")
    assert result["phone"] == "+15559999999"


def test_lookup_user_returns_none_when_user_not_found(app):
    with app.app_context(), \
         patch("app.services.sms_service.Tls"), \
         patch("app.services.sms_service.Server"), \
         patch("app.services.sms_service.Connection", return_value=_make_conn([])):
        from app.services import sms_service
        result = sms_service.lookup_user("ghost")
    assert result is None


def test_lookup_user_returns_none_when_no_phone_attrs(app):
    entry = _make_entry(mobile=None, telephoneNumber=None)
    with app.app_context(), \
         patch("app.services.sms_service.Tls"), \
         patch("app.services.sms_service.Server"), \
         patch("app.services.sms_service.Connection", return_value=_make_conn([entry])):
        from app.services import sms_service
        result = sms_service.lookup_user("alice")
    assert result is None


# ── start_verification ────────────────────────────────────────────────────────

def test_start_verification_calls_twilio(app):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with app.app_context(), patch("app.services.sms_service.requests.post", return_value=mock_resp) as mock_post:
        from app.services import sms_service
        sms_service.start_verification("+15550001234")

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "Verifications" in call_kwargs[0][0]
    assert call_kwargs[1]["data"]["To"] == "+15550001234"
    assert call_kwargs[1]["data"]["Channel"] == "sms"


def test_start_verification_raises_on_error(app):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError("500 Server Error")

    with app.app_context(), patch("app.services.sms_service.requests.post", return_value=mock_resp):
        from app.services import sms_service
        with pytest.raises(req_lib.HTTPError):
            sms_service.start_verification("+15550001234")


# ── check_verification ────────────────────────────────────────────────────────

def test_check_verification_returns_approved(app):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"status": "approved"}

    with app.app_context(), patch("app.services.sms_service.requests.post", return_value=mock_resp):
        from app.services import sms_service
        result = sms_service.check_verification("+15550001234", "123456")
    assert result == "approved"


def test_check_verification_returns_pending(app):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"status": "pending"}

    with app.app_context(), patch("app.services.sms_service.requests.post", return_value=mock_resp):
        from app.services import sms_service
        result = sms_service.check_verification("+15550001234", "000000")
    assert result == "pending"


def test_check_verification_raises_on_404(app):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError("404 Not Found")

    with app.app_context(), patch("app.services.sms_service.requests.post", return_value=mock_resp):
        from app.services import sms_service
        with pytest.raises(req_lib.HTTPError):
            sms_service.check_verification("+15550001234", "123456")


def test_check_verification_raises_on_429(app):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError("429 Too Many Requests")

    with app.app_context(), patch("app.services.sms_service.requests.post", return_value=mock_resp):
        from app.services import sms_service
        with pytest.raises(req_lib.HTTPError):
            sms_service.check_verification("+15550001234", "123456")
