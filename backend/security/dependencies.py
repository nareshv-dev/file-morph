from __future__ import annotations

import hmac

import jwt
from fastapi import Cookie, Header, HTTPException

from backend.database import store
from backend.security.tokens import decode_token


def current_user(filemorph_access: str | None = Cookie(default=None)) -> dict:
    if not filemorph_access:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = decode_token(filemorph_access, "access")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Authentication required.") from exc
    user = store.user_by_id(str(payload["sub"]))
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Authentication required.")
    if payload.get("ver", 0) != user.get("auth_version", 0):
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def require_csrf(
    filemorph_csrf: str | None = Cookie(default=None),
    x_csrf_token: str | None = Header(default=None),
) -> None:
    if not filemorph_csrf or not x_csrf_token or not hmac.compare_digest(filemorph_csrf, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")
