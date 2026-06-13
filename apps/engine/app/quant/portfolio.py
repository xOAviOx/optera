"""Per-leg and portfolio-aggregate Greeks.

Aggregate Greeks are summed as unit_greek * qty, where
qty = sign(BUY/SELL) * lots * lot_size. Rupee conversions:
  delta ₹ per 1% move = net_delta_qty * spot * 0.01
  theta ₹ per day      = sum(theta_per_day * qty)
  vega  ₹ per vol point = sum(vega_per_point * qty)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.quant.black_scholes import bs_greeks, bs_price
from app.quant.types import Greeks, Leg, Market

# A book is called directionally "neutral" when its NET delta is small relative to
# its GROSS delta exposure (scale-free: works for a 1-lot or a 100-lot book).
_DIRECTION_RATIO = 0.15


@dataclass(frozen=True)
class PortfolioRisk:
    net: Greeks  # qty-scaled net Greeks
    delta_rupees_per_pct: float
    theta_rupees_per_day: float
    vega_rupees_per_point: float
    delta_direction: str  # 'bullish' | 'bearish' | 'neutral'


def leg_unit_greeks(leg: Leg, market: Market) -> Greeks:
    """Per-unit (one contract) Greeks for a leg. Futures => pure delta of 1."""
    if not leg.is_option:
        return Greeks(delta=1.0, gamma=0.0, theta=0.0, vega=0.0, rho=0.0)
    return bs_greeks(
        market.spot, leg.strike, leg.t, market.r, leg.sigma, leg.option_type, market.b
    )


def leg_price(leg: Leg, market: Market) -> float:
    if not leg.is_option:
        return market.spot
    return float(
        bs_price(market.spot, leg.strike, leg.t, market.r, leg.sigma, leg.option_type, market.b)
    )


def portfolio_greeks(legs: list[Leg], market: Market) -> PortfolioRisk:
    net = Greeks(0.0, 0.0, 0.0, 0.0, 0.0)
    net_delta_qty = 0.0
    gross_delta_qty = 0.0
    for leg in legs:
        g = leg_unit_greeks(leg, market).scaled(leg.qty)
        net = Greeks(
            delta=net.delta + g.delta,
            gamma=net.gamma + g.gamma,
            theta=net.theta + g.theta,
            vega=net.vega + g.vega,
            rho=net.rho + g.rho,
        )
        net_delta_qty += g.delta
        gross_delta_qty += abs(g.delta)

    delta_rupees_per_pct = net_delta_qty * market.spot * 0.01

    # Scale-free directional tag: |net| / gross delta.
    ratio = net_delta_qty / gross_delta_qty if gross_delta_qty > 1e-9 else 0.0
    if ratio > _DIRECTION_RATIO:
        direction = "bullish"
    elif ratio < -_DIRECTION_RATIO:
        direction = "bearish"
    else:
        direction = "neutral"

    return PortfolioRisk(
        net=net,
        delta_rupees_per_pct=delta_rupees_per_pct,
        theta_rupees_per_day=net.theta,
        vega_rupees_per_point=net.vega,
        delta_direction=direction,
    )
