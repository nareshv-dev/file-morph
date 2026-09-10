from __future__ import annotations

import base64
import io
import zipfile

import fitz
import pytest
from docx import Document
from fastapi.testclient import TestClient

from backend.converters.markdown_converter import markdown_table, normalize_markdown
from backend.main import app
from backend.utils.file_validator import MAX_FILE_SIZE

client = TestClient(app)


def make_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Sample title", fontsize=22)
    page.insert_text((72, 110), "A faithful paragraph from the PDF.", fontsize=11)
    data = document.tobytes()
    document.close()
    return data


def make_docx(with_image: bool = False) -> bytes:
    document = Document()
    document.add_heading("Sample title", level=1)
    paragraph = document.add_paragraph()
    paragraph.add_run("Bold words").bold = True
    paragraph.add_run(" and regular words.")
    document.add_paragraph("First item", style="List Bullet")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Name"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "alpha"
    table.cell(1, 1).text = "one"
    if with_image:
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        document.add_picture(io.BytesIO(png))
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "MarkDrop"}


def test_valid_pdf_conversion() -> None:
    response = client.post("/api/convert", files={"file": ("sample.pdf", make_pdf(), "application/pdf")})
    assert response.status_code == 200
    assert "Sample title" in response.json()["markdown"]
    assert "faithful paragraph" in response.json()["markdown"]


def test_valid_docx_conversion_with_image() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("sample.docx", make_docx(True), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    result = response.json()
    assert "# Sample title" in result["markdown"]
    assert "**Bold words**" in result["markdown"]
    assert "| Name | Value |" in result["markdown"]
    assert result["assets"]
    assert "![" in result["markdown"]
    assert result["bundle"]
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(result["bundle"]))) as bundle:
        assert "sample.md" in bundle.namelist()
        assert any(name.startswith("images/") for name in bundle.namelist())


@pytest.mark.parametrize(
    ("name", "data", "content_type", "expected"),
    [
        ("notes.txt", b"hello", "text/plain", "Only PDF and DOCX"),
        ("empty.pdf", b"", "application/pdf", "empty"),
        ("broken.pdf", b"not a pdf", "application/pdf", "invalid or corrupted"),
    ],
)
def test_invalid_uploads(name: str, data: bytes, content_type: str, expected: str) -> None:
    response = client.post("/api/convert", files={"file": (name, data, content_type)})
    assert response.status_code == 400
    assert expected.lower() in response.json()["error"].lower()


def test_oversized_file() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("huge.pdf", b"%PDF-" + b"0" * MAX_FILE_SIZE, "application/pdf")},
    )
    assert response.status_code == 413


def test_markdown_normalization() -> None:
    assert normalize_markdown(["# Title", "", "Paragraph\n\n\n\nNext"]) == "# Title\n\nParagraph\n\nNext\n"
    assert markdown_table([["A", "B"], ["x", "y"]]) == "| A | B |\n| --- | --- |\n| x | y |"
