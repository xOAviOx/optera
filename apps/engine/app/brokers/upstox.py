"""Upstox adapter (default broker, free tier).

M2 implements the OAuth handshake: build the authorize URL and exchange the auth
code for the daily access token. Positions/holdings/margin/chain land in M4/M6
(stubs raise NotImplementedError so callers fail loudly rather than fake data).

Two tokens (see CLAUDE.md):
  * daily access token  -> reads the user's positions/holdings (this OAuth flow)
  * one-time analytics token -> market data + websocket (captured separately, no
    daily re-auth); stored encrypted alongside the access token.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.brokers import instruments
from app.brokers.base import BrokerAdapter, NormalizedPosition
from app.config import get_settings

UPSTOX_BASE_URL = "https://api.upstox.com/v2"
AUTHORIZE_URL = f"{UPSTOX_BASE_URL}/login/authorization/dialog"
TOKEN_URL = f"{UPSTOX_BASE_URL}/login/authorization/token"

POSITIONS_PATH = "/portfolio/short-term-positions"
HOLDINGS_PATH = "/portfolio/long-term-holdings"
FUNDS_PATH = "/user/get-funds-and-margin"


def _normalize_position(rec: dict) -> NormalizedPosition:
    """Map a raw Upstox position/holding row to the broker-agnostic shape.

    Instrument metadata (lot size, option type, strike, expiry) is enriched from
    the instruments master; absent that, we degrade gracefully to broker fields.
    """
    key = rec.get("instrument_token") or rec.get("instrument_key") or ""
    meta = instruments.get(key)
    lot_size = (meta.lot_size if meta and meta.lot_size else None) or 1
    return NormalizedPosition(
        instrument_token=key,
        tradingsymbol=rec.get("trading_symbol") or rec.get("tradingsymbol") or "",
        name=meta.name if meta else rec.get("company_name"),
        option_type=meta.option_type if meta else None,
        strike=meta.strike_price if meta else None,
        expiry=meta.expiry if meta else None,
        quantity=int(rec.get("quantity") or 0),
        lot_size=lot_size,
        average_price=float(rec.get("average_price") or 0.0),
        last_price=rec.get("last_price"),
        pnl=rec.get("pnl"),
    )


def _normalize_margin(data: dict) -> dict:
    """Collapse Upstox equity+commodity segments into used/available totals."""
    equity = data.get("equity") or {}
    commodity = data.get("commodity") or {}

    def total(field: str) -> float:
        return float(equity.get(field) or 0.0) + float(commodity.get(field) or 0.0)

    return {
        "used": total("used_margin"),
        "available": total("available_margin"),
        "equity": equity or None,
        "commodity": commodity or None,
    }


class UpstoxAdapter(BrokerAdapter):
    broker_name = "upstox"

    # ── OAuth (M2) ────────────────────────────────────────────────────────────
    def authorize_url(self, state: str) -> str:
        """Upstox login dialog URL the user is redirected to."""
        s = get_settings()
        query = urlencode(
            {
                "response_type": "code",
                "client_id": s.upstox_api_key,
                "redirect_uri": s.upstox_redirect_uri,
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def exchange_code(self, code: str) -> dict:
        """Exchange an auth code for the access token. Returns Upstox's token JSON
        (access_token, user details, etc.)."""
        s = get_settings()
        form = {
            "code": code,
            "client_id": s.upstox_api_key,
            "client_secret": s.upstox_api_secret,
            "redirect_uri": s.upstox_redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                TOKEN_URL,
                data=form,
                headers={
                    "accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ── Read-only data (M4) ───────────────────────────────────────────────────
    async def _get(self, path: str, access_token: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{UPSTOX_BASE_URL}{path}",
                headers={"Accept": "application/json", "Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_positions(self, access_token: str) -> list[NormalizedPosition]:
        await instruments.ensure_loaded()
        body = await self._get(POSITIONS_PATH, access_token)
        return [_normalize_position(r) for r in (body.get("data") or [])]

    async def get_holdings(self, access_token: str) -> list[NormalizedPosition]:
        await instruments.ensure_loaded()
        body = await self._get(HOLDINGS_PATH, access_token)
        return [_normalize_position(r) for r in (body.get("data") or [])]

    async def get_margin(self, access_token: str) -> dict:
        body = await self._get(FUNDS_PATH, access_token)
        return _normalize_margin(body.get("data") or {})

    async def get_option_chain(self, analytics_token: str, symbol: str, expiry: str) -> dict:
        raise NotImplementedError("Upstox.get_option_chain lands in M6")
