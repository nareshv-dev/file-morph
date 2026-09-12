from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

from backend.converters.base import ConverterDefinition
from backend.converters.docx_converter import convert_docx
from backend.converters.docx_to_pdf_converter import convert_docx_to_pdf
from backend.converters.pdf_converter import convert_pdf
from backend.converters.pdf_to_docx_converter import convert_pdf_to_docx
from backend.converters.registry import ConverterRegistry
from backend.converters import additional
from backend.utils.file_validator import ALLOWED_MIME_TYPES
from backend.config import settings

MAX_FILE_SIZE = settings.max_file_size_mb * 1024 * 1024
PDF_MIMES = frozenset({"application/pdf", "application/x-pdf", "application/octet-stream"})
DOCX_MIMES = frozenset({
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",
    "application/octet-stream",
})


def _markdown_bundle(filename: str, data: bytes) -> dict[str, object]:
    result = convert_pdf(data) if Path(filename).suffix.lower() == ".pdf" else convert_docx(data)
    markdown_name = f"{Path(filename).stem}.md"
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(markdown_name, result.markdown.encode("utf-8"))
        for asset in result.assets:
            archive.writestr(asset.filename, asset.data)
    return {
        "original_filename": filename,
        "markdown_filename": markdown_name,
        "markdown": result.markdown,
        "assets": [
            {
                "filename": asset.filename,
                "content_type": asset.content_type,
                "data": base64.b64encode(asset.data).decode("ascii"),
                "alt_text": asset.alt_text,
            }
            for asset in result.assets
        ],
        "bundle_filename": f"{Path(filename).stem}-markdown.zip",
        "bundle": base64.b64encode(bundle.getvalue()).decode("ascii"),
        "page_count": result.page_count,
    }


def create_registry() -> ConverterRegistry:
    registry = ConverterRegistry()
    registry.register(ConverterDefinition(
        id="pdf-to-docx",
        title="PDF to DOCX",
        source_extensions=frozenset({".pdf"}),
        target_extension=".docx",
        accepted_mime_types={".pdf": PDF_MIMES},
        output_mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        maximum_file_size=MAX_FILE_SIZE,
        convert=lambda data, _: convert_pdf_to_docx(data),
        fidelity_description="Preserves the visible PDF page layout as high-resolution page images in Word.",
        limitations=("The Word output is visually faithful but page content is not reflowable or fully editable.",),
    ))
    registry.register(ConverterDefinition(
        id="docx-to-pdf",
        title="DOCX to PDF",
        source_extensions=frozenset({".docx"}),
        target_extension=".pdf",
        accepted_mime_types={".docx": DOCX_MIMES},
        output_mime_type="application/pdf",
        maximum_file_size=MAX_FILE_SIZE,
        convert=lambda data, _: convert_docx_to_pdf(data),
        fidelity_description="Preserves common text, headings, lists, tables, links, alignment, and images.",
        limitations=("Advanced Word layout, fields, floating objects, and uncommon fonts may render differently.",),
    ))
    registry.register(ConverterDefinition(
        id="to-markdown",
        title="PDF or DOCX to Markdown",
        source_extensions=frozenset({".pdf", ".docx"}),
        target_extension=".md",
        accepted_mime_types={".pdf": PDF_MIMES, ".docx": DOCX_MIMES},
        output_mime_type="text/markdown",
        maximum_file_size=MAX_FILE_SIZE,
        convert=lambda data, filename: _markdown_bundle(filename, data),
        fidelity_description="Extracts readable structure, tables, links, and embedded images where available.",
        limitations=("Markdown cannot preserve fixed page geometry.", "Scanned PDFs require OCR, which is not included."),
    ))
    additions = [
        ("markdown-to-pdf", "Markdown to PDF", {".md", ".markdown"}, ".pdf", "application/pdf", additional.markdown_to_pdf),
        ("markdown-to-docx", "Markdown to DOCX", {".md", ".markdown"}, ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", additional.markdown_to_docx),
        ("markdown-to-html", "Markdown to HTML", {".md", ".markdown"}, ".html", "text/html", additional.markdown_to_html_bytes),
        ("docx-to-html", "DOCX to HTML", {".docx"}, ".html", "text/html", additional.docx_to_html),
        ("docx-to-text", "DOCX to plain text", {".docx"}, ".txt", "text/plain", additional.docx_to_text),
        ("html-to-pdf", "HTML to PDF", {".html", ".htm"}, ".pdf", "application/pdf", additional.html_to_pdf),
        ("html-to-docx", "HTML to DOCX", {".html", ".htm"}, ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", additional.html_to_docx),
        ("text-to-pdf", "TXT to PDF", {".txt"}, ".pdf", "application/pdf", additional.text_to_pdf),
        ("text-to-docx", "TXT to DOCX", {".txt"}, ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", additional.text_to_docx),
        ("image-to-pdf", "JPG / PNG / WebP to PDF", {".jpg", ".jpeg", ".png", ".webp"}, ".pdf", "application/pdf", additional.image_to_pdf),
        ("pdf-to-png", "PDF pages to PNG", {".pdf"}, ".zip", "application/zip", lambda data: additional.pdf_pages_to_images(data, "png")),
        ("pdf-to-jpg", "PDF pages to JPG", {".pdf"}, ".zip", "application/zip", lambda data: additional.pdf_pages_to_images(data, "jpeg")),
        ("compress-pdf", "Compress PDF", {".pdf"}, ".pdf", "application/pdf", additional.compress_pdf),
    ]
    for converter_id, title, extensions, target, mime, function in additions:
        registry.register(ConverterDefinition(
            id=converter_id,
            title=title,
            source_extensions=frozenset(extensions),
            target_extension=target,
            accepted_mime_types={extension: frozenset(ALLOWED_MIME_TYPES[extension]) for extension in extensions},
            output_mime_type=mime,
            maximum_file_size=MAX_FILE_SIZE,
            convert=lambda data, _, function=function: function(data),
            fidelity_description="Preserves common readable content using a bounded, safe conversion pipeline.",
            limitations=(
                "Advanced layout and formatting may not be preserved; HTML scripts, external assets, and unsafe markup are removed.",
                "PDF image exports are ZIP archives; compression may not reduce an already optimized PDF.",
            ),
        ))
    for converter_id, title, extensions, batch in [
        ("images-to-pdf", "Multiple images to one PDF", {".jpg", ".jpeg", ".png", ".webp"}, additional.images_to_pdf),
        ("merge-pdf", "Merge PDF files", {".pdf"}, additional.merge_pdfs),
    ]:
        registry.register(ConverterDefinition(
            id=converter_id, title=title, source_extensions=frozenset(extensions), target_extension=".pdf",
            accepted_mime_types={extension: frozenset(ALLOWED_MIME_TYPES[extension]) for extension in extensions},
            output_mime_type="application/pdf", maximum_file_size=MAX_FILE_SIZE,
            convert=lambda data, _, batch=batch: batch([data]), supports_multiple_files=True, convert_batch=batch,
            fidelity_description="Combines files in upload order into one PDF.",
            limitations=("Each upload must satisfy the file and page limits; images become fixed PDF pages.",),
        ))
    registry.register(ConverterDefinition(
        id="split-pdf", title="Split PDF by page range", source_extensions=frozenset({".pdf"}), target_extension=".pdf",
        accepted_mime_types={".pdf": PDF_MIMES}, output_mime_type="application/pdf", maximum_file_size=MAX_FILE_SIZE,
        convert=lambda data, _: additional.split_pdf(data, {}), convert_with_options=additional.split_pdf,
        fidelity_description="Copies selected PDF pages without reflowing their layout.",
        limitations=("A valid page range is required; password-protected PDFs are not supported.",),
    ))
    return registry


converter_registry = create_registry()
