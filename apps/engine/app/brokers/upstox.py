"""Upstox adapter (default broker, free tier).

M1: stub only — the real OAuth token exchange, REST calls, and protobuf websocket
decoding land in M2/M4. Methods raise NotImplementedError so callers fail loudly
rather than silently returning fake data.
"""

from __future__ import annotations

from app.brokers.base import BrokerAdapter, NormalizedPosition

UPSTOX_BASE_URL = "https://api.upstox.com/v2"


class UpstoxAdapter(BrokerAdapter):
    broker_name = "upstox"

    async def get_positions(self, access_token: str) -> list[NormalizedPosition]:
        raise NotImplementedError("Upstox.get_positions lands in M2/M4")

    async def get_holdings(self, access_token: str) -> list[NormalizedPosition]:
        raise NotImplementedError("Upstox.get_holdings lands in M2/M4")

    async def get_margin(self, access_token: str) -> dict:
        raise NotImplementedError("Upstox.get_margin lands in M4")

    async def get_option_chain(self, analytics_token: str, symbol: str, expiry: str) -> dict:
        raise NotImplementedError("Upstox.get_option_chain lands in M6")
