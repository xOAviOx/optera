"""Co-pilot tools — the only way the model gets numbers.

Each tool runs against the user's current (hypothetical) strategy context and
calls the tested quant core, so the model never invents Greeks or P&L. Legs are
normalized to carry IV + expiry (mirroring the web client) so /scenario — which
reads IV/expiry from legs, not the request — works regardless of the caller.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from app.ai.providers.base import ToolSpec
from app.models import Leg, PayoffRequest, PopRequest, ScenarioRequest
from app.services import quant_service


@dataclass
class StrategyContext:
    legs: list[Leg]
    spot: float
    iv_pct: float = 14.0  # ATM IV in percent
    dte: float = 7.0  # days to expiry


def _normalized_legs(ctx: StrategyContext) -> list[Leg]:
    iv = ctx.iv_pct / 100.0
    expiry = (dt.date.today() + dt.timedelta(days=max(0, round(ctx.dte)))).isoformat()
    return [
        leg.model_copy(
            update={
                "iv": leg.iv if leg.iv is not None else iv,
                "expiry": leg.expiry or expiry,
            }
        )
        for leg in ctx.legs
    ]


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="get_payoff_summary",
        description=(
            "Max profit, max loss, breakeven prices and probability of profit for the "
            "user's current option structure. Use for 'explain my risk / payoff' questions."
        ),
        parameters={"type": "object", "properties": {}},
    ),
    ToolSpec(
        name="get_greeks",
        description=(
            "Current net portfolio Greeks (delta, gamma, theta, vega, rho) and their rupee "
            "sensitivities for the structure. Use for questions about delta/theta/vega exposure."
        ),
        parameters={"type": "object", "properties": {}},
    ),
    ToolSpec(
        name="run_what_if",
        description=(
            "Reprice the structure under a hypothetical move and return the rupee P&L impact "
            "plus the new Greeks. Use for 'what if NIFTY moves X% / IV changes / N days pass'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "spot_move_pct": {
                    "type": "number",
                    "description": "Underlying move in percent, e.g. -3 for a 3% drop.",
                },
                "iv_change_pts": {
                    "type": "number",
                    "description": "Change in IV in volatility points, e.g. -5 for an IV crush.",
                },
                "days_elapsed": {
                    "type": "number",
                    "description": "Calendar days of time decay to apply.",
                },
            },
        },
    ),
]


def _payoff_summary(ctx: StrategyContext) -> dict[str, Any]:
    legs = _normalized_legs(ctx)
    pf = quant_service.compute_payoff(
        PayoffRequest(legs=legs, spot=ctx.spot, iv=ctx.iv_pct / 100.0, days_to_expiry=ctx.dte)
    )
    pop = quant_service.compute_pop(
        PopRequest(legs=legs, spot=ctx.spot, atm_iv=ctx.iv_pct / 100.0, days_to_expiry=ctx.dte)
    )
    return {
        "max_profit": pf.max_profit,
        "max_loss": pf.max_loss,
        "breakevens": pf.breakevens,
        "probability_of_profit": pop.probability_of_profit,
        "currency": "INR",
    }


def _greeks(ctx: StrategyContext) -> dict[str, Any]:
    sc = quant_service.compute_scenario(ScenarioRequest(legs=_normalized_legs(ctx), spot=ctx.spot))
    g = sc.new_greeks
    return {
        "net": g.net.model_dump(),
        "delta_rupees_per_pct": g.delta_rupees_per_pct,
        "theta_rupees_per_day": g.theta_rupees_per_day,
        "vega_rupees_per_point": g.vega_rupees_per_point,
        "delta_direction": g.delta_direction,
        "currency": "INR",
    }


def _what_if(ctx: StrategyContext, args: dict[str, Any]) -> dict[str, Any]:
    sc = quant_service.compute_scenario(
        ScenarioRequest(
            legs=_normalized_legs(ctx),
            spot=ctx.spot,
            spot_move_pct=float(args.get("spot_move_pct", 0.0)) / 100.0,
            iv_change_pts=float(args.get("iv_change_pts", 0.0)),
            days_elapsed=float(args.get("days_elapsed", 0.0)),
        )
    )
    return {
        "pnl_delta": sc.pnl_delta,
        "new_greeks": {
            "net": sc.new_greeks.net.model_dump(),
            "delta_direction": sc.new_greeks.delta_direction,
            "theta_rupees_per_day": sc.new_greeks.theta_rupees_per_day,
        },
        "currency": "INR",
    }


def dispatch(ctx: StrategyContext | None, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run tool `name`. Returns a compact JSON-able dict for the model to read."""
    if ctx is None or not ctx.legs:
        return {"error": "No strategy is loaded. Ask the user to build one in the Risk workbench."}
    if name == "get_payoff_summary":
        return _payoff_summary(ctx)
    if name == "get_greeks":
        return _greeks(ctx)
    if name == "run_what_if":
        return _what_if(ctx, args)
    return {"error": f"Unknown tool {name!r}"}
