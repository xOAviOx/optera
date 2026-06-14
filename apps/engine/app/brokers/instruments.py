"""Upstox instruments master — resolves instrument metadata by instrument_key.

Positions/holdings responses identify instruments only by `instrument_token`
(an instrument_key like "NSE_FO|44120") plus a trading symbol. The lot size,
option type, strike and expiry come from Upstox's instruments master file, which
we load once per day into an in-memory registry.

The pure `load_records` entry point is injectable, so tests populate the registry
without any network access.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
from dataclasses import dataclass

import httpx

# NSE file covers equities, indices and the NSE F&O segment (NIFTY/BANKNIFTY etc.).
NSE_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"

_OPTION_TYPES = {"CE", "PE"}


@dataclass(frozen=True)
class Instrument:
    instrument_key: str
    trading_symbol: str | None
    name: str | None
    exchange: str | None
    instrument_type: str | None  # EQ / FUT / CE / PE / INDEX
    segment: str | None
    lot_size: int | None
    strike_price: float | None
    expiry: str | None  # ISO date
    underlying_key: str | None

    @property
    def option_type(self) -> str | None:
        return self.instrument_type if self.instrument_type in _OPTION_TYPES else None


_REGISTRY: dict[str, Instrument] = {}
_LOADED_ON: dt.date | None = None


def _parse_expiry(val: object) -> str | None:
    if val in (None, "", 0):
        return None
    # Upstox supplies expiry as epoch milliseconds.
    try:
        ts = int(val)  # type: ignore[arg-type]
        return dt.datetime.fromtimestamp(ts / 1000, tz=dt.UTC).date().isoformat()
    except (ValueError, TypeError, OSError, OverflowError):
        return str(val)[:10] or None


def _num(val: object) -> float | None:
    if val in (None, "", 0):
        return None
    try:
        return float(val)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _to_instrument(rec: dict) -> Instrument:
    lot = rec.get("lot_size")
    return Instrument(
        instrument_key=rec.get("instrument_key", ""),
        trading_symbol=rec.get("trading_symbol"),
        name=rec.get("name"),
        exchange=rec.get("exchange"),
        instrument_type=rec.get("instrument_type"),
        segment=rec.get("segment"),
        lot_size=int(lot) if lot not in (None, "", 0) else None,
        strike_price=_num(rec.get("strike_price")),
        expiry=_parse_expiry(rec.get("expiry")),
        underlying_key=rec.get("underlying_key"),
    )


def load_records(records: list[dict]) -> int:
    """Populate the registry from already-parsed instrument records. Returns count."""
    global _REGISTRY, _LOADED_ON
    registry: dict[str, Instrument] = {}
    for rec in records:
        key = rec.get("instrument_key")
        if key:
            registry[key] = _to_instrument(rec)
    _REGISTRY = registry
    _LOADED_ON = dt.date.today()
    return len(registry)


async def fetch_and_load(url: str = NSE_URL) -> int:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        records = json.loads(gzip.decompress(resp.content))
    return load_records(records)


async def ensure_loaded(url: str = NSE_URL) -> None:
    """Load the master once per calendar day (idempotent, network only on first call)."""
    if not _REGISTRY or _LOADED_ON != dt.date.today():
        await fetch_and_load(url)


def get(instrument_key: str) -> Instrument | None:
    return _REGISTRY.get(instrument_key)


def is_loaded() -> bool:
    return bool(_REGISTRY)
