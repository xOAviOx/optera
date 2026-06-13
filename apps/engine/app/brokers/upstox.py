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

from app.brokers.base import BrokerAdapter, NormalizedPosition
from app.config import get_settings

UPSTOX_BASE_URL = "https://api.upstox.com/v2"
AUTHORIZE_URL = f"{UPSTOX_BASE_URL}/login/authorization/dialog"
TOKEN_URL = f"{UPSTOX_BASE_URL}/login/authorization/token"


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

    # ── Read-only data (M4/M6) ────────────────────────────────────────────────
    async def get_positions(self, access_token: str) -> list[NormalizedPosition]:
        raise NotImplementedError("Upstox.get_positions lands in M4")

    async def get_holdings(self, access_token: str) -> list[NormalizedPosition]:
        raise NotImplementedError("Upstox.get_holdings lands in M4")

    async def get_margin(self, access_token: str) -> dict:
        raise NotImplementedError("Upstox.get_margin lands in M4")

    async def get_option_chain(self, analytics_token: str, symbol: str, expiry: str) -> dict:
        raise NotImplementedError("Upstox.get_option_chain lands in M6")
