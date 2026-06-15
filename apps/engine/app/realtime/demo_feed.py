"""Synthetic market-data feed for demo mode (BROKER=mock).

Drop-in replacement for `upstox_feed.stream_ticks`: yields the same
`{instrument_key: Tick}` batches, but the prices are a small random walk around
plausible base levels instead of a live Upstox socket. No token, no network.

Hypothetical data for education/analytics only — never live quotes or advice.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator

from app.realtime.feed_decode import Tick

# Base price by instrument key; anything else gets a hash-derived option premium.
_BASE_PRICES = {
    "NSE_INDEX|Nifty 50": 24_500.0,
    "NSE_INDEX|Nifty Bank": 52_000.0,
}


def _base_price(key: str) -> float:
    if key in _BASE_PRICES:
        return _BASE_PRICES[key]
    if "Bank" in key:
        return 52_000.0
    if "Nifty" in key:
        return 24_500.0
    # Deterministic-but-varied option premium in ₹40–₹300.
    return 40.0 + (hash(key) % 2600) / 10.0


def _make_tick(key: str, price: float, mode: str) -> Tick:
    is_index = key in _BASE_PRICES
    # option_greeks mode carries OI/IV/Greeks for option legs (not indices).
    if mode == "option_greeks" and not is_index:
        return Tick(
            instrument_key=key,
            ltp=round(price, 2),
            close_price=round(price * 0.99, 2),
            oi=float(50_000 + hash(key) % 80_000),
            iv=0.14,
            greeks={"delta": 0.42, "theta": -3.1, "gamma": 0.0009, "vega": 5.4, "rho": 1.2},
        )
    return Tick(instrument_key=key, ltp=round(price, 2), close_price=round(price * 0.99, 2))


async def stream_ticks(
    analytics_token: str,
    instrument_keys: list[str],
    mode: str = "option_greeks",
    *,
    interval: float = 1.0,
    max_batches: int | None = None,
    rng: random.Random | None = None,
) -> AsyncIterator[dict[str, Tick]]:
    """Yield a tick batch for `instrument_keys` every `interval` seconds.

    Runs forever by default (real feed behaviour); `max_batches` bounds it for
    tests. `analytics_token` is accepted for signature compatibility and ignored.
    """
    rng = rng or random.Random()
    prices = {key: _base_price(key) for key in instrument_keys}
    emitted = 0
    while max_batches is None or emitted < max_batches:
        if emitted:  # don't delay the very first batch
            await asyncio.sleep(interval)
        for key, price in prices.items():
            # ±0.15% gaussian step, floored so premiums stay positive.
            prices[key] = max(round(price * (1 + rng.gauss(0, 0.0015)), 2), 0.05)
        yield {key: _make_tick(key, prices[key], mode) for key in instrument_keys}
        emitted += 1
