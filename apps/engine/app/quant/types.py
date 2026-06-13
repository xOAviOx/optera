"""Shared quant dataclasses. Pure data — no broker/API coupling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Greeks:
    """Per-unit option Greeks (one contract, not scaled by lots/lot_size).

    Conventions:
      delta : ∂V/∂S            (call ∈ [0,1], put ∈ [-1,0])
      gamma : ∂²V/∂S²
      theta : per CALENDAR DAY (year/365), usually negative for long options
      vega  : per 1 VOL POINT  (i.e. a 1% absolute change in σ)
      rho   : per 1% absolute change in the rate
    """

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

    def scaled(self, qty: float) -> Greeks:
        """Scale by signed quantity (sign * lots * lot_size)."""
        return Greeks(
            delta=self.delta * qty,
            gamma=self.gamma * qty,
            theta=self.theta * qty,
            vega=self.vega * qty,
            rho=self.rho * qty,
        )


@dataclass(frozen=True)
class Leg:
    """A single position leg in quant-internal form.

    `option_type` is 'CE'/'PE' for options, or None for a future/underlying leg.
    `t` is time to expiry in years; `sigma` is decimal vol (0.18 == 18%).
    """

    option_type: str | None
    strike: float
    t: float
    sigma: float
    side: str  # 'BUY' | 'SELL'
    lots: int
    lot_size: int

    @property
    def sign(self) -> int:
        return 1 if self.side.upper() == "BUY" else -1

    @property
    def qty(self) -> int:
        return self.sign * self.lots * self.lot_size

    @property
    def is_option(self) -> bool:
        return self.option_type is not None


@dataclass(frozen=True)
class Market:
    """Market context shared by all legs of one underlying.

    `spot` is the underlying price (pass the future/forward for index options).
    `b` is the cost of carry: default (None) => b = r (classic Black-Scholes);
    pass b = 0 to price options on a future (Black-76 style).
    """

    spot: float
    r: float = 0.065
    b: float | None = None

    def carry(self) -> float:
        return self.r if self.b is None else self.b
