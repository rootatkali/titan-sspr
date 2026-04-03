"""Unit tests for otp_service."""
from __future__ import annotations

from time import time

import pytest

from app.services.otp_service import (
    OTPResult,
    clear_otp,
    generate_otp,
    store_otp,
    validate_otp,
)


def test_generate_otp_is_6_digits():
    otp = generate_otp()
    assert len(otp) == 6
    assert otp.isdigit()


def test_generate_otp_is_zero_padded():
    # Run many times to catch edge cases where randbelow returns <100000
    for _ in range(200):
        otp = generate_otp()
        assert len(otp) == 6


def test_store_and_validate_valid_otp():
    session = {}
    store_otp(session, "123456", expiry_seconds=600, max_attempts=3)
    result = validate_otp(session, "123456")
    assert result == OTPResult.VALID
    assert "otp" not in session  # cleared on success


def test_validate_invalid_otp_increments_attempts():
    session = {}
    store_otp(session, "123456", expiry_seconds=600, max_attempts=3)
    result = validate_otp(session, "000000")
    assert result == OTPResult.INVALID
    assert session["otp"]["attempts"] == 1


def test_validate_max_attempts_clears_otp():
    session = {}
    store_otp(session, "123456", expiry_seconds=600, max_attempts=3)
    validate_otp(session, "000000")
    validate_otp(session, "000000")
    result = validate_otp(session, "000000")
    assert result == OTPResult.MAX_ATTEMPTS
    assert "otp" not in session


def test_validate_expired_otp():
    session = {}
    store_otp(session, "123456", expiry_seconds=-1, max_attempts=3)
    result = validate_otp(session, "123456")
    assert result == OTPResult.EXPIRED
    assert "otp" not in session


def test_validate_no_otp_in_session():
    session = {}
    result = validate_otp(session, "123456")
    assert result == OTPResult.NOT_FOUND


def test_clear_otp():
    session = {}
    store_otp(session, "123456", expiry_seconds=600, max_attempts=3)
    clear_otp(session)
    assert "otp" not in session


def test_second_valid_attempt_after_partial_failure():
    session = {}
    store_otp(session, "123456", expiry_seconds=600, max_attempts=3)
    validate_otp(session, "000000")  # 1 wrong
    result = validate_otp(session, "123456")  # correct
    assert result == OTPResult.VALID
