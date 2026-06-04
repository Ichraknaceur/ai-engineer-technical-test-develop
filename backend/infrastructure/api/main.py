"""FastAPI application entry point.

Routers are mounted here. The lifespan context manager handles startup
and shutdown events (e.g. database connection pool warm-up).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.infrastructure.api.exceptions.handlers import register_exception_handlers
from backend.infrastructure.api.routers import discovery, health, jobs, sites


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Run startup and shutdown logic around the application lifecycle."""
    yield


app = FastAPI(
    title="Quarry Extraction API",
    version="1.0.0",
    description="Discover and enrich quarry records from public web sources.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(sites.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
