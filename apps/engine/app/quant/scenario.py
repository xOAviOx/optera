"""Scenario / stress engine.

Given {spot_move_pct, iv_change_pts, days_elapsed}, reprice the whole book and
return the ₹ P&L delta, a per-leg breakdown, and the new portfolio Greeks.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.quant.portfolio import PortfolioRisk, leg_price, portfolio_greeks
from app.quant.types import Leg, Market


@dataclass(frozen=True)
class ScenarioResult:
    pnl_delta: float
    per_leg: list[dict]
    new_greeks: PortfolioRisk


def run_scenario(
    legs: list[Leg],
    market: Market,
    spot_move_pct: float = 0.0,
    iv_change_pts: float = 0.0,
    days_elapsed: float = 0.0,
) -> ScenarioResult:
    new_spot = market.spot * (1.0 + spot_move_pct)
    new_market = Market(spot=new_spot, r=market.r, b=market.b)

    iv_shift = iv_change_pts / 100.0  # vol points -> decimal
    day_shift = days_elapsed / 365.0

    shifted_legs: list[Leg] = []
    per_leg: list[dict] = []
    total_delta = 0.0

    for leg in legs:
        shifted = Leg(
            option_type=leg.option_type,
            strike=leg.strike,
            t=max(leg.t - day_shift, 0.0),
            sigma=max(leg.sigma + iv_shift, 0.0) if leg.is_option else leg.sigma,
            side=leg.side,
            lots=leg.lots,
            lot_size=leg.lot_size,
        )
        shifted_legs.append(shifted)

        before = leg_price(leg, market)
        after = leg_price(shifted, new_market)
        leg_pnl = leg.qty * (after - before)
        total_delta += leg_pnl

        per_leg.append(
            {
                "option_type": leg.option_type,
                "strike": leg.strike,
                "side": leg.side,
                "qty": leg.qty,
                "price_before": before,
                "price_after": after,
                "pnl": leg_pnl,
            }
        )

    return ScenarioResult(
        pnl_delta=total_delta,
        per_leg=per_leg,
        new_greeks=portfolio_greeks(shifted_legs, new_market),
    )
