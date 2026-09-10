from __future__ import annotations

import re
from pathlib import Path

from fastapi import UploadFile

MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
}


class FileValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def sanitize_filename(filename: str | None) -> str:
    original = Path(filename or "document").name
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(original).stem).strip(" ._")
    suffix = Path(original).suffix.lower()
    return f"{stem or 'document'}{suffix}"


async def validate_upload(upload: UploadFile) -> tuple[str, str, bytes]:
    filename = sanitize_filename(upload.filename)
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise FileValidationError("Only PDF and DOCX files are supported.")

    content_type = (upload.content_type or "application/octet-stream").lower()
    if content_type not in ALLOWED_MIME_TYPES[extension]:
        raise FileValidationError("The file type does not match its extension.")

    data = await upload.read(MAX_FILE_SIZE + 1)
    if not data:
        raise FileValidationError("The uploaded file is empty.")
    if len(data) > MAX_FILE_SIZE:
        raise FileValidationError("File exceeds the 20 MB limit.", 413)
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise FileValidationError("The PDF file appears to be invalid or corrupted.")
    if extension == ".docx" and not data.startswith(b"PK"):
        raise FileValidationError("The DOCX file appears to be invalid or corrupted.")
    return filename, extension, data

