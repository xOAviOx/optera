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
    StrategyAnalyzeRequest,
    StrategyAnalyzeResponse,
)

# Rough naked-short margin as a fraction of notional (SPAN+Exposure ballpark).
# Deliberately conservative and clearly labelled — never presented as broker-exact.
_NAKED_MARGIN_PCT = 0.15

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


# ── Strategy analyzer (M9) ────────────────────────────────────────────────────
def _net_premium(quant_legs: list[quant.Leg], mkt: quant.Market) -> float:
    """Entry cash flow across option legs: credit (+) / debit (-), in ₹.

    BUY pays premium (cash out, debit); SELL receives it (cash in, credit).
    leg.qty is signed (+ for BUY), so cash flow = -qty * price.
    """
    total = 0.0
    for leg in quant_legs:
        if leg.is_option:
            total += -leg.qty * quant.leg_price(leg, mkt)
    return total


def _margin_estimate(
    quant_legs: list[quant.Leg], mkt: quant.Market, max_loss: float | None
) -> tuple[bool, float]:
    """Rough, education-only margin. Defined-risk => capped max loss; otherwise a
    flat % of short notional. Returns (defined_risk, estimate)."""
    net_ce = sum(leg.sign * leg.lots for leg in quant_legs if leg.option_type == "CE")
    net_pe = sum(leg.sign * leg.lots for leg in quant_legs if leg.option_type == "PE")
    defined = net_ce >= 0 and net_pe >= 0
    if defined and max_loss is not None:
        return True, abs(max_loss)
    short_notional = sum(
        mkt.spot * leg.lots * leg.lot_size
        for leg in quant_legs
        if leg.is_option and leg.sign < 0
    )
    return False, _NAKED_MARGIN_PCT * short_notional


def analyze_strategy(req: StrategyAnalyzeRequest) -> StrategyAnalyzeResponse:
    """One-shot analysis of a hypothetical structure: payoff extremes, net premium,
    Greeks, probability of profit, and a rough margin estimate. No advice."""
    default_iv = req.iv_pct / 100.0
    legs = _to_quant_legs(req.legs, default_iv, req.dte)
    mkt = _market(req.spot)

    payoff = quant.payoff(legs, mkt, range_pct=req.spot_range_pct, steps=req.steps)
    greeks = quant.portfolio_greeks(legs, mkt)
    t = req.dte / 365.0 if req.dte else None
    prob = quant.pop_lognormal(legs, mkt, sigma=default_iv, t=t)
    prob = None if prob != prob else float(prob)  # NaN -> None

    defined, margin = _margin_estimate(legs, mkt, payoff.max_loss)
    note = (
        "Rough education-only estimate — not your broker's SPAN+Exposure margin. "
        "Defined-risk structures use the capped max loss; naked shorts use "
        f"~{int(_NAKED_MARGIN_PCT * 100)}% of short notional."
    )
    return StrategyAnalyzeResponse(
        net_premium=_net_premium(legs, mkt),
        max_profit=payoff.max_profit,
        max_loss=payoff.max_loss,
        breakevens=payoff.breakevens,
        greeks=_to_api_portfolio(greeks),
        probability_of_profit=prob,
        defined_risk=defined,
        margin_estimate=margin,
        margin_note=note,
    )
