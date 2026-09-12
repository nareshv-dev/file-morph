from __future__ import annotations

from backend.database import store
from backend.services.conversion_service import delete_job_files
from backend.services.storage_service import storage
from backend.config import settings


def cleanup_expired_jobs() -> int:
    jobs = store.expired_jobs()
    for job in jobs:
        delete_job_files(job)
        store.update_job(job["_id"], job["user_id"], {
            "status": "deleted", "source_storage_key": None, "source_storage_keys": [], "output_storage_key": None
        })
    if hasattr(storage, "cleanup_expired_objects"):
        storage.cleanup_expired_objects(settings.file_retention_hours)
    return len(jobs)


if __name__ == "__main__":
    print(f"Removed files for {cleanup_expired_jobs()} expired jobs.")
