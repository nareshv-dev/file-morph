from __future__ import annotations

import base64
import io
import logging
import os
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

try:
    from backend.converters.docx_converter import convert_docx
    from backend.converters.docx_to_pdf_converter import convert_docx_to_pdf
    from backend.converters.pdf_converter import convert_pdf
    from backend.converters.pdf_to_docx_converter import convert_pdf_to_docx
    from backend.utils.file_validator import FileValidationError, validate_upload
except ModuleNotFoundError:
    from converters.docx_converter import convert_docx
    from converters.docx_to_pdf_converter import convert_docx_to_pdf
    from converters.pdf_converter import convert_pdf
    from converters.pdf_to_docx_converter import convert_pdf_to_docx
    from utils.file_validator import FileValidationError, validate_upload

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("filemorph")

app = FastAPI(title="FileMorph API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Output-Filename"],
)


@app.exception_handler(FileValidationError)
async def validation_error_handler(_: Request, exc: FileValidationError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc)})


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_: Request, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "Please choose a file to convert."})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "FileMorph"}


def _make_bundle(markdown_name: str, markdown: str, assets) -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(markdown_name, markdown.encode("utf-8"))
        for asset in assets:
            archive.writestr(asset.filename, asset.data)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@app.post("/api/convert")
async def convert(file: UploadFile = File(...)) -> JSONResponse:
    try:
        filename, extension, data = await validate_upload(file)
        result = convert_pdf(data) if extension == ".pdf" else convert_docx(data)
        markdown_name = f"{Path(filename).stem}.md"
        assets = [
            {
                "filename": asset.filename,
                "content_type": asset.content_type,
                "data": base64.b64encode(asset.data).decode("ascii"),
                "alt_text": asset.alt_text,
            }
            for asset in result.assets
        ]
        return JSONResponse({
            "original_filename": filename,
            "markdown_filename": markdown_name,
            "markdown": result.markdown,
            "assets": assets,
            "bundle_filename": f"{Path(filename).stem}-markdown.zip",
            "bundle": _make_bundle(markdown_name, result.markdown, result.assets),
            "page_count": result.page_count,
        })
    except FileValidationError:
        raise
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})
    except Exception:
        safe_name = getattr(file, "filename", "unknown document")
        logger.exception("Unexpected conversion failure for %s", safe_name)
        return JSONResponse(status_code=500, content={"error": "Something went wrong while converting the document. Please try again."})


@app.post("/api/convert/{conversion_type}")
async def convert_format(conversion_type: str, file: UploadFile = File(...)) -> Response:
    conversions = {
        "pdf-to-docx": ({".pdf"}, convert_pdf_to_docx, ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "docx-to-pdf": ({".docx"}, convert_docx_to_pdf, ".pdf", "application/pdf"),
    }
    if conversion_type == "to-markdown":
        return await convert(file)
    if conversion_type not in conversions:
        return JSONResponse(status_code=404, content={"error": "Unknown conversion type."})

    allowed, converter, output_extension, content_type = conversions[conversion_type]
    try:
        filename, _, data = await validate_upload(file, allowed)
        output = converter(data)
        output_name = f"{Path(filename).stem}{output_extension}"
        return Response(
            content=output,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{output_name}"',
                "X-Output-Filename": output_name,
            },
        )
    except FileValidationError:
        raise
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})
    except Exception:
        safe_name = getattr(file, "filename", "unknown document")
        logger.exception("Unexpected %s conversion failure for %s", conversion_type, safe_name)
        return JSONResponse(status_code=500, content={"error": "Something went wrong while converting the document. Please try again."})


frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
