from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import base64
import io
import mimetypes
import zipfile
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

import fitz

from backend.config import settings
from backend.converters.builtins import converter_registry
from backend.database import store
from backend.security.dependencies import current_user, require_csrf
from backend.security.rate_limit import auth_limiter
from backend.services.conversion_service import create_and_run_job, delete_job_files, public_job, run_job
from backend.services.storage_service import storage
from backend.utils.file_validator import FileValidationError, sanitize_filename, validate_upload

router = APIRouter(prefix="/api", tags=["conversions"])


def _owned_job(job_id: str, user: dict) -> dict:
    job = store.job_by_id(job_id, user["_id"])
    if not job or job["status"] == "deleted":
        raise HTTPException(status_code=404, detail="Conversion not found.")
    if job["expires_at"] <= datetime.now(timezone.utc):
        delete_job_files(job)
        store.update_job(job_id, user["_id"], {"status": "deleted", "source_storage_key": None, "output_storage_key": None})
        raise HTTPException(status_code=410, detail="This conversion has expired and its files were deleted.")
    return job


@router.post("/conversions", status_code=201, dependencies=[Depends(require_csrf)])
async def create_conversion(
    conversion_type: str = Form(...),
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] = File(default=[]),
    page_range: str = Form(default=""),
    user: dict = Depends(current_user),
) -> dict:
    if os.getenv("VERCEL"):
        raise HTTPException(status_code=503, detail="Document processing requires a process-capable worker. Use the container runtime.")
    converter = converter_registry.get(conversion_type)
    auth_limiter.check(f"conversion:{user['_id']}", 20, 60)
    if not converter:
        raise HTTPException(status_code=422, detail="This conversion is not supported.")
    uploads = ([file] if file else []) + files
    if not uploads:
        raise HTTPException(status_code=400, detail="Choose at least one file.")
    if len(uploads) > 20 or (len(uploads) > 1 and not converter.supports_multiple_files):
        raise HTTPException(status_code=400, detail="This conversion does not accept this number of files.")
    validated = [await validate_upload(
        upload, set(converter.source_extensions), converter.accepted_mime_types, converter.maximum_file_size
    ) for upload in uploads]
    if sum(len(item[2]) for item in validated) > converter.maximum_file_size:
        raise FileValidationError("Combined uploads exceed the configured size limit.", 413)
    if conversion_type == "merge-pdf":
        total_pages = 0
        for _, _, data in validated:
            document = fitz.open(stream=data, filetype="pdf"); total_pages += document.page_count; document.close()
        if total_pages > settings.max_pdf_pages:
            raise FileValidationError("Combined PDF pages exceed the configured page limit.", 413)
    filename, extension, data = validated[0]
    job = await create_and_run_job(user["_id"], filename, extension, data, conversion_type, validated[1:], {"page_range": page_range})
    return {"job": public_job(job)}


@router.get("/conversions/{job_id}")
def conversion_detail(job_id: str, user: dict = Depends(current_user)) -> dict:
    return {"job": public_job(_owned_job(job_id, user))}


@router.get("/conversions/{job_id}/download")
def download_conversion(job_id: str, user: dict = Depends(current_user)) -> Response:
    job = _owned_job(job_id, user)
    if job["status"] != "completed" or not job.get("output_storage_key"):
        raise HTTPException(status_code=409, detail="The converted file is not available.")
    try:
        data = storage.get(job["output_storage_key"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="The converted file has expired.") from exc
    converter = converter_registry.require(job["converter_id"])
    return Response(data, media_type=job.get("output_mime_type", converter.output_mime_type), headers={
        "Content-Disposition": f'attachment; filename="{job["output_filename"]}"',
        "X-Output-Filename": job["output_filename"],
    })


@router.get("/conversions/{job_id}/preview")
def preview_conversion(job_id: str, user: dict = Depends(current_user)) -> dict:
    job = _owned_job(job_id, user)
    if job["converter_id"] != "to-markdown" or job["status"] != "completed":
        raise HTTPException(status_code=422, detail="Preview is available only for completed Markdown conversions.")
    with zipfile.ZipFile(io.BytesIO(storage.get(job["output_storage_key"]))) as archive:
        markdown_name = next(name for name in archive.namelist() if name.endswith(".md"))
        assets = [{"filename": name, "content_type": mimetypes.guess_type(name)[0] or "application/octet-stream", "data": base64.b64encode(archive.read(name)).decode("ascii"), "alt_text": "Extracted document image"} for name in archive.namelist() if name.startswith("images/")]
        return {"markdown": archive.read(markdown_name).decode("utf-8"), "assets": assets}


@router.post("/conversions/{job_id}/retry", dependencies=[Depends(require_csrf)])
async def retry_conversion(job_id: str, user: dict = Depends(current_user)) -> dict:
    job = _owned_job(job_id, user)
    if job["status"] == "processing":
        raise HTTPException(status_code=409, detail="This conversion is already processing.")
    storage.delete(job.get("output_storage_key"))
    auth_limiter.check(f"conversion:{user['_id']}", 20, 60)
    refreshed = store.update_job_if_status(job_id, user["_id"], ["completed", "failed"], {"status": "queued", "progress": 0, "output_storage_key": None})
    if not refreshed:
        raise HTTPException(status_code=409, detail="This conversion cannot be retried now.")
    return {"job": public_job(await run_job(refreshed))}


@router.patch("/conversions/{job_id}", dependencies=[Depends(require_csrf)])
def rename_conversion(job_id: str, output_filename: str = Form(...), user: dict = Depends(current_user)) -> dict:
    job = _owned_job(job_id, user)
    converter = converter_registry.require(job["converter_id"])
    cleaned = sanitize_filename(output_filename)
    output_extension = Path(job.get("output_filename") or "").suffix or converter.target_extension
    if Path(cleaned).suffix.lower() != output_extension:
        cleaned = f"{Path(cleaned).stem}{output_extension}"
    updated = store.update_job(job_id, user["_id"], {"output_filename": cleaned}) or job
    return {"job": public_job(updated)}


@router.delete("/conversions/{job_id}", status_code=204, response_class=Response, dependencies=[Depends(require_csrf)])
def delete_conversion(job_id: str, response: Response, user: dict = Depends(current_user)) -> Response:
    job = _owned_job(job_id, user)
    delete_job_files(job)
    store.update_job(job_id, user["_id"], {
        "status": "deleted", "progress": 100, "source_storage_key": None, "output_storage_key": None
    })
    response.status_code = 204
    return response


@router.get("/history")
def history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = "",
    source_format: str = "",
    target_format: str = "",
    status: str = "",
    sort: str = Query("newest", pattern="^(newest|oldest)$"),
    user: dict = Depends(current_user),
) -> dict:
    raw_jobs = store.list_jobs(
        user["_id"], search=search, source_format=source_format, target_format=target_format,
        status=status, newest=sort == "newest"
    )
    jobs = []
    now = datetime.now(timezone.utc)
    for job in raw_jobs:
        if job["status"] == "deleted":
            continue
        if job["expires_at"] <= now:
            delete_job_files(job)
            store.update_job(job["_id"], user["_id"], {"status": "deleted", "source_storage_key": None, "output_storage_key": None})
            continue
        jobs.append(job)
    start = (page - 1) * page_size
    return {"items": [public_job(job) for job in jobs[start:start + page_size]], "total": len(jobs), "page": page, "page_size": page_size}


@router.delete("/history", status_code=204, response_class=Response, dependencies=[Depends(require_csrf)])
def clear_history(response: Response, user: dict = Depends(current_user)) -> Response:
    for job in store.list_jobs(user["_id"]):
        if job["status"] != "deleted":
            delete_job_files(job)
            store.update_job(job["_id"], user["_id"], {"status": "deleted", "source_storage_key": None, "output_storage_key": None})
    response.status_code = 204
    return response


@router.delete("/history/{job_id}", status_code=204, response_class=Response, dependencies=[Depends(require_csrf)])
def delete_history_item(job_id: str, response: Response, user: dict = Depends(current_user)) -> Response:
    return delete_conversion(job_id, response, user)
