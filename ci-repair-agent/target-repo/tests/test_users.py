import pytest

from app.user_service import (
    create_user,
    reset_state,
    ValidationError,
    DuplicateEmailError,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_state()
    yield
    reset_state()


def test_create_user_returns_user_without_display_name():
    # This will fail initially because display_name is omitted (Bug 1 - KeyError)
    user = create_user({"email": "alex@example.com", "password": "password123"})
    assert user["email"] == "alex@example.com"
    assert user["display_name"] is None


def test_create_user_with_display_name():
    user = create_user({"email": "alex@example.com", "display_name": "Alex", "password": "password123"})
    assert user["display_name"] == "Alex"


def test_duplicate_email_raises():
    create_user({"email": "alex@example.com", "display_name": "Alex", "password": "password123"})
    with pytest.raises(DuplicateEmailError):
        create_user({"email": "alex@example.com", "display_name": "Alex2", "password": "password123"})


def test_invalid_email_raises():
    with pytest.raises(ValidationError):
        create_user({"email": "not-an-email", "display_name": "Alex", "password": "password123"})


# Tests for New Bugs/Requirements:

def test_create_user_missing_password_raises_validation_error():
    # This will fail initially because password is omitted (Bug 2 - KeyError)
    with pytest.raises(ValidationError, match="Password is required"):
        create_user({"email": "bob@example.com", "display_name": "Bob"})


def test_create_user_short_password_raises_validation_error():
    with pytest.raises(ValidationError, match="Password must be at least 8 characters"):
        create_user({"email": "bob@example.com", "display_name": "Bob", "password": "short"})


def test_create_user_non_string_password_raises_validation_error():
    # This will fail initially because password is an integer (Bug 3 - TypeError)
    with pytest.raises(ValidationError, match="Password must be a string"):
        create_user({"email": "bob@example.com", "display_name": "Bob", "password": 12345678})


def test_create_user_under_18_raises_validation_error():
    with pytest.raises(ValidationError, match="User must be at least 18 years old"):
        create_user({"email": "bob@example.com", "display_name": "Bob", "password": "password123", "age": 17})


def test_create_user_invalid_age_raises_validation_error():
    # This will fail initially because age is not convertible to int (Bug 4 - ValueError)
    with pytest.raises(ValidationError, match="Age must be a valid integer"):
        create_user({"email": "bob@example.com", "display_name": "Bob", "password": "password123", "age": "not-a-number"})


def test_create_user_invalid_username_raises_validation_error():
    with pytest.raises(ValidationError, match="Username must be alphanumeric"):
        create_user({"email": "bob@example.com", "display_name": "Bob", "password": "password123", "username": "bob_special!"})


def test_create_user_non_string_username_raises_validation_error():
    # This will fail initially because username is an integer (Bug 5 - AttributeError)
    with pytest.raises(ValidationError, match="Username must be a string"):
        create_user({"email": "bob@example.com", "display_name": "Bob", "password": "password123", "username": 123})
