"""Adapter between the API models (app.models) and the quant core (app.quant).

Keeps HTTP/Pydantic concerns out of the pure quant math.
"""

from __future__ import annotations

from datetime import date

from app import quant
from app.config import get_settings
from app.models import (
    Greeks as ApiGreeks,
)
from app.models import (
    Leg as ApiLeg,
)
from app.models import (
    PayoffRequest,
    PayoffResponse,
    PopRequest,
    PopResponse,
    PortfolioGreeks,
    ScenarioRequest,
    ScenarioResponse,
)

DEFAULT_IV = 0.18  # used only when a leg supplies no IV and none is passed in


def _years_to_expiry(api_leg: ApiLeg, fallback_days: float | None) -> float:
    if api_leg.expiry:
        days = (date.fromisoformat(api_leg.expiry) - date.today()).days
        return max(days, 0) / 365.0
    if fallback_days is not None:
        return max(fallback_days, 0.0) / 365.0
    return 0.0


def _to_quant_leg(api_leg: ApiLeg, default_iv: float, fallback_days: float | None) -> quant.Leg:
    sigma = api_leg.iv if api_leg.iv is not None else default_iv
    return quant.Leg(
        option_type=api_leg.option_type.value if api_leg.option_type else None,
        strike=api_leg.strike or 0.0,
        t=_years_to_expiry(api_leg, fallback_days),
        sigma=sigma,
        side=api_leg.side.value,
        lots=api_leg.lots,
        lot_size=api_leg.lot_size,
    )


def _to_quant_legs(
    api_legs: list[ApiLeg], default_iv: float, fallback_days: float | None
) -> list[quant.Leg]:
    return [_to_quant_leg(leg, default_iv, fallback_days) for leg in api_legs]


def _market(spot: float) -> quant.Market:
    return quant.Market(spot=spot, r=get_settings().risk_free_rate)


def _to_api_greeks(g: quant.Greeks) -> ApiGreeks:
    return ApiGreeks(delta=g.delta, gamma=g.gamma, theta=g.theta, vega=g.vega, rho=g.rho)


def _to_api_portfolio(risk: quant.PortfolioRisk) -> PortfolioGreeks:
    return PortfolioGreeks(
        net=_to_api_greeks(risk.net),
        delta_rupees_per_pct=risk.delta_rupees_per_pct,
        theta_rupees_per_day=risk.theta_rupees_per_day,
        vega_rupees_per_point=risk.vega_rupees_per_point,
        delta_direction=risk.delta_direction,
    )


# ── Public entry points used by the API router ───────────────────────────────
def compute_payoff(req: PayoffRequest) -> PayoffResponse:
    default_iv = req.iv if req.iv is not None else DEFAULT_IV
    legs = _to_quant_legs(req.legs, default_iv, req.days_to_expiry)
    res = quant.payoff(legs, _market(req.spot), range_pct=req.spot_range_pct, steps=req.steps)
    return PayoffResponse(
        spots=res.spots,
        pnl_expiry=res.pnl_expiry,
        pnl_t0=res.pnl_t0,
        breakevens=res.breakevens,
        max_profit=res.max_profit,
        max_loss=res.max_loss,
    )


def compute_scenario(req: ScenarioRequest) -> ScenarioResponse:
    legs = _to_quant_legs(req.legs, DEFAULT_IV, None)
    res = quant.run_scenario(
        legs,
        _market(req.spot),
        spot_move_pct=req.spot_move_pct,
        iv_change_pts=req.iv_change_pts,
        days_elapsed=req.days_elapsed,
    )
    return ScenarioResponse(
        pnl_delta=res.pnl_delta,
        per_leg=res.per_leg,
        new_greeks=_to_api_portfolio(res.new_greeks),
    )


def compute_pop(req: PopRequest) -> PopResponse:
    legs = _to_quant_legs(req.legs, req.atm_iv, req.days_to_expiry)
    mkt = _market(req.spot)
    t = req.days_to_expiry / 365.0 if req.days_to_expiry is not None else None
    if req.mode == "monte_carlo":
        prob = quant.pop_monte_carlo(legs, mkt, sigma=req.atm_iv, t=t, n_paths=req.n_paths)
    else:
        prob = quant.pop_lognormal(legs, mkt, sigma=req.atm_iv, t=t)
    # NaN -> None (no finite horizon / vol)
    prob = None if prob != prob else float(prob)
    return PopResponse(probability_of_profit=prob, mode=req.mode)
