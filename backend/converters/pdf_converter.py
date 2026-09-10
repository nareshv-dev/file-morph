from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import fitz

try:
    from backend.converters.markdown_converter import normalize_markdown
    from backend.models import Asset, ConversionResult
except ModuleNotFoundError:
    from converters.markdown_converter import normalize_markdown
    from models import Asset, ConversionResult

_BULLET = re.compile(r"^[\s]*[•◦▪‣–—-]\s+")
_NUMBERED = re.compile(r"^[\s]*(\d+)[.)]\s+")


def _clean_lines(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return " ".join(line for line in lines if line)


def _image_extension(ext: str) -> tuple[str, str]:
    ext = (ext or "png").lower().replace("jpeg", "jpg")
    mime_ext = "jpeg" if ext == "jpg" else ext
    return ext, f"image/{mime_ext}"


def _block_markdown(page: fitz.Page, block: dict, heading: bool = False) -> str:
    links = [link for link in page.get_links() if link.get("uri") and link.get("from")]
    lines: list[str] = []
    for line in block.get("lines", []):
        chunks: list[str] = []
        for span in line.get("spans", []):
            value = span.get("text", "")
            if not value:
                continue
            if not heading:
                flags = int(span.get("flags", 0))
                is_bold = bool(flags & 16) or "bold" in span.get("font", "").lower()
                is_italic = bool(flags & 2) or "italic" in span.get("font", "").lower()
                clean = value.strip()
                if clean and is_bold and is_italic:
                    value = value.replace(clean, f"***{clean}***")
                elif clean and is_bold:
                    value = value.replace(clean, f"**{clean}**")
                elif clean and is_italic:
                    value = value.replace(clean, f"*{clean}*")
                span_box = fitz.Rect(span.get("bbox", (0, 0, 0, 0)))
                center = (span_box.x0 + span_box.x1) / 2, (span_box.y0 + span_box.y1) / 2
                matching = next((link for link in links if fitz.Rect(link["from"]).contains(center)), None)
                if matching and clean:
                    value = value.replace(clean, f"[{clean}]({matching['uri']})")
            chunks.append(value)
        lines.append("".join(chunks))
    return _clean_lines("\n".join(lines))


def convert_pdf(source: Path | bytes) -> ConversionResult:
    try:
        document = fitz.open(stream=source, filetype="pdf") if isinstance(source, bytes) else fitz.open(source)
    except Exception as exc:
        raise ValueError("The document could not be processed.") from exc

    if document.needs_pass:
        document.close()
        raise ValueError("Password-protected PDFs are not supported.")

    parts: list[str] = []
    assets: list[Asset] = []
    seen_xrefs: dict[int, str] = {}
    try:
        sizes: list[float] = []
        page_dicts: list[dict] = []
        for page in document:
            data = page.get_text("dict", sort=True)
            page_dicts.append(data)
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            sizes.extend([round(float(span.get("size", 11)), 1)] * max(1, len(span["text"])))
        body_size = Counter(sizes).most_common(1)[0][0] if sizes else 11.0

        for page_index, (page, data) in enumerate(zip(document, page_dicts), start=1):
            page_parts: list[str] = []
            for block_index, block in enumerate(data.get("blocks", []), start=1):
                if block.get("type") == 1 and block.get("image"):
                    xref = block.get("xref", 0)
                    if xref and xref in seen_xrefs:
                        image_name = seen_xrefs[xref]
                    else:
                        ext, content_type = _image_extension(block.get("ext", "png"))
                        image_name = f"images/page-{page_index}-image-{block_index}.{ext}"
                        assets.append(Asset(image_name, content_type, block["image"], f"Image from page {page_index}"))
                        if xref:
                            seen_xrefs[xref] = image_name
                    page_parts.append(f"![Image from page {page_index}]({image_name})")
                    continue
                if block.get("type") != 0:
                    continue
                spans = [span for line in block.get("lines", []) for span in line.get("spans", [])]
                text = _block_markdown(page, block)
                if not text:
                    continue
                max_size = max((float(s.get("size", body_size)) for s in spans), default=body_size)
                bold_ratio = sum(len(s.get("text", "")) for s in spans if int(s.get("flags", 0)) & 16) / max(1, sum(len(s.get("text", "")) for s in spans))
                if max_size >= body_size * 1.65:
                    text = f"# {_block_markdown(page, block, heading=True)}"
                elif max_size >= body_size * 1.35:
                    text = f"## {_block_markdown(page, block, heading=True)}"
                elif max_size >= body_size * 1.15 or (bold_ratio > 0.7 and len(text) < 120):
                    text = f"### {_block_markdown(page, block, heading=True)}"
                elif _BULLET.match(text):
                    text = "- " + _BULLET.sub("", text)
                elif match := _NUMBERED.match(text):
                    text = f"{match.group(1)}. " + _NUMBERED.sub("", text)
                page_parts.append(text)
            if page_parts:
                parts.extend(page_parts)
        if not parts:
            raise ValueError("No readable content was found. This may be a scanned PDF; OCR is not included in this version.")
        return ConversionResult(normalize_markdown(parts), assets, len(document))
    finally:
        document.close()
