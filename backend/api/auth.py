from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.config import settings
from backend.database import store
from backend.schemas.auth import LoginRequest, SignupRequest
from backend.security.dependencies import current_user, require_csrf
from backend.security.passwords import hash_password, verify_password
from backend.security.rate_limit import rate_limit_auth
from backend.security.tokens import (
    create_access_token,
    create_refresh_token,
    csrf_token,
    decode_token,
    token_hash,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
_DUMMY_PASSWORD_HASH = hash_password("filemorph-dummy-password-for-timing")


def _public_user(user: dict) -> dict:
    return {
        "id": user["_id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "created_at": user["created_at"].isoformat(),
    }


def _set_auth_cookies(response: Response, user_id: str) -> None:
    user = store.user_by_id(user_id) or {}
    access = create_access_token(user_id, user.get("auth_version", 0))
    refresh = create_refresh_token(user_id)
    csrf = csrf_token()
    now = datetime.now(timezone.utc)
    store.create_session({
        "user_id": user_id,
        "token_hash": token_hash(refresh),
        "created_at": now,
        "expires_at": now + timedelta(days=settings.refresh_token_days),
        "revoked_at": None,
    })
    common = {"secure": settings.secure_cookies, "samesite": "lax", "path": "/"}
    response.set_cookie("filemorph_access", access, httponly=True, max_age=settings.access_token_minutes * 60, **common)
    response.set_cookie("filemorph_refresh", refresh, httponly=True, max_age=settings.refresh_token_days * 86400, **common)
    response.set_cookie("filemorph_csrf", csrf, httponly=False, max_age=settings.refresh_token_days * 86400, **common)


def _clear_auth_cookies(response: Response) -> None:
    for name in ("filemorph_access", "filemorph_refresh", "filemorph_csrf"):
        response.delete_cookie(name, path="/", secure=settings.secure_cookies, samesite="lax")


@router.post("/signup", status_code=201, dependencies=[Depends(rate_limit_auth)])
def signup(payload: SignupRequest, response: Response) -> dict:
    now = datetime.now(timezone.utc)
    try:
        user = store.create_user({
            "email": payload.email,
            "normalized_email": payload.email,
            "password_hash": hash_password(payload.password),
            "display_name": payload.display_name,
            "is_active": True,
            "auth_version": 0,
            "created_at": now,
            "updated_at": now,
            "last_login_at": now,
        })
    except ValueError as exc:
        if str(exc) == "DUPLICATE_EMAIL":
            raise HTTPException(status_code=409, detail="An account with these details cannot be created.") from exc
        raise
    _set_auth_cookies(response, user["_id"])
    return {"user": _public_user(user)}


@router.post("/login", dependencies=[Depends(rate_limit_auth)])
def login(payload: LoginRequest, response: Response) -> dict:
    user = store.user_by_email(payload.email)
    verified = verify_password(payload.password, user["password_hash"] if user else _DUMMY_PASSWORD_HASH)
    if not user or not verified or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    now = datetime.now(timezone.utc)
    user = store.update_user(user["_id"], {"last_login_at": now, "updated_at": now}) or user
    _set_auth_cookies(response, user["_id"])
    return {"user": _public_user(user)}


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return {"user": _public_user(user)}


@router.post("/refresh", dependencies=[Depends(require_csrf)])
def refresh(request: Request, response: Response) -> dict:
    raw_token = request.cookies.get("filemorph_refresh")
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = decode_token(raw_token, "refresh")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Authentication required.") from exc
    session = store.session_by_hash(token_hash(raw_token))
    if not session or session.get("revoked_at") or session["expires_at"] <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Authentication required.")
    user = store.user_by_id(str(payload["sub"]))
    if not user or not user.get("is_active", True) or session["user_id"] != user["_id"]:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if not store.consume_session(session["_id"]):
        raise HTTPException(status_code=401, detail="Authentication required.")
    _set_auth_cookies(response, user["_id"])
    return {"user": _public_user(user)}


@router.post("/logout", status_code=204, response_class=Response, dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response) -> Response:
    raw_token = request.cookies.get("filemorph_refresh")
    if raw_token:
        session = store.session_by_hash(token_hash(raw_token))
        if session:
            store.revoke_session(session["_id"])
    _clear_auth_cookies(response)
    response.status_code = 204
    return response
