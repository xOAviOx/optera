"""Optera engine entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import router
from app.config import get_settings
from app.models import HealthResponse

settings = get_settings()

app = FastAPI(
    title="Optera Engine",
    version=__version__,
    description="Quant + realtime + AI orchestration. Education/analytics only — no advice.",
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
