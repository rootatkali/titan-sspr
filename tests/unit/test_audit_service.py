"""Unit tests for audit_service."""
import pytest

from app.models.audit_log import Action, Outcome
from app.services import audit_service


def test_log_creates_entry(app):
    with app.app_context():
        audit_service.log(
            Action.SEND_OTP,
            Outcome.SUCCESS,
            username="testuser",
            ip_address="1.2.3.4",
        )
        entries, total = audit_service.get_logs()
        assert total >= 1
        entry = next((e for e in entries if e.username == "testuser"), None)
        assert entry is not None
        assert entry.action == "SEND_OTP"
        assert entry.outcome == "SUCCESS"


def test_log_failure_entry(app):
    with app.app_context():
        audit_service.log(
            Action.RESET_PASSWORD,
            Outcome.FAILURE,
            username="baduser",
            ip_address="5.6.7.8",
            detail="user not found",
        )
        entries, total = audit_service.get_logs()
        entry = next((e for e in entries if e.username == "baduser"), None)
        assert entry is not None
        assert entry.detail == "user not found"


def test_get_logs_pagination(app):
    with app.app_context():
        for i in range(5):
            audit_service.log(Action.VERIFY_OTP, Outcome.SUCCESS, username=f"user{i}")
        _, total = audit_service.get_logs(page=1, per_page=2)
        assert total >= 5
        entries, _ = audit_service.get_logs(page=1, per_page=2)
        assert len(entries) == 2
