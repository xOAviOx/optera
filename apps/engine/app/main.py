"""Optera engine entrypoint."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import router
from app.config import get_settings
from app.models import HealthResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Run the M8 alert monitor for the app's lifetime (no-op if disabled)."""
    monitor: asyncio.Task | None = None
    if settings.alert_monitor_enabled:
        from app.services import alert_service

        monitor = asyncio.create_task(alert_service.monitor_loop())
    yield
    if monitor:
        monitor.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor


app = FastAPI(
    title="Optera Engine",
    version=__version__,
    description="Quant + realtime + AI orchestration. Education/analytics only — no advice.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, environment=settings.environment)


app.include_router(router)
