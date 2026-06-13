"""Probability of Profit (POP).

Two modes, both measured at expiry against the current cost basis:
  * pop_lognormal     — closed-form-ish: integrate the lognormal terminal density
                        of S_T over the profitable spot region.
  * pop_monte_carlo   — GBM terminal simulation (~10k paths) for intuition and to
                        cross-check the analytic value.
Drift defaults to the risk-free rate (risk-neutral forward).
"""

from __future__ import annotations

import math

import numpy as np

from app.quant.black_scholes import bs_price
from app.quant.types import Leg, Market


def _expiry_pnl(legs: list[Leg], market: Market, spots: np.ndarray) -> np.ndarray:
    """Total book P&L at expiry across `spots`, cost basis = current theoretical value."""
    pnl = np.zeros_like(spots, dtype=float)
    for leg in legs:
        if leg.is_option:
            cost = float(
                bs_price(
                    market.spot, leg.strike, leg.t, market.r, leg.sigma, leg.option_type, market.b
                )
            )
            if leg.option_type.upper() in ("CE", "C", "CALL"):
                payoff = np.maximum(spots - leg.strike, 0.0)
            else:
                payoff = np.maximum(leg.strike - spots, 0.0)
        else:
            cost = market.spot
            payoff = spots
        pnl += leg.qty * (payoff - cost)
    return pnl


def _horizon(legs: list[Leg], t: float | None) -> float:
    if t is not None:
        return t
    opt_ts = [leg.t for leg in legs if leg.is_option and leg.t > 0]
    return max(opt_ts) if opt_ts else 0.0


def pop_lognormal(
    legs: list[Leg],
    market: Market,
    sigma: float,
    t: float | None = None,
    drift: float | None = None,
    n: int = 4001,
) -> float:
    """Integrate the lognormal density of S_T over the region where book P&L > 0."""
    horizon = _horizon(legs, t)
    if horizon <= 0 or sigma <= 0:
        return float("nan")

    mu_drift = market.r if drift is None else drift
    std = sigma * math.sqrt(horizon)
    mean_log = math.log(market.spot) + (mu_drift - 0.5 * sigma * sigma) * horizon

    # Spot grid spanning ±7σ in log space (captures essentially all mass).
    s_lo = math.exp(mean_log - 7.0 * std)
    s_hi = math.exp(mean_log + 7.0 * std)
    spots = np.linspace(s_lo, s_hi, n)

    # Lognormal pdf of S_T.
    pdf = np.exp(-((np.log(spots) - mean_log) ** 2) / (2.0 * std * std)) / (
        spots * std * math.sqrt(2.0 * math.pi)
    )
    pnl = _expiry_pnl(legs, market, spots)

    profitable = pnl > 0.0
    total = np.trapezoid(pdf, spots)
    prob = np.trapezoid(np.where(profitable, pdf, 0.0), spots)
    return float(prob / total) if total > 0 else float("nan")


def pop_monte_carlo(
    legs: list[Leg],
    market: Market,
    sigma: float,
    t: float | None = None,
    n_paths: int = 10_000,
    drift: float | None = None,
    seed: int | None = None,
) -> float:
    """Fraction of GBM terminal paths with book P&L > 0 at expiry."""
    horizon = _horizon(legs, t)
    if horizon <= 0 or sigma <= 0:
        return float("nan")

    mu_drift = market.r if drift is None else drift
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n_paths)
    log_return = (mu_drift - 0.5 * sigma * sigma) * horizon + sigma * math.sqrt(horizon) * z
    s_t = market.spot * np.exp(log_return)
    pnl = _expiry_pnl(legs, market, s_t)
    return float(np.mean(pnl > 0.0))
