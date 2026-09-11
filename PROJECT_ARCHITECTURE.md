# FileMorph Project Architecture

This document explains how FileMorph works and identifies the files and functions responsible for every conversion.

## System flow

```text
Choose a conversion type
        |
        v
Open the matching PDF or DOCX drop zone
        |
        v
POST the file to /api/convert/{conversion-type}
        |
        v
Validate extension, MIME type, size, and file signature
        |
        v
Run the selected converter entirely in memory
        |
        v
Return DOCX/PDF bytes or Markdown JSON
        |
        v
Download the output (and preview Markdown when applicable)
```

The project does not use an AI model. Conversion is performed by deterministic Python code using PyMuPDF and python-docx.

## Frontend

### `frontend/src/App.jsx`

This is the main workflow controller.

- `CONVERSIONS` defines the three choices and their accepted input types.
- `chooseMode()` changes the interface to the selected drop zone and writes a shareable URL hash.
- `convert()` posts the file to `/api/convert/${mode.id}`.
- Binary DOCX/PDF responses are downloaded as blobs.
- Markdown JSON responses are shown in the existing raw/rendered preview.

### `frontend/src/components/FileUpload.jsx`

This component provides click-to-browse and drag-and-drop upload. The `acceptedExtensions` property changes by selected mode, so PDF to DOCX accepts only PDF and DOCX to PDF accepts only DOCX.

### `frontend/src/components/MarkdownPreview.jsx`

This is used only for the Markdown mode. It displays both rendered Markdown and the raw Markdown source, and replaces extracted image paths with temporary in-browser data URLs for previewing.

## API and validation

### `backend/main.py`

The new mode-aware route is:

```python
@app.post("/api/convert/{conversion_type}")
async def convert_format(conversion_type: str, file: UploadFile = File(...)) -> Response:
```

Its `conversions` map connects each route name to the correct source extension, converter function, output extension, and MIME type:

```python
"pdf-to-docx": ({".pdf"}, convert_pdf_to_docx, ".docx", ...)
"docx-to-pdf": ({".docx"}, convert_docx_to_pdf, ".pdf", ...)
```

`to-markdown` delegates to the original Markdown conversion function. The old `/api/convert` route is kept so existing clients continue to work.

### `backend/utils/file_validator.py`

`validate_upload()` checks:

- the extension required by the selected conversion;
- the reported MIME type;
- that the file is not empty;
- the 20 MB maximum size;
- the `%PDF-` signature for PDF or the `PK` ZIP signature for DOCX.

## PDF to DOCX

### `backend/converters/pdf_to_docx_converter.py`

The main function is:

```python
def convert_pdf_to_docx(source: Path | bytes) -> bytes:
```

It opens the PDF with PyMuPDF, renders every page at high resolution, fits each page image to a matching zero-margin Word page, adds deterministic page breaks, and returns the generated DOCX as bytes. This prevents Word's paragraph reflow from moving columns, dates, rules, icons, or other fixed-layout PDF content.

Important helpers:

- `_open_pdf()` validates that PyMuPDF can open the source.
- `_configure_page()` matches the Word page dimensions to the first PDF page.
- `_add_pdf_page()` renders and inserts one full-page image without cropping or stretching.

## DOCX to PDF

### `backend/converters/docx_to_pdf_converter.py`

The main function is:

```python
def convert_docx_to_pdf(source: Path | bytes) -> bytes:
```

It reads the DOCX with python-docx, walks paragraphs and tables in document order, translates Word structure and inline formatting into safe HTML, places embedded images in a PyMuPDF in-memory archive, and uses `fitz.Story` plus `fitz.DocumentWriter` to create the PDF.

Important helpers:

- `_iter_blocks()` preserves paragraph/table order.
- `_run_html()` transfers bold, italic, underline, hyperlinks, and images.
- `_paragraph_html()` maps headings and list styles.
- `_table_html()` creates bordered PDF tables.

## PDF or DOCX to Markdown

### `backend/converters/pdf_converter.py`

`convert_pdf()` extracts ordered text blocks, detects headings from font sizes, carries bold/italic text and links into Markdown, extracts embedded images, and returns a `ConversionResult`.

### `backend/converters/docx_converter.py`

`convert_docx()` walks Word paragraphs and tables, maps Word headings/lists/emphasis/links into Markdown, extracts images, and returns a `ConversionResult`.

### `backend/converters/markdown_converter.py`

`markdown_table()` produces Markdown tables and `normalize_markdown()` removes unwanted spacing while preserving content.

## Response formats

PDF to DOCX and DOCX to PDF return the converted file bytes directly with `Content-Disposition` and `X-Output-Filename` headers. This avoids base64 overhead and lets the frontend download the response as a browser `Blob`.

Markdown conversion returns JSON because the frontend needs the Markdown text for preview, image assets for rendering, and a ready-made ZIP bundle containing the `.md` file plus its `images/` directory.

## Limitations

- PDF is fixed-layout while Word text reflows. PDF to DOCX therefore prioritizes visual fidelity by placing each source page as a high-resolution page image. The result preserves appearance but is not reflowable/editable at the text level.
- DOCX layout features such as floating shapes, SmartArt, tracked changes, complex headers/footers, and advanced pagination may be simplified in PDF output.
- Scanned PDFs work for layout-preserved DOCX output, but their text remains part of the page image because OCR is not included.
- `.doc` is a legacy binary format; FileMorph accepts modern `.docx` files.
