"""Live positions / margin orchestration (M4).

Loads the user's encrypted Upstox access token from Supabase, decrypts it in
memory, and calls the broker adapter. Keeps token handling and storage concerns
out of both the HTTP router and the broker adapter.
"""

from __future__ import annotations

from app.brokers.base import NormalizedPosition
from app.brokers.upstox import UpstoxAdapter
from app.db import supabase
from app.models import MarginResponse
from app.security.crypto import decrypt_token

_upstox = UpstoxAdapter()


class BrokerNotConnected(RuntimeError):
    """Raised when the user has no usable Upstox access token on file."""


async def _access_token(user_id: str) -> str:
    conn = await supabase.get_broker_connection(user_id, "upstox")
    if not conn or not conn.get("access_token_enc"):
        raise BrokerNotConnected("Upstox is not connected for this user.")
    return decrypt_token(conn["access_token_enc"])


async def list_positions(user_id: str) -> list[NormalizedPosition]:
    return await _upstox.get_positions(await _access_token(user_id))


async def list_holdings(user_id: str) -> list[NormalizedPosition]:
    return await _upstox.get_holdings(await _access_token(user_id))


async def get_margin(user_id: str) -> MarginResponse:
    raw = await _upstox.get_margin(await _access_token(user_id))
    return MarginResponse(**raw)
