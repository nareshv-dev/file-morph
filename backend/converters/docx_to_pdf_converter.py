from __future__ import annotations

import html
import io
from pathlib import Path
from typing import Iterator

import fitz
from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph


def _iter_blocks(parent: DocumentObject | _Cell) -> Iterator[Paragraph | Table]:
    element = parent.element.body if isinstance(parent, DocumentObject) else parent._tc
    for child in element.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _run_html(run_element, relationships, archive: fitz.Archive, image_counter: list[int]) -> str:
    text_parts: list[str] = []
    for node in run_element.iter():
        if node.tag == qn("w:t"):
            text_parts.append(html.escape(node.text or ""))
        elif node.tag == qn("w:tab"):
            text_parts.append("&emsp;")
        elif node.tag == qn("w:br"):
            text_parts.append("<br>")
    value = "".join(text_parts)
    properties = run_element.find(qn("w:rPr"))
    if value and properties is not None:
        styles: list[str] = []
        size = properties.find(qn("w:sz"))
        color = properties.find(qn("w:color"))
        fonts = properties.find(qn("w:rFonts"))
        if size is not None and size.get(qn("w:val")):
            styles.append(f"font-size:{int(size.get(qn('w:val'))) / 2:g}pt")
        if color is not None and color.get(qn("w:val"), "").lower() not in {"", "auto"}:
            styles.append(f"color:#{html.escape(color.get(qn('w:val')), quote=True)}")
        if fonts is not None:
            font_name = fonts.get(qn("w:ascii")) or fonts.get(qn("w:hAnsi"))
            if font_name:
                styles.append(f"font-family:'{html.escape(font_name, quote=True)}'")
        if styles:
            value = f'<span style="{";".join(styles)}">{value}</span>'
        if properties.find(qn("w:b")) is not None:
            value = f"<strong>{value}</strong>"
        if properties.find(qn("w:i")) is not None:
            value = f"<em>{value}</em>"
        if properties.find(qn("w:u")) is not None:
            value = f"<u>{value}</u>"

    images: list[str] = []
    for blip in run_element.iter(qn("a:blip")):
        relation_id = blip.get(qn("r:embed"))
        if not relation_id or relation_id not in relationships:
            continue
        part = relationships[relation_id].target_part
        image_counter[0] += 1
        suffix = Path(str(part.partname)).suffix.lower() or ".png"
        image_name = f"word-image-{image_counter[0]}{suffix}"
        archive.add(part.blob, image_name)
        width = ""
        extent = next(iter(run_element.iter(qn("wp:extent"))), None)
        if extent is not None and extent.get("cx"):
            width_points = min(500, int(extent.get("cx")) / 12700)
            width = f' style="width:{width_points:.2f}pt"'
        images.append(f'<img src="{image_name}" alt="Document image"{width}>')
    return value + "".join(images)


def _list_kind(paragraph: Paragraph, document) -> str | None:
    style = (paragraph.style.name if paragraph.style else "").lower()
    if "list bullet" in style:
        return "bullet"
    if "list number" in style:
        return "number"
    properties = paragraph._p.pPr
    if properties is None or properties.numPr is None:
        return None
    try:
        num_id = properties.numPr.numId.val
        numbering = document.part.numbering_part.element
        num = next(item for item in numbering.findall(qn("w:num")) if int(item.get(qn("w:numId"))) == num_id)
        abstract_id = num.find(qn("w:abstractNumId")).get(qn("w:val"))
        abstract = next(item for item in numbering.findall(qn("w:abstractNum")) if item.get(qn("w:abstractNumId")) == abstract_id)
        level = abstract.find(qn("w:lvl"))
        number_format = level.find(qn("w:numFmt")).get(qn("w:val")) if level is not None else "bullet"
        return "bullet" if number_format == "bullet" else "number"
    except (AttributeError, StopIteration):
        return "bullet"


def _paragraph_html(
    paragraph: Paragraph,
    document,
    archive: fitz.Archive,
    image_counter: list[int],
    list_counter: list[int],
) -> str:
    chunks: list[str] = []
    for child in paragraph._p.iterchildren():
        if child.tag == qn("w:r"):
            chunks.append(_run_html(child, document.part.rels, archive, image_counter))
        elif child.tag == qn("w:hyperlink"):
            relation_id = child.get(qn("r:id"))
            label = "".join(_run_html(run, document.part.rels, archive, image_counter) for run in child.findall(qn("w:r")))
            url = document.part.rels[relation_id].target_ref if relation_id in document.part.rels else ""
            chunks.append(f'<a href="{html.escape(url, quote=True)}">{label}</a>' if label and url else label)

    content = "".join(chunks) or "&nbsp;"
    style = (paragraph.style.name if paragraph.style else "").lower()
    alignment = {1: "center", 2: "right", 3: "justify"}.get(paragraph.alignment)
    alignment_attr = f' style="text-align:{alignment}"' if alignment else ""
    if style.startswith("heading ") and style[-1:].isdigit():
        list_counter[0] = 0
        level = min(6, int(style[-1]))
        return f"<h{level}{alignment_attr}>{content}</h{level}>"
    list_kind = _list_kind(paragraph, document)
    if list_kind == "bullet":
        return f'<div class="list-item">&#8226;&nbsp; {content}</div>'
    if list_kind == "number":
        list_counter[0] += 1
        return f'<div class="list-item">{list_counter[0]}.&nbsp; {content}</div>'
    list_counter[0] = 0
    return f"<p{alignment_attr}>{content}</p>"


def _table_html(table: Table, document, archive: fitz.Archive, image_counter: list[int], list_counter: list[int]) -> str:
    rows: list[str] = []
    for row_index, row in enumerate(table.rows):
        cells: list[str] = []
        cell_tag = "th" if row_index == 0 else "td"
        for cell in row.cells:
            content = "".join(_paragraph_html(p, document, archive, image_counter, list_counter) for p in cell.paragraphs)
            cells.append(f"<{cell_tag}>{content}</{cell_tag}>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def convert_docx_to_pdf(source: Path | bytes) -> bytes:
    """Render DOCX structure and images to a portable PDF using PyMuPDF."""
    try:
        document = Document(io.BytesIO(source) if isinstance(source, bytes) else source)
    except Exception as exc:
        raise ValueError("The DOCX document could not be processed.") from exc

    archive = fitz.Archive()
    image_counter = [0]
    list_counter = [0]
    body: list[str] = []
    for block in _iter_blocks(document):
        if isinstance(block, Paragraph):
            body.append(_paragraph_html(block, document, archive, image_counter, list_counter))
        else:
            body.append(_table_html(block, document, archive, image_counter, list_counter))

    if not body:
        raise ValueError("No readable content was found in this document.")

    section = document.sections[0]
    page_width = max(300, section.page_width.pt)
    page_height = max(300, section.page_height.pt)
    media_box = fitz.Rect(0, 0, page_width, page_height)
    content_box = fitz.Rect(
        section.left_margin.pt,
        section.top_margin.pt,
        page_width - section.right_margin.pt,
        page_height - section.bottom_margin.pt,
    )
    css = """
        body { font-family: sans-serif; font-size: 11pt; line-height: 1.35; color: #111; }
        p { margin: 0 0 7pt 0; }
        h1 { font-size: 22pt; margin: 13pt 0 8pt; }
        h2 { font-size: 18pt; margin: 12pt 0 7pt; }
        h3 { font-size: 15pt; margin: 11pt 0 6pt; }
        h4, h5, h6 { font-size: 12pt; margin: 9pt 0 5pt; }
        .list-item { margin: 0 0 5pt 16pt; }
        table { width: 100%; border-collapse: collapse; margin: 6pt 0 10pt; }
        th, td { border: 0.7pt solid #777; padding: 4pt; vertical-align: top; }
        th { font-weight: bold; background-color: #eeeeee; }
        td p, th p { margin: 0; }
        img { display: block; max-width: 100%; height: auto; margin: 6pt 0; }
    """

    output = io.BytesIO()
    writer = fitz.DocumentWriter(output)
    try:
        story = fitz.Story("<html><body>" + "".join(body) + "</body></html>", user_css=css, archive=archive)
        story.write(writer, lambda _page_number, _filled: (media_box, content_box, None))
    except Exception as exc:
        raise ValueError("The DOCX document could not be rendered as PDF.") from exc
    finally:
        writer.close()
    return output.getvalue()
