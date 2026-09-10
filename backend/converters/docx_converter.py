from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Iterator

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

try:
    from backend.converters.markdown_converter import markdown_table, normalize_markdown
    from backend.models import Asset, ConversionResult
except ModuleNotFoundError:
    from converters.markdown_converter import markdown_table, normalize_markdown
    from models import Asset, ConversionResult


def _iter_blocks(parent: DocumentObject | _Cell) -> Iterator[Paragraph | Table]:
    element = parent.element.body if isinstance(parent, DocumentObject) else parent._tc
    for child in element.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _content_type(extension: str) -> str:
    ext = extension.lower().lstrip(".")
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}.get(ext, f"image/{ext or 'png'}")


def _run_markdown(run_element, relationships, assets: list[Asset], image_counter: list[int]) -> str:
    texts = [node.text or "" for node in run_element.iter(qn("w:t"))]
    text = "".join(texts)
    if text:
        properties = run_element.find(qn("w:rPr"))
        bold = properties is not None and properties.find(qn("w:b")) is not None
        italic = properties is not None and properties.find(qn("w:i")) is not None
        if bold and italic:
            text = f"***{text}***"
        elif bold:
            text = f"**{text}**"
        elif italic:
            text = f"*{text}*"

    image_refs: list[str] = []
    for blip in run_element.iter(qn("a:blip")):
        relation_id = blip.get(qn("r:embed"))
        if not relation_id or relation_id not in relationships:
            continue
        part = relationships[relation_id].target_part
        image_counter[0] += 1
        suffix = Path(str(part.partname)).suffix or ".png"
        filename = f"images/image-{image_counter[0]}{suffix.lower()}"
        description = "Document image"
        for drawing_prop in run_element.iter(qn("wp:docPr")):
            description = drawing_prop.get("descr") or drawing_prop.get("name") or description
        assets.append(Asset(filename, _content_type(suffix), part.blob, description))
        image_refs.append(f"![{description}]({filename})")
    return text + ("\n" if text and image_refs else "") + "\n".join(image_refs)


def _paragraph_markdown(paragraph: Paragraph, document, assets: list[Asset], image_counter: list[int]) -> str:
    chunks: list[str] = []
    for child in paragraph._p.iterchildren():
        if child.tag == qn("w:r"):
            chunks.append(_run_markdown(child, document.part.rels, assets, image_counter))
        elif child.tag == qn("w:hyperlink"):
            relation_id = child.get(qn("r:id"))
            label = "".join(_run_markdown(run, document.part.rels, assets, image_counter) for run in child.findall(qn("w:r")))
            url = document.part.rels[relation_id].target_ref if relation_id in document.part.rels else ""
            chunks.append(f"[{label}]({url})" if label and url else label)
    text = "".join(chunks).strip()
    if not text:
        return ""

    style = (paragraph.style.name if paragraph.style else "").lower()
    heading_match = re.match(r"heading\s+(\d+)", style)
    if heading_match:
        return f"{'#' * min(6, int(heading_match.group(1)))} {text}"

    properties = paragraph._p.pPr
    if properties is not None and properties.numPr is not None:
        num_id = properties.numPr.numId.val if properties.numPr.numId is not None else 0
        try:
            numbering = document.part.numbering_part.element
            num = next(n for n in numbering.findall(qn("w:num")) if int(n.get(qn("w:numId"))) == num_id)
            abstract_id = num.find(qn("w:abstractNumId")).get(qn("w:val"))
            abstract = next(a for a in numbering.findall(qn("w:abstractNum")) if a.get(qn("w:abstractNumId")) == abstract_id)
            level = abstract.find(qn("w:lvl"))
            fmt = level.find(qn("w:numFmt")).get(qn("w:val")) if level is not None else "bullet"
            return ("1. " if fmt != "bullet" else "- ") + text
        except (AttributeError, StopIteration):
            return "- " + text
    if "list bullet" in style:
        return "- " + text
    if "list number" in style:
        return "1. " + text
    return text


def convert_docx(source: Path | bytes) -> ConversionResult:
    try:
        document = Document(BytesIO(source) if isinstance(source, bytes) else source)
    except Exception as exc:
        raise ValueError("The document could not be processed.") from exc

    parts: list[str] = []
    assets: list[Asset] = []
    image_counter = [0]
    for block in _iter_blocks(document):
        if isinstance(block, Paragraph):
            value = _paragraph_markdown(block, document, assets, image_counter)
        else:
            rows: list[list[str]] = []
            for row in block.rows:
                rows.append([
                    " ".join(filter(None, (_paragraph_markdown(p, document, assets, image_counter) for p in cell.paragraphs)))
                    for cell in row.cells
                ])
            value = markdown_table(rows)
        if value:
            parts.append(value)
    if not parts:
        raise ValueError("No readable content was found in this document.")
    return ConversionResult(normalize_markdown(parts), assets)
