from __future__ import annotations

import io
import struct
import zipfile
import zlib

import fitz
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_mime_and_image_signature_mismatch() -> None:
    response = client.post("/api/convert/image-to-pdf", files={"file": ("fake.png", b"not an image", "image/png")})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE"
    response = client.post("/api/convert/pdf-to-docx", files={"file": ("fake.pdf", b"%PDF-", "image/png")})
    assert response.status_code == 400


def test_docx_package_inspection_and_zip_bomb_rejection() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("word/document.xml", "A" * 1_000_000)
    response = client.post("/api/convert/docx-to-pdf", files={"file": ("bomb.docx", buffer.getvalue(), "application/zip")})
    assert response.status_code == 413


def test_password_protected_pdf_is_rejected() -> None:
    document = fitz.open(); document.new_page()
    data = document.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="password", owner_pw="owner")
    document.close()
    response = client.post("/api/convert/pdf-to-docx", files={"file": ("protected.pdf", data, "application/pdf")})
    assert response.status_code == 400
    assert "Password-protected" in response.json()["error"]["message"]


def test_pdf_page_limit() -> None:
    document = fitz.open()
    for _ in range(101): document.new_page()
    data = document.tobytes(); document.close()
    response = client.post("/api/convert/compress-pdf", files={"file": ("many.pdf", data, "application/pdf")})
    assert response.status_code == 413


def test_html_scripts_and_external_assets_are_removed() -> None:
    response = client.post("/api/convert/markdown-to-html", files={"file": ("safe.md", b"# Hello\n<script>secret script</script>\n![remote](https://example.com/image.png)", "text/markdown")})
    assert response.status_code == 200
    assert b"secret script" not in response.content
    assert b"<img" not in response.content


def test_large_image_dimensions_are_rejected_without_rendering() -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 10000, 5000, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"")) + chunk(b"IEND", b"")
    response = client.post("/api/convert/image-to-pdf", files={"file": ("large.png", png, "image/png")})
    assert response.status_code == 413
