from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from web.backend.db import init_db
from web.backend.errors import describe_message, structured_http_detail
from web.backend.routes import api_keys, auth, device_models, devices, settings, schema, vendors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    init_db()
    yield


app = FastAPI(title="Dotmate Admin", lifespan=lifespan)


def _structured_errors(request: Request) -> bool:
    return request.headers.get("x-dotmate-structured-errors") == "1"


@app.exception_handler(StarletteHTTPException)
async def structured_http_exception(
    request: Request,
    exc: StarletteHTTPException,
):
    detail = (
        structured_http_detail(exc.detail, exc.status_code)
        if _structured_errors(request)
        else exc.detail
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def structured_validation_exception(
    request: Request,
    exc: RequestValidationError,
):
    if not _structured_errors(request):
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors())},
        )

    fields: dict[str, str] = {}
    field_errors: dict[str, dict] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"] if part != "body")
        field = location or "form"
        message = error.get("msg", "Invalid value")
        fields[field] = message
        field_errors[field] = describe_message(
            "Field required" if error.get("type") == "missing" else message,
            status_code=422,
        )
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "message": "Check the highlighted fields",
                "code": "validation",
                "params": {},
                "fields": fields,
                "field_errors": field_errors,
            }
        },
    )

# CORS — allow the Vite dev server during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth.router)
app.include_router(vendors.router)
app.include_router(device_models.router)
app.include_router(api_keys.router)
app.include_router(devices.router)
app.include_router(settings.router)
app.include_router(schema.router)

# Serve built frontend (production)
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if (_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="static-assets")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve safe frontend files or index.html for client-side routes."""
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")

    dist = _DIST.resolve()
    file = (_DIST / full_path).resolve()
    if not file.is_relative_to(dist):
        raise HTTPException(status_code=404, detail="File not found")
    if file.is_file():
        return FileResponse(file)

    index = dist / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="Frontend build not found")
    return FileResponse(index)
