"""Implied volatility solver.

Newton-Raphson fast path (uses vega), falling back to Brent's method (robust,
bracketed) when Newton steps out of bounds or vega is tiny. Returns an IVResult
that flags low-confidence / no-solution cases (deep ITM, illiquid, arb-violating
prints) rather than returning a misleading number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.optimize import brentq

from app.quant.black_scholes import _is_call, bs_price, vega_raw

SIGMA_MIN = 1e-3
SIGMA_MAX = 5.0


@dataclass(frozen=True)
class IVResult:
    iv: float | None
    converged: bool
    low_confidence: bool
    method: str  # 'newton' | 'brent' | 'none'


def _price(S, K, T, r, sigma, is_call, b):
    return bs_price(S, K, T, r, sigma, "CE" if is_call else "PE", b)


def implied_vol(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str,
    b: float | None = None,
) -> IVResult:
    is_call = _is_call(option_type)

    if T <= 0 or market_price <= 0:
        return IVResult(None, False, True, "none")

    bb = r if b is None else b
    carry = math.exp((bb - r) * T)
    disc = math.exp(-r * T)

    # No-arbitrage bounds for the discounted European price.
    if is_call:
        lower = max(S * carry - K * disc, 0.0)
        upper = S * carry
    else:
        lower = max(K * disc - S * carry, 0.0)
        upper = K * disc

    # Prices at/through the bounds have no finite-vol solution; flag rather than lie.
    if market_price <= lower + 1e-12 or market_price >= upper - 1e-12:
        return IVResult(None, False, True, "none")

    # --- Newton-Raphson fast path ---
    # Brenner-Subrahmanyam seed for ATM-ish options.
    sigma = max(math.sqrt(2.0 * math.pi / T) * market_price / S, 0.05)
    sigma = min(max(sigma, SIGMA_MIN), SIGMA_MAX)
    for _ in range(50):
        diff = _price(S, K, T, r, sigma, is_call, b) - market_price
        v = vega_raw(S, K, T, r, sigma, b)  # per unit σ
        if v < 1e-8:
            break  # flat — hand off to Brent
        step = diff / v
        new_sigma = sigma - step
        if not (SIGMA_MIN <= new_sigma <= SIGMA_MAX):
            break
        sigma = new_sigma
        if abs(step) < 1e-7:
            low_conf = v < 1e-3  # near-zero vega => unstable IV
            return IVResult(float(sigma), True, low_conf, "newton")

    # --- Brent fallback (bracketed, robust) ---
    f = lambda s: _price(S, K, T, r, s, is_call, b) - market_price  # noqa: E731
    f_lo, f_hi = f(SIGMA_MIN), f(SIGMA_MAX)
    if f_lo * f_hi > 0:
        return IVResult(None, False, True, "none")  # no sign change => no root in range
    root = brentq(f, SIGMA_MIN, SIGMA_MAX, xtol=1e-8, maxiter=200)
    low_conf = vega_raw(S, K, T, r, root, b) < 1e-3
    return IVResult(float(root), True, low_conf, "brent")
