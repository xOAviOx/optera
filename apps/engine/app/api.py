"""Engine HTTP/WS surface (§6). M1 ships the contract as stubs.

Endpoints that need real broker/quant/AI work return HTTP 501 with the module that
implements them, so the API shape is visible and testable from day one.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.models import (
    PayoffRequest,
    PayoffResponse,
    ScenarioRequest,
    ScenarioResponse,
)

router = APIRouter()


def _todo(module: str) -> HTTPException:
    return HTTPException(status_code=501, detail=f"Not implemented yet — lands in {module}")


# ── Broker / auth (M2) ────────────────────────────────────────────────────────
@router.post("/auth/broker/connect")
async def broker_connect() -> dict:
    raise _todo("M2")


@router.get("/broker/status")
async def broker_status() -> dict:
    raise _todo("M2")


# ── Positions & portfolio (M4) ────────────────────────────────────────────────
@router.get("/positions")
async def positions() -> dict:
    raise _todo("M4")


@router.get("/portfolio/greeks")
async def portfolio_greeks() -> dict:
    raise _todo("M4")


# ── Quant endpoints (M3/M5) ───────────────────────────────────────────────────
@router.post("/payoff", response_model=PayoffResponse)
async def payoff(_: PayoffRequest) -> PayoffResponse:
    raise _todo("M3/M5")


@router.post("/scenario", response_model=ScenarioResponse)
async def scenario(_: ScenarioRequest) -> ScenarioResponse:
    raise _todo("M3/M5")


@router.post("/pop")
async def pop() -> dict:
    raise _todo("M3/M5")


# ── Chain / IV (M6) ───────────────────────────────────────────────────────────
@router.get("/chain/{symbol}")
async def chain(symbol: str) -> dict:
    raise _todo("M6")


@router.get("/iv-rank/{symbol}")
async def iv_rank(symbol: str) -> dict:
    raise _todo("M6")


@router.get("/margin")
async def margin() -> dict:
    raise _todo("M4")


# ── Alerts (M8) ───────────────────────────────────────────────────────────────
@router.get("/alert-rules")
async def list_alert_rules() -> dict:
    raise _todo("M8")


@router.get("/alerts")
async def alerts() -> dict:
    raise _todo("M8")


# ── AI co-pilot (M7) ──────────────────────────────────────────────────────────
@router.post("/ai/chat")
async def ai_chat() -> dict:
    raise _todo("M7")


# ── Strategy / journal (M9) ───────────────────────────────────────────────────
@router.post("/strategy/analyze")
async def strategy_analyze() -> dict:
    raise _todo("M9")


@router.get("/journal")
async def journal() -> dict:
    raise _todo("M9")


# ── Billing (M10) ─────────────────────────────────────────────────────────────
@router.post("/billing/webhook")
async def billing_webhook() -> dict:
    raise _todo("M10")


# ── Realtime stream (M4) ──────────────────────────────────────────────────────
@router.websocket("/stream")
async def stream(ws: WebSocket) -> None:
    """Per-session live computed-risk push. M1: echo handshake so the contract is wired."""
    await ws.accept()
    await ws.send_json({"type": "hello", "msg": "Optera stream connected (stub — M4)"})
    try:
        while True:
            data = await ws.receive_text()
            await ws.send_json({"type": "echo", "data": data})
    except WebSocketDisconnect:
        return
