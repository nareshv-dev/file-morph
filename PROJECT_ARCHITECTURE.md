# MarkDrop Project Architecture

This file explains how the MarkDrop project works and where the PDF/DOCX to Markdown conversion happens.

## What This Project Does

MarkDrop is a full-stack document converter.

It accepts a PDF or DOCX file from the browser, sends it to a Python FastAPI backend, extracts readable content and images, converts the structure into Markdown, and returns a downloadable `.md` file plus an optional ZIP bundle with images.

Important note: this project does not use an AI model. The conversion is done with Python libraries and custom converter logic.

- PDF files are read using `PyMuPDF`.
- DOCX files are read using `python-docx`.
- Markdown formatting is created by the code inside `backend/converters/`.

## High-Level Flow

```text
User selects PDF/DOCX in browser
        |
        v
React frontend sends file to /api/convert
        |
        v
FastAPI backend receives uploaded file
        |
        v
File validator checks file type, size, and signature
        |
        v
Backend chooses PDF converter or DOCX converter
        |
        v
Converter extracts text, headings, lists, tables, links, and images
        |
        v
Markdown is normalized
        |
        v
Backend returns Markdown, image assets, and ZIP bundle
        |
        v
Frontend shows preview and download buttons
```

## Main Frontend Files

### `frontend/src/App.jsx`

This is the main React component. It controls the upload, API call, loading state, error handling, result preview, and download buttons.

The conversion starts in the frontend here:

```javascript
async function convert() {
```

Inside that function, the uploaded file is sent to the backend:

```javascript
const response = await fetch('/api/convert', { method: 'POST', body, signal: controller.signal })
```

After the backend returns the converted Markdown, the frontend stores the response:

```javascript
setResult(data); setStatus('complete')
```

The Markdown download button creates a `.md` file from `result.markdown`.

```javascript
downloadBlob(new Blob([result.markdown], { type: 'text/markdown;charset=utf-8' }), result.markdown_filename)
```

## Main Backend Files

### `backend/main.py`

This is the FastAPI server. It defines the API routes.

The upload route is:

```python
@app.post("/api/convert")
async def convert(file: UploadFile = File(...)) -> JSONResponse:
```

The uploaded file is validated:

```python
filename, extension, data = await validate_upload(file)
```

This is the most important conversion decision line:

```python
result = convert_pdf(data) if extension == ".pdf" else convert_docx(data)
```

That line means:

- If the uploaded file extension is `.pdf`, call `convert_pdf(data)`.
- Otherwise, call `convert_docx(data)`.

The backend then creates the output Markdown file name:

```python
markdown_name = f"{Path(filename).stem}.md"
```

Finally, the backend returns the converted result to the frontend as JSON:

```python
return JSONResponse({
    "original_filename": filename,
    "markdown_filename": markdown_name,
    "markdown": result.markdown,
    "assets": assets,
    "bundle_filename": f"{Path(filename).stem}-markdown.zip",
    "bundle": _make_bundle(markdown_name, result.markdown, result.assets),
    "page_count": result.page_count,
})
```

## File Validation

### `backend/utils/file_validator.py`

This file protects the backend from invalid uploads.

It checks:

- Whether the extension is allowed.
- Whether the MIME type matches.
- Whether the file size is under the limit.
- Whether the file really looks like a PDF or DOCX internally.

The validator starts here:

```python
async def validate_upload(upload: UploadFile) -> tuple[str, str, bytes]:
```

The project currently allows files up to 20 MB:

```python
MAX_FILE_SIZE = 20 * 1024 * 1024
```

It reads the uploaded file into memory:

```python
data = await upload.read(MAX_FILE_SIZE + 1)
```

It checks PDF files using the PDF signature:

```python
if extension == ".pdf" and not data.startswith(b"%PDF-"):
```

It checks DOCX files using the ZIP signature, because `.docx` files are internally ZIP files:

```python
if extension == ".docx" and not data.startswith(b"PK"):
```

## PDF Conversion

### `backend/converters/pdf_converter.py`

The PDF converter starts here:

```python
def convert_pdf(source: Path | bytes) -> ConversionResult:
```

It opens the PDF using PyMuPDF:

```python
document = fitz.open(stream=source, filetype="pdf") if isinstance(source, bytes) else fitz.open(source)
```

It rejects password-protected PDFs:

```python
if document.needs_pass:
```

It extracts page text as structured data:

```python
data = page.get_text("dict", sort=True)
```

PDF content comes as blocks, lines, and spans. The converter reads these blocks and decides how to format them as Markdown.

For images, the converter creates Markdown image references:

```python
page_parts.append(f"![Image from page {page_index}]({image_name})")
```

For headings, the converter uses font size and boldness. Larger text becomes Markdown headings:

```python
text = f"# {_block_markdown(page, block, heading=True)}"
```

or:

```python
text = f"## {_block_markdown(page, block, heading=True)}"
```

or:

```python
text = f"### {_block_markdown(page, block, heading=True)}"
```

For bullet lists:

```python
text = "- " + _BULLET.sub("", text)
```

For numbered lists:

```python
text = f"{match.group(1)}. " + _NUMBERED.sub("", text)
```

The final PDF result is returned here:

```python
return ConversionResult(normalize_markdown(parts), assets, len(document))
```

## DOCX Conversion

### `backend/converters/docx_converter.py`

The DOCX converter starts here:

```python
def convert_docx(source: Path | bytes) -> ConversionResult:
```

It opens the DOCX file using `python-docx`:

```python
document = Document(BytesIO(source) if isinstance(source, bytes) else source)
```

It loops through paragraphs and tables:

```python
for block in _iter_blocks(document):
```

If the block is a paragraph, it converts it using:

```python
value = _paragraph_markdown(block, document, assets, image_counter)
```

If the block is a table, it converts rows into a Markdown table:

```python
value = markdown_table(rows)
```

Headings are converted by checking the DOCX paragraph style:

```python
heading_match = re.match(r"heading\s+(\d+)", style)
```

Then it creates Markdown heading syntax:

```python
return f"{'#' * min(6, int(heading_match.group(1)))} {text}"
```

Images inside DOCX files are extracted here:

```python
assets.append(Asset(filename, _content_type(suffix), part.blob, description))
```

The image is referenced in Markdown like this:

```python
image_refs.append(f"![{description}]({filename})")
```

The final DOCX result is returned here:

```python
return ConversionResult(normalize_markdown(parts), assets)
```

## Markdown Helpers

### `backend/converters/markdown_converter.py`

This file contains helper functions that clean and format Markdown.

Tables are created here:

```python
def markdown_table(rows: list[list[str]]) -> str:
```

Final Markdown cleanup happens here:

```python
def normalize_markdown(parts: list[str]) -> str:
```

This removes extra blank lines and joins all extracted Markdown parts into one clean Markdown file.

## Data Models

### `backend/models.py`

The backend uses small data classes to pass conversion results around.

`Asset` represents an extracted image:

```python
class Asset:
```

`ConversionResult` represents the final converted output:

```python
class ConversionResult:
```

It stores:

- `markdown`: the final Markdown text.
- `assets`: extracted images.
- `page_count`: number of pages, mainly for PDFs.

## Why Images Need A ZIP

Markdown files do not store image bytes inside the `.md` file by default.

Instead, Markdown references image paths:

```markdown
![Document image](images/image-1.png)
```

That means the image file must exist beside the Markdown file. This is why MarkDrop provides:

- A standalone `.md` download.
- A ZIP download containing the `.md` file plus the `images/` folder.

The ZIP bundle is created in `backend/main.py`:

```python
def _make_bundle(markdown_name: str, markdown: str, assets) -> str:
```

## Short Answer

The most important line in the whole project is in `backend/main.py`:

```python
result = convert_pdf(data) if extension == ".pdf" else convert_docx(data)
```

The actual conversion logic lives here:

- `backend/converters/pdf_converter.py`
- `backend/converters/docx_converter.py`
- `backend/converters/markdown_converter.py`

The frontend upload and download logic lives here:

- `frontend/src/App.jsx`

