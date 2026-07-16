"""
Minimal in-memory user service used as the demo target for the CI repair agent.

Known bugs (intentional, for the demo and benchmark):
1. create_user crashes with a KeyError when display_name is omitted, because it
   accesses payload["display_name"] directly instead of using .get().
2. create_user crashes with a KeyError when password is omitted.
3. create_user crashes with a TypeError when password is not a string.
4. create_user crashes with a ValueError when age is not a valid integer.
5. create_user crashes with an AttributeError when username is not a string.
"""

from __future__ import annotations

_USERS: dict[str, dict] = {}


class ValidationError(Exception):
    pass


class DuplicateEmailError(Exception):
    pass


def _validate_email(email: str) -> bool:
    return "@" in email and "." in email.split("@")[-1]


def create_user(payload: dict) -> dict:
    email = payload.get("email", "")

    if not _validate_email(email):
        raise ValidationError("Invalid email address")

    if email in _USERS:
        raise DuplicateEmailError("Email already registered")

    # Bug 1: Access payload["display_name"] directly instead of using .get()
    display_name = payload.get("display_name", None)

    # Bug 2: Missing password validation + KeyError if missing
    password = payload.get("password")
    if password is None:
        raise ValidationError("Password is required")
    # Bug 3: TypeError if password is not a string
    if not isinstance(password, str):
        raise ValidationError("Password must be a string")
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")

    # Bug 4: ValueError if age is not convertible to int
    age = payload.get("age")
    if age is not None:
        try:
            age_int = int(age)
        except (ValueError, TypeError):
            raise ValidationError("Age must be a valid integer")
        if age_int < 18:
            raise ValidationError("User must be at least 18 years old")

    # Bug 5: AttributeError if username is not a string
    username = payload.get("username")
    if username is not None:
        if not isinstance(username, str):
            raise ValidationError("Username must be a string")
        if not username.isalnum():
            raise ValidationError("Username must be alphanumeric")

    user = {
        "email": email,
        "display_name": display_name,
        "password": password,
        "age": age,
        "username": username,
    }
    _USERS[email] = user
    return user


def reset_state() -> None:
    _USERS.clear()