from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.database import store
from backend.schemas.user import PasswordUpdate, ProfileUpdate
from backend.security.dependencies import current_user, require_csrf
from backend.security.passwords import hash_password, verify_password
from backend.services.conversion_service import delete_job_files

router = APIRouter(prefix="/api/users", tags=["users"])


def _public(user: dict) -> dict:
    return {"id": user["_id"], "email": user["email"], "display_name": user["display_name"], "created_at": user["created_at"].isoformat()}


@router.get("/me")
def get_profile(user: dict = Depends(current_user)) -> dict:
    return {"user": _public(user)}


@router.patch("/me", dependencies=[Depends(require_csrf)])
def update_profile(payload: ProfileUpdate, user: dict = Depends(current_user)) -> dict:
    updated = store.update_user(user["_id"], {"display_name": payload.display_name, "updated_at": datetime.now(timezone.utc)})
    return {"user": _public(updated or user)}


@router.patch("/me/password", status_code=204, response_class=Response, dependencies=[Depends(require_csrf)])
def update_password(payload: PasswordUpdate, response: Response, user: dict = Depends(current_user)) -> Response:
    if not verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    store.update_user(user["_id"], {"password_hash": hash_password(payload.new_password), "auth_version": user.get("auth_version", 0) + 1, "updated_at": datetime.now(timezone.utc)})
    store.revoke_user_sessions(user["_id"])
    response.status_code = 204
    return response


@router.delete("/me", status_code=204, response_class=Response, dependencies=[Depends(require_csrf)])
def delete_account(response: Response, user: dict = Depends(current_user)) -> Response:
    for job in store.list_jobs(user["_id"]):
        delete_job_files(job)
    store.delete_user(user["_id"])
    for name in ("filemorph_access", "filemorph_refresh", "filemorph_csrf"):
        response.delete_cookie(name, path="/")
    response.status_code = 204
    return response
