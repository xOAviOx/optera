"""Payoff engine — vectorized P&L across a spot grid, at expiry and T+0.

Cost basis is the current theoretical price of each leg (so the T+0 curve passes
through ~0 at the current spot). P&L per leg = qty * (value_at_spot - current_value).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.quant.black_scholes import bs_price
from app.quant.types import Leg, Market


@dataclass(frozen=True)
class PayoffResult:
    spots: list[float]
    pnl_expiry: list[float]
    pnl_t0: list[float]
    breakevens: list[float]
    max_profit: float | None
    max_loss: float | None


def _leg_value(leg: Leg, spots: np.ndarray, market: Market, *, at_expiry: bool):
    if not leg.is_option:
        return spots  # future/underlying value tracks spot 1:1
    if at_expiry:
        if leg.option_type.upper() in ("CE", "C", "CALL"):
            return np.maximum(spots - leg.strike, 0.0)
        return np.maximum(leg.strike - spots, 0.0)
    return bs_price(spots, leg.strike, leg.t, market.r, leg.sigma, leg.option_type, market.b)


def payoff(
    legs: list[Leg],
    market: Market,
    range_pct: float = 0.15,
    steps: int = 200,
) -> PayoffResult:
    spots = np.linspace(market.spot * (1 - range_pct), market.spot * (1 + range_pct), steps)

    pnl_expiry = np.zeros_like(spots)
    pnl_t0 = np.zeros_like(spots)

    for leg in legs:
        if leg.is_option:
            cost = float(
                bs_price(
                    market.spot, leg.strike, leg.t, market.r, leg.sigma, leg.option_type, market.b
                )
            )
        else:
            cost = market.spot
        expiry_val = _leg_value(leg, spots, market, at_expiry=True)
        t0_val = _leg_value(leg, spots, market, at_expiry=False)
        pnl_expiry += leg.qty * (expiry_val - cost)
        pnl_t0 += leg.qty * (t0_val - cost)

    breakevens = _find_breakevens(spots, pnl_expiry)

    return PayoffResult(
        spots=[float(x) for x in spots],
        pnl_expiry=[float(x) for x in pnl_expiry],
        pnl_t0=[float(x) for x in pnl_t0],
        breakevens=breakevens,
        max_profit=float(np.max(pnl_expiry)),
        max_loss=float(np.min(pnl_expiry)),
    )


def _find_breakevens(spots: np.ndarray, pnl: np.ndarray) -> list[float]:
    """Linear-interpolated zero crossings of the expiry P&L curve."""
    out: list[float] = []
    for i in range(len(spots) - 1):
        y0, y1 = pnl[i], pnl[i + 1]
        if y0 == 0.0:
            out.append(float(spots[i]))
        elif y0 * y1 < 0.0:
            x0, x1 = spots[i], spots[i + 1]
            out.append(float(x0 - y0 * (x1 - x0) / (y1 - y0)))
    return out
