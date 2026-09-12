from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Request, UploadFile, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.auth import router as auth_router
from backend.api.conversions import router as conversions_router
from backend.api.users import router as users_router
from backend.config import settings
from backend.database import mongo_is_configured, store
from backend.services.storage_service import storage
from backend.cleanup import cleanup_expired_jobs
from backend.services.conversion_executor import execute_conversion

try:
    from backend.converters.builtins import converter_registry
    from backend.utils.file_validator import FileValidationError, validate_upload
except ModuleNotFoundError:
    from converters.builtins import converter_registry
    from utils.file_validator import FileValidationError, validate_upload

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("filemorph")

@asynccontextmanager
async def lifespan(_: FastAPI):
    async def retention_loop():
        while True:
            try:
                await asyncio.to_thread(cleanup_expired_jobs)
            except Exception:
                logger.warning("Retention cleanup failed; it will retry on the next interval.")
            await asyncio.sleep(60)
    task = asyncio.create_task(retention_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="FileMorph API", version="3.0.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(conversions_router)
app.include_router(users_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Output-Filename"],
)


@app.middleware("http")
async def request_security(request: Request, call_next):
    request.state.request_id = uuid4().hex
    content_length = request.headers.get("content-length", "0")
    if content_length.isdigit() and int(content_length) > settings.max_file_size_mb * 1024 * 1024 + 1024 * 1024:
        return error_response(request, 413, "UPLOAD_TOO_LARGE", "Upload exceeds the configured request size limit.")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if settings.secure_cookies:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid4().hex)
    return JSONResponse(status_code=status_code, content={"error": {
        "code": code, "message": message, "request_id": request_id
    }}, headers={"X-Request-ID": request_id})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, _: Exception) -> JSONResponse:
    logger.error("Unexpected API error; request_id=%s", getattr(request.state, "request_id", "unknown"))
    return error_response(request, 500, "INTERNAL_ERROR", "The request could not be completed. Please try again.")


@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codes = {400: "INVALID_REQUEST", 401: "AUTHENTICATION_REQUIRED", 403: "CSRF_REJECTED", 404: "NOT_FOUND", 409: "CONFLICT", 410: "FILE_EXPIRED", 429: "RATE_LIMITED"}
    return error_response(request, exc.status_code, codes.get(exc.status_code, "REQUEST_FAILED"), str(exc.detail))


@app.exception_handler(FileValidationError)
async def validation_error_handler(request: Request, exc: FileValidationError) -> JSONResponse:
    return error_response(request, exc.status_code, "INVALID_FILE", str(exc))


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, __: RequestValidationError) -> JSONResponse:
    return error_response(request, 400, "VALIDATION_ERROR", "Check the submitted fields and try again.")


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "FileMorph"}


@app.get("/api/ready")
def ready() -> dict[str, object]:
    try:
        if mongo_is_configured(): store.client.admin.command("ping")
        if hasattr(storage, "ready") and not storage.ready():
            raise RuntimeError("Storage is unavailable")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="A required persistence service is unavailable.") from exc
    return {"status": "ready", "database": "mongodb" if mongo_is_configured() else "memory-local-only", "storage": settings.storage_provider}


@app.get("/api/formats")
def formats() -> dict[str, list[dict[str, object]]]:
    return {"formats": [converter.public_metadata() for converter in converter_registry.all()]}


@app.post("/convert")
@app.post("/api/convert")
async def convert(file: UploadFile = File(...)) -> JSONResponse:
    return await convert_format("to-markdown", file)


@app.post("/convert/{conversion_type}")
@app.post("/api/convert/{conversion_type}")
async def convert_format(conversion_type: str, file: UploadFile = File(...)) -> Response:
    if os.getenv("VERCEL"):
        raise HTTPException(status_code=503, detail="Document processing requires a process-capable worker. Use the container runtime.")
    converter = converter_registry.get(conversion_type)
    if converter is None:
        raise HTTPException(status_code=404, detail="Unknown conversion type.")

    try:
        filename, _, data = await validate_upload(
            file,
            set(converter.source_extensions),
            converter.accepted_mime_types,
            converter.maximum_file_size,
        )
        output = await asyncio.to_thread(execute_conversion, conversion_type, [data], filename)
        if isinstance(output, dict):
            return JSONResponse(output)
        output_name = f"{Path(filename).stem}{converter.target_extension}"
        return Response(
            content=output,
            media_type=converter.output_mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{output_name}"',
                "X-Output-Filename": output_name,
            },
        )
    except FileValidationError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.error("Unexpected %s conversion failure", conversion_type)
        raise HTTPException(status_code=500, detail="Something went wrong while converting the document. Please try again.")


frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or scope["method"] not in {"GET", "HEAD"} or path.startswith("api/") or Path(path).suffix:
                raise
            return await super().get_response("index.html", scope)


if frontend_dist.exists():
    app.mount("/", SPAStaticFiles(directory=frontend_dist, html=True), name="frontend")
