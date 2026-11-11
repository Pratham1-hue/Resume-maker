from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api import align, export, ingest, profiles
from .config import get_settings
from .core.logging import setup_logging
from .llm.client import LLMError


def _config_report() -> str:
    """One-line effective-config summary so misconfiguration is visible
    at startup instead of surfacing as a mysterious failure at Generate-time."""
    import os

    provider = os.getenv("LLM_PROVIDER", "anthropic")
    model = os.getenv("LLM_MODEL", "") or "(provider default)"
    has_anthropic = "set" if os.getenv("ANTHROPIC_API_KEY") else "MISSING"
    has_gemini = "set" if os.getenv("GEMINI_API_KEY") else "MISSING"
    settings = get_settings()
    return (
        f"provider={provider} model={model} "
        f"ANTHROPIC_API_KEY={has_anthropic} GEMINI_API_KEY={has_gemini} "
        f"chroma={os.getenv('CHROMA_PERSIST_DIR', './chroma_db')} "
        f"cors={settings.cors_origins}"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize job registry, ChromaDB collections, etc.
    logger = setup_logging()
    logger.info("Starting up Quick Resume Maker...")
    logger.info("Effective config: %s", _config_report())
    yield
    # Shutdown
    logger.info("Shutting down Quick Resume Maker...")


app = FastAPI(
    title="Quick Resume Maker API",
    version="0.1.0",
    description="AI-powered resume tailor: ingest → align → export",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Liveness probe (also silences health-check 404 noise)."""
    return {"status": "ok"}


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    """Any provider failure anywhere becomes a 502 with the reason."""
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    """No unhandled failure ever returns an empty/opaque response again."""
    if isinstance(exc, StarletteHTTPException):
        raise exc  # normal 4xx flow (404/400/422) — leave untouched
    logger = setup_logging()
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})

# NOTE: include each section router directly. (Nested APIRouter.include_router
# does not flatten endpoints on current FastAPI versions, so the aggregate
# app.api.router module is kept only for backwards compatibility.)
# Final paths:
#   POST /api/v1/profiles/  GET /api/v1/profiles/{id}
#   GET  /api/v1/profiles/{id}/ingest/status
#   POST /api/v1/profiles/{id}/ingest
#   POST /api/v1/align/  POST /api/v1/export/
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(align.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")


def main():
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
