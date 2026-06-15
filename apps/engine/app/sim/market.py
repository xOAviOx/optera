"""Deterministic simulated market.

`spot(symbol, tick)` and `iv(symbol, tick)` are pure functions of an integer
tick — built from smoothed value-noise so the path looks market-like, stays
bounded (no runaway), and is identical on every call/device. One tick ≈ one NSE
trading minute, which drives realistic (gentle) time decay.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# One tick ≈ one NSE trading minute (09:15–15:30 ≈ 375 min/day).
TICKS_PER_DAY = 375
TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class SymbolSpec:
    name: str
    base_spot: float
    strike_step: float
    lot_size: int
    base_iv: float  # decimal
    log_amplitude: float  # peak |log-return| swing around base_spot
    seed: int


# Index universe for the simulator. Lot sizes are plausible recent NSE values.
SYMBOLS: dict[str, SymbolSpec] = {
    "NIFTY": SymbolSpec("NIFTY", 24_500.0, 50.0, 75, 0.14, 0.030, 1001),
    "BANKNIFTY": SymbolSpec("BANKNIFTY", 52_000.0, 100.0, 30, 0.16, 0.040, 2002),
}


def _hash01(n: int, seed: int) -> float:
    """Deterministic pseudo-random float in [0, 1) from an integer + seed."""
    x = (n * 2_654_435_761 + seed * 40_503) & 0xFFFFFFFF
    x ^= x >> 13
    x = (x * 1_274_126_177) & 0xFFFFFFFF
    x ^= x >> 16
    return x / 0xFFFFFFFF


def _value_noise(t: float, seed: int) -> float:
    """Smooth noise in [-1, 1]: hashed lattice values, smoothstep-interpolated."""
    i = math.floor(t)
    f = t - i
    a = _hash01(i, seed) * 2.0 - 1.0
    b = _hash01(i + 1, seed) * 2.0 - 1.0
    u = f * f * (3.0 - 2.0 * f)  # smoothstep
    return a * (1.0 - u) + b * u


def _fbm(t: float, seed: int) -> float:
    """Fractal value-noise (3 octaves) in ~[-1, 1] — richer, still smooth."""
    return (
        0.6 * _value_noise(t, seed)
        + 0.3 * _value_noise(t * 2.0 + 11.0, seed)
        + 0.1 * _value_noise(t * 4.0 + 23.0, seed)
    )


def _spec(symbol: str) -> SymbolSpec:
    spec = SYMBOLS.get(symbol.upper())
    if spec is None:
        raise KeyError(f"Unknown sim symbol {symbol!r}; known: {sorted(SYMBOLS)}")
    return spec


def spot(symbol: str, tick: int) -> float:
    """Underlying level for `symbol` at `tick` (bounded random-walk-like path)."""
    spec = _spec(symbol)
    # tick/30 → a gentle wiggle every ~30 ticks; amplitude caps the % swing.
    log_return = spec.log_amplitude * _fbm(tick / 30.0, spec.seed)
    return round(spec.base_spot * math.exp(log_return), 2)


def iv(symbol: str, tick: int) -> float:
    """ATM implied vol (decimal) for `symbol` at `tick` — drifts gently."""
    spec = _spec(symbol)
    drift = 0.15 * _fbm(tick / 45.0 + 7.0, spec.seed + 99)
    return round(max(spec.base_iv * (1.0 + drift), 0.03), 4)


def years_to_expiry(tick: int, expiry_tick: int) -> float:
    """Time to expiry in years for Black–Scholes, from ticks remaining."""
    remaining = max(expiry_tick - tick, 0)
    return remaining / (TICKS_PER_DAY * TRADING_DAYS_PER_YEAR)


def expiry_tick_for(entry_tick: int, dte_days: float) -> int:
    """Tick at which an option opened at `entry_tick` with `dte_days` expires."""
    return entry_tick + int(round(max(dte_days, 0.0) * TICKS_PER_DAY))


def atm_strike(symbol: str, tick: int) -> float:
    """Nearest strike to spot on the symbol's strike ladder."""
    spec = _spec(symbol)
    return round(spot(symbol, tick) / spec.strike_step) * spec.strike_step


def strike_ladder(symbol: str, tick: int, depth: int = 6) -> list[float]:
    """`2*depth+1` strikes centered on ATM, on the symbol's step."""
    spec = _spec(symbol)
    atm = atm_strike(symbol, tick)
    return [atm + i * spec.strike_step for i in range(-depth, depth + 1)]
