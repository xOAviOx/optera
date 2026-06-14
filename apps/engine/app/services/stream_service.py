"""Live market-data stream orchestration (M4 Phase 2).

Bridges the user's encrypted Upstox *analytics* token to the live feed and pumps
normalized ticks out to a connected client. Keeps token handling and the
tick->wire shape out of the HTTP/WS router.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from app.db import supabase
from app.realtime import upstox_feed
from app.realtime.feed_decode import Tick
from app.security.crypto import decrypt_token

# Source of decoded tick batches; injectable so the bridge is testable offline.
TickSource = Callable[[str, list[str], str], AsyncIterator[dict[str, Tick]]]
# Async sender (e.g. WebSocket.send_json); injectable for the same reason.
JsonSender = Callable[[dict], Awaitable[None]]


class AnalyticsTokenMissing(RuntimeError):
    """User has no analytics token on file — the live feed cannot start."""


async def analytics_token(user_id: str) -> str:
    """Decrypt the user's stored Upstox analytics token, or raise."""
    conn = await supabase.get_broker_connection(user_id, "upstox")
    if not conn or not conn.get("analytics_token_enc"):
        raise AnalyticsTokenMissing(
            "No Upstox analytics token on file — add one to start the live feed."
        )
    return decrypt_token(conn["analytics_token_enc"])


def tick_to_payload(tick: Tick) -> dict:
    """Serialize a Tick to the JSON shape pushed to the client (drops None fields)."""
    payload: dict = {"ltp": tick.ltp}
    if tick.close_price is not None:
        payload["close"] = tick.close_price
    if tick.oi is not None:
        payload["oi"] = tick.oi
    if tick.iv is not None:
        payload["iv"] = tick.iv
    if tick.greeks is not None:
        payload["greeks"] = tick.greeks
    return payload


async def forward_ticks(
    send: JsonSender,
    token: str,
    instrument_keys: list[str],
    mode: str,
    *,
    tick_source: TickSource = upstox_feed.stream_ticks,
) -> None:
    """Pump live tick batches to `send` until the feed ends or `send` fails.

    A failing `send` (client gone) propagates so the caller can tear down the
    upstream connection. Feed errors are reported to the client, not raised.
    """
    try:
        async for ticks in tick_source(token, instrument_keys, mode):
            await send(
                {"type": "ticks", "data": {key: tick_to_payload(t) for key, t in ticks.items()}}
            )
    except upstox_feed.FeedError as exc:
        await send({"type": "error", "detail": str(exc)})
        return
    await send({"type": "feed_closed"})
