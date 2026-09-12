from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.config import settings
from backend.converters.builtins import converter_registry
from backend.database import store
from backend.services.storage_service import storage
from backend.services.conversion_executor import execute_conversion


def public_job(job: dict) -> dict:
    return {
        "id": job["_id"],
        "source_filename": job["source_filename"],
        "source_format": job["source_format"],
        "target_format": job["target_format"],
        "source_size": job["source_size"],
        "output_size": job.get("output_size"),
        "output_filename": job.get("output_filename"),
        "status": job["status"],
        "progress": job["progress"],
        "page_count": job.get("page_count"),
        "fidelity_mode": job["fidelity_mode"],
        "failure_reason": job.get("sanitized_error_message"),
        "created_at": job["created_at"].isoformat(),
        "completed_at": job.get("completed_at").isoformat() if job.get("completed_at") else None,
        "expires_at": job["expires_at"].isoformat(),
    }


async def run_job(job: dict) -> dict:
    converter = converter_registry.require(job["converter_id"])
    claimed = store.update_job_if_status(job["_id"], job["user_id"], ["queued"], {"status": "processing", "progress": 35, "started_at": datetime.now(timezone.utc)})
    if not claimed:
        return store.job_by_id(job["_id"], job["user_id"]) or job
    output_key = None
    try:
        source = storage.get(job["source_storage_key"])
        sources = [storage.get(key) for key in job.get("source_storage_keys", [job["source_storage_key"]])] if converter.convert_batch else [source]
        output = await asyncio.to_thread(execute_conversion, job["converter_id"], sources, job["source_filename"], job.get("options", {}))
        if isinstance(output, dict):
            output_bytes = base64.b64decode(str(output["bundle"]))
            page_count = output.get("page_count")
            output_name = str(output["bundle_filename"])
            output_suffix = ".zip"
            output_mime_type = "application/zip"
        else:
            output_bytes = output
            page_count = None
            output_name = f"{Path(job['source_filename']).stem}{converter.target_extension}"
            output_suffix = converter.target_extension
            output_mime_type = converter.output_mime_type
        output_key = storage.put(job["user_id"], output_bytes, output_suffix)
        completed = store.update_job_if_status(job["_id"], job["user_id"], ["processing"], {
            "status": "completed",
            "progress": 100,
            "output_storage_key": output_key,
            "output_filename": output_name,
            "output_size": len(output_bytes),
            "output_mime_type": output_mime_type,
            "page_count": page_count,
            "completed_at": datetime.now(timezone.utc),
            "error_code": None,
            "sanitized_error_message": None,
        })
        if not completed:
            storage.delete(output_key)
            return store.job_by_id(job["_id"], job["user_id"]) or {**job, "status": "deleted"}
        return completed
    except Exception as exc:
        if output_key:
            storage.delete(output_key)
        return store.update_job_if_status(job["_id"], job["user_id"], ["processing"], {
            "status": "failed",
            "progress": 100,
            "error_code": "CONVERSION_FAILED",
            "sanitized_error_message": "Conversion exceeded the processing time limit. Try a smaller file." if isinstance(exc, TimeoutError) else str(exc) if isinstance(exc, ValueError) else "The document could not be converted.",
        }) or store.job_by_id(job["_id"], job["user_id"]) or {**job, "status": "deleted"}


async def create_and_run_job(
    user_id: str, filename: str, extension: str, data: bytes, converter_id: str,
    additional_sources: list[tuple[str, str, bytes]] | None = None,
    options: dict[str, object] | None = None,
) -> dict:
    converter = converter_registry.require(converter_id)
    now = datetime.now(timezone.utc)
    source_keys: list[str] = []
    try:
        for _, suffix, content in [(filename, extension, data), *(additional_sources or [])]:
            source_keys.append(storage.put(user_id, content, suffix))
    except Exception:
        for key in source_keys: storage.delete(key)
        raise
    source_key, extra_keys = source_keys[0], source_keys[1:]
    job = _create_job_record({
        "user_id": user_id,
        "converter_id": converter_id,
        "source_filename": filename,
        "safe_source_filename": filename,
        "source_format": extension.removeprefix("."),
        "target_format": converter.target_extension.removeprefix("."),
        "source_size": len(data) + sum(len(item[2]) for item in (additional_sources or [])),
        "output_size": None,
        "status": "queued",
        "progress": 0,
        "source_storage_key": source_key,
        "source_storage_keys": [source_key, *extra_keys],
        "source_filenames": [filename, *(item[0] for item in (additional_sources or []))],
        "options": options or {},
        "output_storage_key": None,
        "output_filename": None,
        "page_count": None,
        "fidelity_mode": converter.fidelity_description,
        "error_code": None,
        "sanitized_error_message": None,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "expires_at": now + timedelta(hours=settings.file_retention_hours),
    })
    return await run_job(job)


def _create_job_record(values: dict) -> dict:
    try:
        return store.create_job(values)
    except Exception:
        delete_job_files(values)
        raise


def delete_job_files(job: dict) -> None:
    for key in job.get("source_storage_keys", [job.get("source_storage_key")]):
        storage.delete(key)
    storage.delete(job.get("output_storage_key"))
