from __future__ import annotations

import re
import io
import zipfile
from pathlib import Path

import fitz
from fastapi import UploadFile
from PIL import Image

from backend.config import settings

MAX_FILE_SIZE = settings.max_file_size_mb * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown", ".html", ".htm", ".txt", ".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
    ".markdown": {"text/markdown", "text/plain", "application/octet-stream"},
    ".html": {"text/html", "application/xhtml+xml", "text/plain", "application/octet-stream"},
    ".htm": {"text/html", "application/xhtml+xml", "text/plain", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".jpg": {"image/jpeg", "application/octet-stream"},
    ".jpeg": {"image/jpeg", "application/octet-stream"},
    ".png": {"image/png", "application/octet-stream"},
    ".webp": {"image/webp", "application/octet-stream"},
}


class FileValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def sanitize_filename(filename: str | None) -> str:
    original = Path(filename or "document").name
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(original).stem).strip(" ._")[:120]
    suffix = Path(original).suffix.lower()
    return f"{stem or 'document'}{suffix}"


async def validate_upload(
    upload: UploadFile,
    allowed_extensions: set[str] | None = None,
    accepted_mime_types: dict[str, set[str] | frozenset[str]] | None = None,
    maximum_file_size: int = MAX_FILE_SIZE,
) -> tuple[str, str, bytes]:
    filename = sanitize_filename(upload.filename)
    extension = Path(filename).suffix.lower()
    accepted = allowed_extensions or ALLOWED_EXTENSIONS
    if extension not in accepted:
        if accepted == {".pdf", ".docx"}:
            raise FileValidationError("Only PDF and DOCX files are supported.")
        if accepted == ALLOWED_EXTENSIONS:
            raise FileValidationError("This file format is not supported.")
        expected = " or ".join(item.removeprefix(".").upper() for item in sorted(accepted))
        raise FileValidationError(f"Only {expected} files are supported for this conversion.")

    content_type = (upload.content_type or "application/octet-stream").lower()
    mime_types = accepted_mime_types or ALLOWED_MIME_TYPES
    if content_type not in mime_types[extension]:
        raise FileValidationError("The file type does not match its extension.")

    data = await upload.read(maximum_file_size + 1)
    if not data:
        raise FileValidationError("The uploaded file is empty.")
    if len(data) > maximum_file_size:
        limit_mb = maximum_file_size // (1024 * 1024)
        raise FileValidationError(f"File exceeds the {limit_mb} MB limit.", 413)
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise FileValidationError("The PDF file appears to be invalid or corrupted.")
    if extension == ".pdf":
        try:
            with fitz.open(stream=data, filetype="pdf") as pdf:
                if pdf.needs_pass:
                    raise FileValidationError("Password-protected PDFs are not supported.")
                if pdf.page_count > settings.max_pdf_pages:
                    raise FileValidationError(f"PDF exceeds the {settings.max_pdf_pages}-page limit.", 413)
                if any(page.rect.width * page.rect.height * 9 > 40_000_000 for page in pdf):
                    raise FileValidationError("A PDF page exceeds the safe rendering dimension limit.", 413)
        except FileValidationError:
            raise
        except Exception as exc:
            raise FileValidationError("The PDF file appears to be invalid or corrupted.") from exc
    if extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise FileValidationError("The DOCX file appears to be invalid or corrupted.")
                total = sum(item.file_size for item in archive.infolist())
                compressed = max(1, sum(item.compress_size for item in archive.infolist()))
                if total > maximum_file_size * 5 or total / compressed > 100:
                    raise FileValidationError("The DOCX archive expands beyond the safe processing limit.", 413)
        except FileValidationError:
            raise
        except (zipfile.BadZipFile, OSError) as exc:
            raise FileValidationError("The DOCX file appears to be invalid or corrupted.") from exc
    image_formats = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
    if extension in image_formats:
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format != image_formats[extension]:
                    raise FileValidationError("The image type does not match its extension.")
                if image.width * image.height > 40_000_000:
                    raise FileValidationError("The image dimensions exceed the safe processing limit.", 413)
                image.verify()
        except FileValidationError:
            raise
        except Exception as exc:
            raise FileValidationError("The image appears to be invalid or corrupted.") from exc
    if extension in {".md", ".markdown", ".html", ".htm", ".txt"}:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileValidationError("Text documents must use UTF-8 encoding.") from exc
    return filename, extension, data
