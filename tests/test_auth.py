from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.database import store
from backend.main import app
from backend.security.rate_limit import auth_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_store() -> None:
    store.reset()
    auth_limiter.reset()
    client.cookies.clear()


def signup(email: str = "naresh@example.com", password: str = "StrongPass123"):
    return client.post("/api/auth/signup", json={
        "email": email,
        "password": password,
        "display_name": "Naresh",
    })


def csrf_headers() -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("filemorph_csrf")}


def test_signup_creates_authenticated_session_without_exposing_password() -> None:
    response = signup()
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "naresh@example.com"
    assert "password" not in response.text
    assert client.cookies.get("filemorph_access")
    assert client.get("/api/auth/me").status_code == 200


def test_duplicate_email_is_normalized_and_rejected() -> None:
    assert signup().status_code == 201
    client.cookies.clear()
    response = signup("  NARESH@example.com  ")
    assert response.status_code == 409


def test_login_rejects_invalid_credentials() -> None:
    signup()
    client.cookies.clear()
    response = client.post("/api/auth/login", json={"email": "naresh@example.com", "password": "WrongPass123"})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Email or password is incorrect."


def test_refresh_rotates_session_and_logout_revokes_it() -> None:
    signup()
    old_refresh = client.cookies.get("filemorph_refresh")
    response = client.post("/api/auth/refresh", headers=csrf_headers())
    assert response.status_code == 200
    assert client.cookies.get("filemorph_refresh") != old_refresh
    response = client.post("/api/auth/logout", headers=csrf_headers())
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_refresh_and_logout_require_csrf_header() -> None:
    signup()
    assert client.post("/api/auth/refresh").status_code == 403
    assert client.post("/api/auth/logout").status_code == 403


def test_password_change_invalidates_existing_access_token() -> None:
    signup()
    response = client.patch("/api/users/me/password", json={"current_password": "StrongPass123", "new_password": "NewStrongPass123"}, headers=csrf_headers())
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_cookie_flags_and_error_request_id() -> None:
    response = signup()
    cookies = response.headers.get_list("set-cookie")
    assert any("HttpOnly" in cookie and "filemorph_access" in cookie for cookie in cookies)
    client.cookies.clear()
    error = client.get("/api/auth/me")
    assert error.json()["error"]["request_id"] == error.headers["X-Request-ID"]
