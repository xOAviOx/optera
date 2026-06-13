"""Engine HTTP/WS surface (§6). M1 ships the contract as stubs.

Endpoints that need real broker/quant/AI work return HTTP 501 with the module that
implements them, so the API shape is visible and testable from day one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.brokers.upstox import UpstoxAdapter
from app.db import supabase
from app.models import (
    AnalyticsTokenRequest,
    BrokerConnectRequest,
    BrokerConnectResponse,
    BrokerStatusResponse,
    LoginUrlResponse,
    PayoffRequest,
    PayoffResponse,
    PopRequest,
    PopResponse,
    ScenarioRequest,
    ScenarioResponse,
)
from app.security.auth import get_current_user
from app.security.crypto import EncryptionNotConfigured, encrypt_token
from app.services import quant_service

router = APIRouter()

_IST = timezone(timedelta(hours=5, minutes=30))
_upstox = UpstoxAdapter()


def _todo(module: str) -> HTTPException:
    return HTTPException(status_code=501, detail=f"Not implemented yet — lands in {module}")


def _next_token_expiry() -> str:
    """Upstox daily access tokens expire ~03:30 IST. Return the next such instant."""
    now = datetime.now(_IST)
    expiry = now.replace(hour=3, minute=30, second=0, microsecond=0)
    if now >= expiry:
        expiry += timedelta(days=1)
    return expiry.isoformat()


def _config_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"Broker/storage not configured: {exc}")


# ── Broker / auth (M2) ────────────────────────────────────────────────────────
@router.get("/broker/upstox/login-url", response_model=LoginUrlResponse, tags=["broker"])
async def upstox_login_url(user_id: str = Depends(get_current_user)) -> LoginUrlResponse:
    # `state` carries the user id so the callback can be correlated; the connect
    # call re-verifies the logged-in user regardless.
    return LoginUrlResponse(url=_upstox.authorize_url(state=user_id))


@router.post("/auth/broker/connect", response_model=BrokerConnectResponse, tags=["broker"])
async def broker_connect(
    req: BrokerConnectRequest, user_id: str = Depends(get_current_user)
) -> BrokerConnectResponse:
    from app.config import get_settings

    try:
        token_json = await _upstox.exchange_code(req.code)
    except Exception as exc:  # network / invalid code
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {exc}") from exc

    access_token = token_json.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="No access_token in broker response")

    try:
        expires_at = _next_token_expiry()
        row = await supabase.upsert_broker_connection(
            user_id=user_id,
            broker="upstox",
            api_key=get_settings().upstox_api_key,
            access_token_enc=encrypt_token(access_token),
            status="active",
            expires_at=expires_at,
        )
    except (EncryptionNotConfigured, supabase.SupabaseNotConfigured) as exc:
        raise _config_error(exc) from exc

    return BrokerConnectResponse(
        connected=True, broker="upstox", status=row.get("status", "active"), expires_at=expires_at
    )


@router.post("/broker/analytics-token", response_model=BrokerConnectResponse, tags=["broker"])
async def broker_analytics_token(
    req: AnalyticsTokenRequest, user_id: str = Depends(get_current_user)
) -> BrokerConnectResponse:
    """Store the one-time analytics token (market data + websocket; no daily re-auth)."""
    try:
        row = await supabase.upsert_broker_connection(
            user_id=user_id,
            broker="upstox",
            analytics_token_enc=encrypt_token(req.analytics_token),
        )
    except (EncryptionNotConfigured, supabase.SupabaseNotConfigured) as exc:
        raise _config_error(exc) from exc
    return BrokerConnectResponse(
        connected=True, broker="upstox", status=row.get("status", "active")
    )


@router.get("/broker/status", response_model=BrokerStatusResponse, tags=["broker"])
async def broker_status(user_id: str = Depends(get_current_user)) -> BrokerStatusResponse:
    try:
        conn = await supabase.get_broker_connection(user_id, "upstox")
    except supabase.SupabaseNotConfigured as exc:
        raise _config_error(exc) from exc

    if not conn:
        return BrokerStatusResponse(connected=False, reconnect_needed=True)

    expires_at = conn.get("expires_at")
    expired = False
    if expires_at:
        try:
            expired = datetime.fromisoformat(expires_at) <= datetime.now(_IST)
        except ValueError:
            expired = False

    has_access = conn.get("access_token_enc") is not None
    return BrokerStatusResponse(
        connected=has_access,
        broker="upstox",
        status=conn.get("status"),
        expires_at=expires_at,
        reconnect_needed=(not has_access) or expired,
        has_analytics_token=conn.get("analytics_token_enc") is not None,
    )


# ── Positions & portfolio (M4) ────────────────────────────────────────────────
@router.get("/positions")
async def positions() -> dict:
    raise _todo("M4")


@router.get("/portfolio/greeks")
async def portfolio_greeks() -> dict:
    raise _todo("M4")


# ── Quant endpoints (M3 — live) ───────────────────────────────────────────────
@router.post("/payoff", response_model=PayoffResponse, tags=["quant"])
async def payoff(req: PayoffRequest) -> PayoffResponse:
    return quant_service.compute_payoff(req)


@router.post("/scenario", response_model=ScenarioResponse, tags=["quant"])
async def scenario(req: ScenarioRequest) -> ScenarioResponse:
    return quant_service.compute_scenario(req)


@router.post("/pop", response_model=PopResponse, tags=["quant"])
async def pop(req: PopRequest) -> PopResponse:
    return quant_service.compute_pop(req)


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
