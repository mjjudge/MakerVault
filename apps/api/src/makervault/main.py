"""MakerVault FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from makervault import __version__
from makervault.config import get_settings
from makervault.routers import categories, containers, documents, health, locations, parts, stock

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Self-hosted inventory and knowledge system for electronics and workshop parts.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(locations.router, prefix="/api")
app.include_router(containers.router, prefix="/api")
app.include_router(parts.router, prefix="/api")
app.include_router(stock.router, prefix="/api")
app.include_router(documents.router, prefix="/api/v1")
