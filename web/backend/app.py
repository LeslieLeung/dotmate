from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from web.backend.db import init_db
from web.backend.routes import api_keys, auth, devices, settings, schema, vendors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    init_db()
    yield


app = FastAPI(title="Dotmate Admin", lifespan=lifespan)

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
