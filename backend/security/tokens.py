from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from backend.config import settings


def _encode(user_id: str, kind: str, secret: str, lifetime: timedelta, token_id: str | None = None, version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": user_id,
        "type": kind,
        "jti": token_id or secrets.token_urlsafe(24),
        "iat": now,
        "exp": now + lifetime,
        "ver": version,
    }, secret, algorithm="HS256")


def create_access_token(user_id: str, version: int = 0) -> str:
    return _encode(user_id, "access", settings.jwt_access_secret, timedelta(minutes=settings.access_token_minutes), version=version)


def create_refresh_token(user_id: str) -> str:
    return _encode(user_id, "refresh", settings.jwt_refresh_secret, timedelta(days=settings.refresh_token_days))


def decode_token(token: str, kind: str) -> dict:
    secret = settings.jwt_access_secret if kind == "access" else settings.jwt_refresh_secret
    payload = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["sub", "exp", "iat", "jti", "type"]})
    if payload.get("type") != kind:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_token() -> str:
    return secrets.token_urlsafe(32)
