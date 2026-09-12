from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.config import settings


class DataStore:
    """Small repository boundary with an in-memory local/test implementation."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.users: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.jobs: dict[str, dict[str, Any]] = {}

    def reset(self) -> None:
        with self._lock:
            self.users.clear()
            self.sessions.clear()
            self.jobs.clear()

    def create_user(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if any(user["normalized_email"] == values["normalized_email"] for user in self.users.values()):
                raise ValueError("DUPLICATE_EMAIL")
            record = {"_id": uuid4().hex, **values}
            self.users[record["_id"]] = record
            return deepcopy(record)

    def user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._lock:
            return deepcopy(next((u for u in self.users.values() if u["normalized_email"] == email), None))

    def user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            return deepcopy(self.users.get(user_id))

    def update_user(self, user_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            if user_id not in self.users:
                return None
            self.users[user_id].update(values)
            return deepcopy(self.users[user_id])

    def delete_user(self, user_id: str) -> None:
        with self._lock:
            self.users.pop(user_id, None)
            self.sessions = {key: value for key, value in self.sessions.items() if value["user_id"] != user_id}
            self.jobs = {key: value for key, value in self.jobs.items() if value["user_id"] != user_id}

    def create_session(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = {"_id": uuid4().hex, **values}
            self.sessions[record["_id"]] = record
            return deepcopy(record)

    def session_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        with self._lock:
            return deepcopy(next((s for s in self.sessions.values() if s["token_hash"] == token_hash), None))

    def revoke_session(self, session_id: str) -> None:
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id]["revoked_at"] = datetime.now(timezone.utc)

    def consume_session(self, session_id: str) -> bool:
        with self._lock:
            session = self.sessions.get(session_id)
            if not session or session.get("revoked_at"):
                return False
            session["revoked_at"] = datetime.now(timezone.utc)
            return True

    def revoke_user_sessions(self, user_id: str) -> None:
        with self._lock:
            for session in self.sessions.values():
                if session["user_id"] == user_id and not session.get("revoked_at"):
                    session["revoked_at"] = datetime.now(timezone.utc)

    def create_job(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = {"_id": uuid4().hex, **values}
            self.jobs[record["_id"]] = record
            return deepcopy(record)

    def job_by_id(self, job_id: str, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self.jobs.get(job_id)
            return deepcopy(job) if job and job["user_id"] == user_id else None

    def update_job(self, job_id: str, user_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            job = self.jobs.get(job_id)
            if not job or job["user_id"] != user_id:
                return None
            job.update(values)
            return deepcopy(job)

    def update_job_if_status(self, job_id: str, user_id: str, statuses: list[str], values: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            job = self.jobs.get(job_id)
            if not job or job["user_id"] != user_id or job["status"] not in statuses:
                return None
            job.update(values)
            return deepcopy(job)

    def list_jobs(
        self,
        user_id: str,
        *,
        search: str = "",
        source_format: str = "",
        target_format: str = "",
        status: str = "",
        newest: bool = True,
    ) -> list[dict[str, Any]]:
        with self._lock:
            jobs = [deepcopy(job) for job in self.jobs.values() if job["user_id"] == user_id]
        if search:
            jobs = [job for job in jobs if search.lower() in job["source_filename"].lower()]
        if source_format:
            jobs = [job for job in jobs if job["source_format"] == source_format]
        if target_format:
            jobs = [job for job in jobs if job["target_format"] == target_format]
        if status:
            jobs = [job for job in jobs if job["status"] == status]
        return sorted(jobs, key=lambda job: job["created_at"], reverse=newest)

    def expired_jobs(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        with self._lock:
            return [deepcopy(job) for job in self.jobs.values() if job["expires_at"] <= now and job["status"] != "deleted"]


class MongoDataStore:
    def __init__(self, uri: str, database: str) -> None:
        from pymongo import ASCENDING, DESCENDING, MongoClient

        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
        self.db = self.client[database]
        self.users = self.db.users
        self.sessions = self.db.refresh_sessions
        self.jobs = self.db.conversion_jobs
        self.users.create_index("normalized_email", unique=True)
        self.jobs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self.jobs.create_index("status")
        self.sessions.create_index("token_hash", unique=True)
        self.sessions.create_index("expires_at", expireAfterSeconds=0)

    def reset(self) -> None:
        raise RuntimeError("Resetting a MongoDB-backed store is not allowed.")

    def create_user(self, values: dict[str, Any]) -> dict[str, Any]:
        from pymongo.errors import DuplicateKeyError
        record = {"_id": uuid4().hex, **values}
        try:
            self.users.insert_one(record)
        except DuplicateKeyError as exc:
            raise ValueError("DUPLICATE_EMAIL") from exc
        return record

    def user_by_email(self, email: str) -> dict[str, Any] | None: return self.users.find_one({"normalized_email": email})
    def user_by_id(self, user_id: str) -> dict[str, Any] | None: return self.users.find_one({"_id": user_id})
    def update_user(self, user_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        from pymongo import ReturnDocument
        return self.users.find_one_and_update({"_id": user_id}, {"$set": values}, return_document=ReturnDocument.AFTER)
    def delete_user(self, user_id: str) -> None:
        self.users.delete_one({"_id": user_id}); self.sessions.delete_many({"user_id": user_id}); self.jobs.delete_many({"user_id": user_id})
    def create_session(self, values: dict[str, Any]) -> dict[str, Any]:
        record = {"_id": uuid4().hex, **values}; self.sessions.insert_one(record); return record
    def session_by_hash(self, value: str) -> dict[str, Any] | None: return self.sessions.find_one({"token_hash": value})
    def revoke_session(self, session_id: str) -> None: self.sessions.update_one({"_id": session_id}, {"$set": {"revoked_at": datetime.now(timezone.utc)}})
    def consume_session(self, session_id: str) -> bool:
        result = self.sessions.update_one({"_id": session_id, "revoked_at": None}, {"$set": {"revoked_at": datetime.now(timezone.utc)}})
        return bool(result.modified_count)
    def revoke_user_sessions(self, user_id: str) -> None: self.sessions.update_many({"user_id": user_id, "revoked_at": None}, {"$set": {"revoked_at": datetime.now(timezone.utc)}})
    def create_job(self, values: dict[str, Any]) -> dict[str, Any]:
        record = {"_id": uuid4().hex, **values}; self.jobs.insert_one(record); return record
    def job_by_id(self, job_id: str, user_id: str) -> dict[str, Any] | None: return self.jobs.find_one({"_id": job_id, "user_id": user_id})
    def update_job(self, job_id: str, user_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        from pymongo import ReturnDocument
        return self.jobs.find_one_and_update({"_id": job_id, "user_id": user_id}, {"$set": values}, return_document=ReturnDocument.AFTER)
    def update_job_if_status(self, job_id: str, user_id: str, statuses: list[str], values: dict[str, Any]) -> dict[str, Any] | None:
        from pymongo import ReturnDocument
        return self.jobs.find_one_and_update({"_id": job_id, "user_id": user_id, "status": {"$in": statuses}}, {"$set": values}, return_document=ReturnDocument.AFTER)
    def list_jobs(self, user_id: str, *, search: str = "", source_format: str = "", target_format: str = "", status: str = "", newest: bool = True) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"user_id": user_id}
        if search: query["source_filename"] = {"$regex": re_escape(search), "$options": "i"}
        if source_format: query["source_format"] = source_format
        if target_format: query["target_format"] = target_format
        if status: query["status"] = status
        return list(self.jobs.find(query).sort("created_at", -1 if newest else 1))
    def expired_jobs(self) -> list[dict[str, Any]]:
        return list(self.jobs.find({"expires_at": {"$lte": datetime.now(timezone.utc)}, "status": {"$ne": "deleted"}}))


def re_escape(value: str) -> str:
    import re
    return re.escape(value)


store: DataStore | MongoDataStore = MongoDataStore(settings.mongodb_uri, settings.mongodb_database) if settings.mongodb_uri else DataStore()


def mongo_is_configured() -> bool: return isinstance(store, MongoDataStore)
