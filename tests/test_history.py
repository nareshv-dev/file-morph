from __future__ import annotations

import fitz
import io
import pytest
from fastapi.testclient import TestClient

from backend.database import store
from backend.main import app
from backend.security.rate_limit import auth_limiter
from PIL import Image
from backend.services.storage_service import LocalStorageService
from datetime import datetime, timedelta, timezone

client = TestClient(app)


def make_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "History sample")
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture(autouse=True)
def clean_store(tmp_path, monkeypatch) -> None:
    store.reset()
    auth_limiter.reset()
    client.cookies.clear()
    local = LocalStorageService(tmp_path)
    monkeypatch.setattr("backend.services.conversion_service.storage", local)
    monkeypatch.setattr("backend.api.conversions.storage", local)


def signup(email: str) -> None:
    response = client.post("/api/auth/signup", json={
        "email": email, "password": "StrongPass123", "display_name": "History User"
    })
    assert response.status_code == 201


def csrf_headers() -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("filemorph_csrf")}


def create_job(converter: str = "pdf-to-docx") -> dict:
    response = client.post(
        "/api/conversions",
        data={"conversion_type": converter},
        files={"file": ("history.pdf", make_pdf(), "application/pdf")},
        headers=csrf_headers(),
    )
    assert response.status_code == 201
    return response.json()["job"]


def test_conversion_creates_history_and_download() -> None:
    signup("one@example.com")
    job = create_job()
    assert job["status"] == "completed"
    history = client.get("/api/history").json()
    assert history["total"] == 1
    response = client.get(f"/api/conversions/{job['id']}/download")
    assert response.status_code == 200
    assert response.content.startswith(b"PK")


def test_history_is_isolated_between_users() -> None:
    signup("one@example.com")
    job = create_job()
    client.cookies.clear()
    signup("two@example.com")
    assert client.get("/api/history").json()["total"] == 0
    assert client.get(f"/api/conversions/{job['id']}").status_code == 404
    assert client.get(f"/api/conversions/{job['id']}/download").status_code == 404
    assert client.post(f"/api/conversions/{job['id']}/retry", headers=csrf_headers()).status_code == 404
    assert client.delete(f"/api/conversions/{job['id']}", headers=csrf_headers()).status_code == 404


def test_delete_removes_download_and_retry_recreates_output() -> None:
    signup("one@example.com")
    job = create_job()
    retried = client.post(f"/api/conversions/{job['id']}/retry", headers=csrf_headers())
    assert retried.status_code == 200
    assert retried.json()["job"]["status"] == "completed"
    deleted = client.delete(f"/api/conversions/{job['id']}", headers=csrf_headers())
    assert deleted.status_code == 204
    assert client.get(f"/api/conversions/{job['id']}/download").status_code == 404


def test_history_search_filter_and_pagination() -> None:
    signup("one@example.com")
    create_job()
    result = client.get("/api/history", params={"search": "history", "source_format": "pdf", "status": "completed", "page_size": 1}).json()
    assert result["total"] == 1
    assert len(result["items"]) == 1


@pytest.mark.parametrize("converter", ["merge-pdf", "images-to-pdf", "split-pdf"])
def test_batch_and_page_range_conversions(converter: str) -> None:
    signup("one@example.com")
    if converter == "images-to-pdf":
        image = Image.new("RGB", (64, 64), "green"); buffer = io.BytesIO(); image.save(buffer, "PNG")
        uploads = [("files", ("one.png", buffer.getvalue(), "image/png")), ("files", ("two.png", buffer.getvalue(), "image/png"))]
    else:
        uploads = [("files", ("one.pdf", make_pdf(), "application/pdf"))]
        if converter == "merge-pdf": uploads.append(("files", ("two.pdf", make_pdf(), "application/pdf")))
    response = client.post("/api/conversions", data={"conversion_type": converter, "page_range": "1"}, files=uploads, headers=csrf_headers())
    assert response.status_code == 201
    job = response.json()["job"]; assert job["status"] == "completed", job
    downloaded = client.get(f"/api/conversions/{job['id']}/download")
    pdf = fitz.open(stream=downloaded.content, filetype="pdf")
    assert pdf.page_count == (1 if converter == "split-pdf" else 2)
    pdf.close()


def test_expiration_removes_files_and_denies_download(tmp_path) -> None:
    signup("one@example.com")
    job = create_job()
    user_id = client.get("/api/auth/me").json()["user"]["id"]
    store.update_job(job["id"], user_id, {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
    response = client.get(f"/api/conversions/{job['id']}/download")
    assert response.status_code == 410
    assert not list(tmp_path.rglob("*.pdf"))
    assert not list(tmp_path.rglob("*.docx"))


def test_account_deletion_removes_jobs_and_files(tmp_path) -> None:
    signup("one@example.com")
    create_job()
    response = client.delete("/api/users/me", headers=csrf_headers())
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert not list(tmp_path.rglob("*.pdf"))
    assert not list(tmp_path.rglob("*.docx"))
    assert not list(tmp_path.rglob("*.tmp"))


def test_markdown_history_download_contains_bundle_assets() -> None:
    import zipfile
    signup("one@example.com")
    job = create_job("to-markdown")
    response = client.get(f"/api/conversions/{job['id']}/download")
    assert response.headers["content-type"] == "application/zip"
    assert job["output_filename"].endswith(".zip")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "history.md" in archive.namelist()
    preview = client.get(f"/api/conversions/{job['id']}/preview")
    assert preview.status_code == 200
    assert "History sample" in preview.json()["markdown"]
