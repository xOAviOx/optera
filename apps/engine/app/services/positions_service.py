"""Live positions / margin orchestration (M4).

Loads the user's encrypted Upstox access token from Supabase, decrypts it in
memory, and calls the broker adapter. Keeps token handling and storage concerns
out of both the HTTP router and the broker adapter.
"""

from __future__ import annotations

from app.brokers.base import BrokerAdapter, NormalizedPosition
from app.brokers.factory import get_broker_adapter
from app.db import supabase
from app.models import MarginResponse
from app.security.crypto import decrypt_token


class BrokerNotConnected(RuntimeError):
    """Raised when the user has no usable Upstox access token on file."""


async def _access_token(user_id: str, adapter: BrokerAdapter) -> str:
    # Demo brokers carry their own data and ignore the token entirely.
    if not adapter.requires_auth:
        return ""
    conn = await supabase.get_broker_connection(user_id, "upstox")
    if not conn or not conn.get("access_token_enc"):
        raise BrokerNotConnected("Upstox is not connected for this user.")
    return decrypt_token(conn["access_token_enc"])


async def list_positions(user_id: str) -> list[NormalizedPosition]:
    adapter = get_broker_adapter()
    return await adapter.get_positions(await _access_token(user_id, adapter))


async def list_holdings(user_id: str) -> list[NormalizedPosition]:
    adapter = get_broker_adapter()
    return await adapter.get_holdings(await _access_token(user_id, adapter))


async def get_margin(user_id: str) -> MarginResponse:
    adapter = get_broker_adapter()
    raw = await adapter.get_margin(await _access_token(user_id, adapter))
    return MarginResponse(**raw)
