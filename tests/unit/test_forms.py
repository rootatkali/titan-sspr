"""Unit tests for form validation helpers."""
import pytest

from app.blueprints.sspr.forms import validate_password_complexity


@pytest.mark.parametrize("password,expected_errors", [
    ("Short1!", ["At least 12 characters"]),
    ("alllowercasenodigit!!", ["At least one uppercase letter", "At least one digit"]),
    ("ALLUPPERCASENODIGIT!!", ["At least one lowercase letter", "At least one digit"]),
    ("NoSpecialChar1234567", ["At least one special character (!@#$%^&* etc.)"]),
    ("ValidPass123!", []),
    ("AnotherValidP@ss1", []),
    ("short", ["At least 12 characters", "At least one uppercase letter", "At least one digit", "At least one special character (!@#$%^&* etc.)"]),
])
def test_password_complexity(password, expected_errors):
    errors = validate_password_complexity(password)
    for expected in expected_errors:
        assert expected in errors, f"Expected error '{expected}' not found in {errors}"
    # Ensure no unexpected errors for valid passwords
    if not expected_errors:
        assert errors == []
