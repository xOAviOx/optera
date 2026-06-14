"""Upstox Market Data Feed V3 client (M4 Phase 2).

The live feed never re-auths daily, so we drive it with the user's one-time
*analytics* token (see CLAUDE.md), not the daily OAuth access token.

Flow (V3):
  1. GET the authorize endpoint with the analytics token -> a short-lived `wss://`
     redirect URI.
  2. Open that websocket and send a binary `sub` request naming the instrument
     keys + mode.
  3. Upstox streams binary protobuf `FeedResponse` frames, which we hand to
     `feed_decode` and surface as normalized ticks.

The upstream connection is injectable (`stream_raw_frames`) so the bridge and
tests run without a live analytics token or network.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from uuid import uuid4

import httpx
import websockets

from app.realtime import feed_decode
from app.realtime.feed_decode import Tick

AUTHORIZE_URL = "https://api.upstox.com/v3/feed/market-data-feed/authorize"

# Subscription modes Upstox V3 accepts. `option_greeks` gives the
# first-level-with-greeks feed (LTP + OI + IV + Greeks) we want for option legs.
VALID_MODES = frozenset({"ltpc", "option_greeks", "full", "full_d30"})
DEFAULT_MODE = "option_greeks"


class FeedError(RuntimeError):
    """Upstream market-data feed could not be authorized or opened."""


async def authorize(analytics_token: str) -> str:
    """Resolve the short-lived authorized `wss://` URI for the feed socket."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            AUTHORIZE_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {analytics_token}",
            },
        )
        resp.raise_for_status()
        data = resp.json().get("data") or {}
    # Upstox has used both snake_case and camelCase across versions; accept either.
    uri = data.get("authorized_redirect_uri") or data.get("authorizedRedirectUri")
    if not uri:
        raise FeedError("Upstox authorize response had no authorized_redirect_uri")
    return uri


def build_sub_message(
    instrument_keys: list[str], mode: str = DEFAULT_MODE, guid: str | None = None
) -> bytes:
    """Build the binary `sub` request frame Upstox expects (JSON encoded as bytes)."""
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported feed mode {mode!r}; expected one of {sorted(VALID_MODES)}")
    if not instrument_keys:
        raise ValueError("instrument_keys must be non-empty")
    payload = {
        "guid": guid or uuid4().hex,
        "method": "sub",
        "data": {"mode": mode, "instrumentKeys": list(instrument_keys)},
    }
    return json.dumps(payload).encode()


async def stream_raw_frames(
    analytics_token: str, instrument_keys: list[str], mode: str = DEFAULT_MODE
) -> AsyncIterator[bytes]:
    """Yield raw protobuf frames from the live Upstox feed for `instrument_keys`."""
    uri = await authorize(analytics_token)
    try:
        async with websockets.connect(uri, max_size=None) as ws:
            await ws.send(build_sub_message(instrument_keys, mode))
            async for message in ws:
                if isinstance(message, bytes):  # ignore any text/heartbeat frames
                    yield message
    except websockets.exceptions.WebSocketException as exc:
        raise FeedError(f"Upstox feed socket error: {exc}") from exc


# Type of an injectable raw-frame source (real or fake).
RawFrameSource = Callable[[str, list[str], str], AsyncIterator[bytes]]


async def stream_ticks(
    analytics_token: str,
    instrument_keys: list[str],
    mode: str = DEFAULT_MODE,
    *,
    raw_frames: RawFrameSource = stream_raw_frames,
) -> AsyncIterator[dict[str, Tick]]:
    """Yield decoded `{instrument_key: Tick}` batches from the live feed.

    Frames carrying no usable tick are skipped so consumers only see real updates.
    """
    async for raw in raw_frames(analytics_token, instrument_keys, mode):
        ticks = feed_decode.decode_ticks(raw)
        if ticks:
            yield ticks
