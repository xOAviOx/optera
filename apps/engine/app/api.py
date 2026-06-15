"""Engine HTTP/WS surface (§6). M1 ships the contract as stubs.

Endpoints that need real broker/quant/AI work return HTTP 501 with the module that
implements them, so the API shape is visible and testable from day one.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.brokers.base import NormalizedPosition
from app.brokers.upstox import UpstoxAdapter
from app.db import supabase
from app.models import (
    AnalyticsTokenRequest,
    BrokerConnectRequest,
    BrokerConnectResponse,
    BrokerStatusResponse,
    ChatRequest,
    ChatResponse,
    LoginUrlResponse,
    MarginResponse,
    PayoffRequest,
    PayoffResponse,
    PopRequest,
    PopResponse,
    ScenarioRequest,
    ScenarioResponse,
    SimAccountResponse,
    SimChainResponse,
    SimCloseRequest,
    SimOrderRequest,
)
from app.realtime import upstox_feed
from app.security.auth import get_current_user, verify_jwt
from app.security.crypto import EncryptionNotConfigured, encrypt_token
from app.services import positions_service, quant_service, sim_service, stream_service
from app.services.positions_service import BrokerNotConnected
from app.services.sim_service import PaperTablesMissing, SimError
from app.services.stream_service import AnalyticsTokenMissing

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


def _broker_error(exc: Exception) -> HTTPException:
    """Map broker/data-layer failures to HTTP responses for the live-data endpoints."""
    if isinstance(exc, BrokerNotConnected):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (EncryptionNotConfigured, supabase.SupabaseNotConfigured)):
        return _config_error(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return HTTPException(status_code=502, detail=f"Upstox API error: {code}")
    return HTTPException(status_code=502, detail=f"Broker request failed: {exc}")


def _sim_error(exc: Exception) -> HTTPException:
    """Map paper-simulator failures to HTTP responses."""
    if isinstance(exc, PaperTablesMissing):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, SimError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, (EncryptionNotConfigured, supabase.SupabaseNotConfigured)):
        return _config_error(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        return HTTPException(status_code=502, detail=f"Storage error: {exc.response.status_code}")
    return HTTPException(status_code=502, detail=f"Simulator request failed: {exc}")


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
@router.get("/positions", response_model=list[NormalizedPosition], tags=["positions"])
async def positions(user_id: str = Depends(get_current_user)) -> list[NormalizedPosition]:
    try:
        return await positions_service.list_positions(user_id)
    except Exception as exc:  # noqa: BLE001 — mapped to HTTP below
        raise _broker_error(exc) from exc


@router.get("/portfolio/greeks")
async def portfolio_greeks(user_id: str = Depends(get_current_user)) -> dict:
    # Needs a live spot + IV source (same machinery as the /stream risk engine).
    raise _todo("M4 Phase 3 (live risk engine)")


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


@router.get("/margin", response_model=MarginResponse, tags=["positions"])
async def margin(user_id: str = Depends(get_current_user)) -> MarginResponse:
    try:
        return await positions_service.get_margin(user_id)
    except Exception as exc:  # noqa: BLE001 — mapped to HTTP below
        raise _broker_error(exc) from exc


# ── Paper-trading simulator (hypothetical/paper only — no real orders, no advice)
@router.get("/sim/account", response_model=SimAccountResponse, tags=["sim"])
async def sim_account(
    tick: int = 0, user_id: str = Depends(get_current_user)
) -> SimAccountResponse:
    try:
        return SimAccountResponse(**await sim_service.account_state(user_id, max(tick, 0)))
    except Exception as exc:  # noqa: BLE001 — mapped to HTTP below
        raise _sim_error(exc) from exc


@router.post("/sim/order", response_model=SimAccountResponse, tags=["sim"])
async def sim_order(
    req: SimOrderRequest, user_id: str = Depends(get_current_user)
) -> SimAccountResponse:
    try:
        snap = await sim_service.place_order(
            user_id,
            symbol=req.symbol,
            option_type=req.option_type.value,
            strike=req.strike,
            lots=req.lots,
            side=req.side.value,
            dte_days=req.dte_days,
            tick=req.tick,
        )
        return SimAccountResponse(**snap)
    except Exception as exc:  # noqa: BLE001 — mapped to HTTP below
        raise _sim_error(exc) from exc


@router.post("/sim/close", response_model=SimAccountResponse, tags=["sim"])
async def sim_close(
    req: SimCloseRequest, user_id: str = Depends(get_current_user)
) -> SimAccountResponse:
    try:
        snap = await sim_service.close_position(user_id, req.position_id, req.tick)
        return SimAccountResponse(**snap)
    except Exception as exc:  # noqa: BLE001 — mapped to HTTP below
        raise _sim_error(exc) from exc


@router.post("/sim/reset", response_model=SimAccountResponse, tags=["sim"])
async def sim_reset(user_id: str = Depends(get_current_user)) -> SimAccountResponse:
    try:
        return SimAccountResponse(**await sim_service.reset_account(user_id))
    except Exception as exc:  # noqa: BLE001 — mapped to HTTP below
        raise _sim_error(exc) from exc


@router.get("/sim/chain/{symbol}", response_model=SimChainResponse, tags=["sim"])
async def sim_chain(symbol: str, tick: int = 0, dte_days: float = 7.0) -> SimChainResponse:
    # Pure simulated market data (no user data), so this needs no auth.
    try:
        return SimChainResponse(**sim_service.chain(symbol, max(tick, 0), max(dte_days, 0.0)))
    except Exception as exc:  # noqa: BLE001 — mapped to HTTP below
        raise _sim_error(exc) from exc


# ── Alerts (M8) ───────────────────────────────────────────────────────────────
@router.get("/alert-rules")
async def list_alert_rules() -> dict:
    raise _todo("M8")


@router.get("/alerts")
async def alerts() -> dict:
    raise _todo("M8")


# ── AI co-pilot (M7) ──────────────────────────────────────────────────────────
@router.post("/ai/chat", response_model=ChatResponse, tags=["ai"])
async def ai_chat(req: ChatRequest, user_id: str = Depends(get_current_user)) -> ChatResponse:
    from app.ai import copilot
    from app.ai.providers.base import LLMError, LLMNotConfigured
    from app.ai.tools import StrategyContext

    ctx = (
        StrategyContext(
            legs=req.context.legs,
            spot=req.context.spot,
            iv_pct=req.context.iv_pct,
            dte=req.context.dte,
        )
        if req.context
        else None
    )
    try:
        reply = await copilot.run_chat([m.model_dump() for m in req.messages], ctx)
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"AI provider error: {exc}") from exc
    return ChatResponse(reply=reply.reply, flagged=reply.flagged)


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
async def _watch_disconnect(ws: WebSocket) -> None:
    """Block until the client disconnects, so we can tear down the upstream feed.

    (Inbound messages are drained here; mid-stream re-subscription is a later
    enhancement.)
    """
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        return


@router.websocket("/stream")
async def stream(ws: WebSocket) -> None:
    """Per-session live market-data push.

    Auth: pass the Supabase access token as `?token=` (browsers can't set WS
    headers). The first client message selects instruments:
        {"instrument_keys": ["NSE_INDEX|Nifty 50", ...], "mode": "option_greeks"}
    The feed is driven by the user's analytics token (no daily re-auth).
    """
    await ws.accept()

    token = ws.query_params.get("token")
    if not token:
        await ws.send_json({"type": "error", "detail": "Missing ?token= (Supabase access token)"})
        await ws.close(code=1008)
        return
    try:
        user_id = verify_jwt(token)
    except ValueError as exc:
        await ws.send_json({"type": "error", "detail": f"Invalid token: {exc}"})
        await ws.close(code=1008)
        return

    try:
        analytics = await stream_service.resolve_feed_token(user_id)
    except AnalyticsTokenMissing as exc:
        await ws.send_json({"type": "error", "detail": str(exc)})
        await ws.close(code=1008)
        return
    except (EncryptionNotConfigured, supabase.SupabaseNotConfigured) as exc:
        await ws.send_json({"type": "error", "detail": f"Server not configured: {exc}"})
        await ws.close(code=1011)
        return

    try:
        req = await ws.receive_json()
    except WebSocketDisconnect:
        return
    instrument_keys = req.get("instrument_keys") if isinstance(req, dict) else None
    mode = (req.get("mode") if isinstance(req, dict) else None) or upstox_feed.DEFAULT_MODE
    if not isinstance(instrument_keys, list) or not instrument_keys:
        await ws.send_json(
            {"type": "error", "detail": "Send {'instrument_keys': [...]} to subscribe"}
        )
        await ws.close(code=1008)
        return
    if mode not in upstox_feed.VALID_MODES:
        await ws.send_json({"type": "error", "detail": f"Invalid mode {mode!r}"})
        await ws.close(code=1008)
        return

    await ws.send_json({"type": "subscribed", "instrument_keys": instrument_keys, "mode": mode})

    # Pump live ticks until either the feed ends or the client disconnects.
    tasks = {
        asyncio.create_task(
            stream_service.forward_ticks(
                ws.send_json,
                analytics,
                instrument_keys,
                mode,
                tick_source=stream_service.active_tick_source(),
            )
        ),
        asyncio.create_task(_watch_disconnect(ws)),
    }
    _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    for task in tasks - pending:
        # A dead client raising inside forward_ticks is expected, not an error.
        with contextlib.suppress(Exception):
            task.result()
    with contextlib.suppress(RuntimeError):
        await ws.close()
