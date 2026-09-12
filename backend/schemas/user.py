from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Enter your name.")
        return cleaned


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("current_password", "new_password")
    @classmethod
    def bounded_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Use a password no longer than 72 UTF-8 bytes.")
        return value
