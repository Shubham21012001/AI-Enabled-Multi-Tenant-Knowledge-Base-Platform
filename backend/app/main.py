import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import AppError, RateLimitError
from app.core.logging import setup_logging
from app.routes import auth, chat, documents, misc, organizations

setup_logging()
logger = logging.getLogger("knowbot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("KnowBot starting (env=%s, ai=%s, storage=%s)", settings.ENVIRONMENT, settings.AI_PROVIDER, settings.STORAGE_BACKEND)
    if settings.ENVIRONMENT != "test":
        from app.services.processing import resume_pending

        resume_pending()
    yield


app = FastAPI(
    title="KnowBot API",
    version="1.0.0",
    description="Multi-tenant RAG knowledge base",
    lifespan=lifespan,
    # Interactive docs are handy in development but expose the API surface publicly.
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Uploads are 10 MB; allow some multipart overhead. Everything else is small JSON.
_MAX_BODY_BYTES = settings.max_upload_bytes + 1024 * 1024


@app.middleware("http")
async def request_context(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > _MAX_BODY_BYTES:
        return JSONResponse(
            {"detail": f"Request body too large (max {settings.MAX_UPLOAD_SIZE_MB} MB)", "code": "file_too_large"},
            status_code=413,
        )
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    # Path only — query strings can contain tokens.
    logger.info("%s %s %d %.0fms rid=%s", request.method, request.url.path, response.status_code, elapsed_ms, request_id)
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    headers = {}
    if isinstance(exc, RateLimitError):
        headers["Retry-After"] = str(exc.retry_after)
    if exc.status_code == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=exc.status_code, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()
    ]
    message = errors[0]["message"] if errors else "Invalid request"
    return JSONResponse({"detail": message, "code": "validation_error", "errors": errors}, status_code=422)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal server error", "code": "internal_error"}, status_code=500)


app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(organizations.admin_router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(misc.router)
