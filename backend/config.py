from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

TESTING = os.getenv("FILEMORPH_TESTING") == "1"
if not TESTING:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development" if TESTING else os.getenv("ENVIRONMENT", "development")
    mongodb_uri: str = "" if TESTING else os.getenv("MONGODB_URI", "")
    mongodb_database: str = os.getenv("MONGODB_DATABASE", "filemorph")
    jwt_access_secret: str = os.getenv("JWT_ACCESS_SECRET") or secrets.token_urlsafe(48)
    jwt_refresh_secret: str = os.getenv("JWT_REFRESH_SECRET") or secrets.token_urlsafe(48)
    access_token_minutes: int = _int("ACCESS_TOKEN_MINUTES", 15)
    refresh_token_days: int = _int("REFRESH_TOKEN_DAYS", 30)
    cors_origins: tuple[str, ...] = tuple(
        item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if item.strip()
    )
    max_file_size_mb: int = _int("MAX_FILE_SIZE_MB", 20)
    max_pdf_pages: int = _int("MAX_PDF_PAGES", 100)
    file_retention_hours: int = _int("FILE_RETENTION_HOURS", 24)
    storage_provider: str = "local" if TESTING else os.getenv("STORAGE_PROVIDER", "local")
    storage_path: Path = (Path(__file__).resolve().parents[1] / Path(os.getenv("STORAGE_PATH", ".filemorph-storage"))).resolve()
    conversion_timeout_seconds: int = _int("CONVERSION_TIMEOUT_SECONDS", 60)
    max_output_size_mb: int = _int("MAX_OUTPUT_SIZE_MB", 50)

    @property
    def secure_cookies(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
if settings.storage_provider not in {"local", "s3"}:
    raise RuntimeError("Unsupported STORAGE_PROVIDER. Choose local or s3.")
if min(settings.max_file_size_mb, settings.max_pdf_pages, settings.file_retention_hours, settings.conversion_timeout_seconds, settings.max_output_size_mb) <= 0:
    raise RuntimeError("Upload, page, retention, and timeout limits must be positive.")
if settings.secure_cookies:
    for name in ("JWT_ACCESS_SECRET", "JWT_REFRESH_SECRET"):
        if len(os.getenv(name, "")) < 32:
            raise RuntimeError(f"{name} must be configured with at least 32 characters in production.")
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is required in production.")
    if settings.storage_provider != "s3":
        raise RuntimeError("Production requires a configured private object-storage provider (STORAGE_PROVIDER=s3).")
    if "*" in settings.cors_origins:
        raise RuntimeError("Credentialed production CORS must list explicit origins.")
