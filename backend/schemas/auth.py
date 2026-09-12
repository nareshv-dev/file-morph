from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def bounded_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Use a password no longer than 72 UTF-8 bytes.")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class SignupRequest(Credentials):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Enter your name.")
        return cleaned


class LoginRequest(Credentials):
    pass
