"""Generalized Black-Scholes-Merton pricing and Greeks.

Uses a cost-of-carry parameter `b` so the same code prices:
  * b = r   -> classic Black-Scholes on a non-dividend stock/index spot
  * b = 0   -> options on a future (Black-76), still discounted at r
  * b = r-q -> with continuous dividend yield q

Index options on NIFTY/BANKNIFTY are European, so this is exact for them.
All math validated against textbook reference values in tests/test_quant.py.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.special import ndtr  # fast, vectorized standard-normal CDF

from app.quant.types import Greeks

_SQRT_2PI = math.sqrt(2.0 * math.pi)

_CALL_TOKENS = {"CE", "C", "CALL"}
_PUT_TOKENS = {"PE", "P", "PUT"}


def _is_call(option_type: str) -> bool:
    t = str(option_type).upper()
    if t in _CALL_TOKENS:
        return True
    if t in _PUT_TOKENS:
        return False
    raise ValueError(f"Unknown option_type: {option_type!r}")


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def d1_d2(S: float, K: float, T: float, sigma: float, b: float) -> tuple[float, float]:
    vt = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (b + 0.5 * sigma * sigma) * T) / vt
    return d1, d1 - vt


def bs_price(
    S,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    b: float | None = None,
):
    """Price a European option. `S` may be a scalar or a NumPy array (vectorized
    over spot); `K`, `T`, `r`, `sigma` are scalars. At/after expiry or with σ<=0
    returns undiscounted intrinsic value."""
    is_call = _is_call(option_type)
    S_arr = np.asarray(S, dtype=float)

    if T <= 0 or sigma <= 0:
        intrinsic = np.maximum(S_arr - K, 0.0) if is_call else np.maximum(K - S_arr, 0.0)
        return _scalarize(intrinsic)

    bb = r if b is None else b
    vt = sigma * math.sqrt(T)
    d1 = (np.log(S_arr / K) + (bb + 0.5 * sigma * sigma) * T) / vt
    d2 = d1 - vt
    disc = math.exp(-r * T)
    carry = math.exp((bb - r) * T)

    if is_call:
        px = S_arr * carry * ndtr(d1) - K * disc * ndtr(d2)
    else:
        px = K * disc * ndtr(-d2) - S_arr * carry * ndtr(-d1)
    return _scalarize(px)


def bs_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    b: float | None = None,
) -> Greeks:
    """Per-unit Greeks (theta per day, vega/rho per 1% point). Scalar inputs."""
    is_call = _is_call(option_type)

    if T <= 0 or sigma <= 0:
        # Degenerate: delta is a step, the rest collapse to ~0.
        if is_call:
            delta = 1.0 if S > K else 0.0
        else:
            delta = -1.0 if S < K else 0.0
        return Greeks(delta=delta, gamma=0.0, theta=0.0, vega=0.0, rho=0.0)

    bb = r if b is None else b
    sqrt_t = math.sqrt(T)
    d1, d2 = d1_d2(S, K, T, sigma, bb)
    pdf = _norm_pdf(d1)
    disc = math.exp(-r * T)
    carry = math.exp((bb - r) * T)

    gamma = carry * pdf / (S * sigma * sqrt_t)
    vega = S * carry * pdf * sqrt_t / 100.0  # per 1 vol point
    common_theta = -(S * carry * pdf * sigma) / (2.0 * sqrt_t)

    if is_call:
        delta = carry * ndtr(d1)
        theta_year = common_theta - (bb - r) * S * carry * ndtr(d1) - r * K * disc * ndtr(d2)
        rho = K * T * disc * ndtr(d2) / 100.0
    else:
        delta = carry * (ndtr(d1) - 1.0)
        theta_year = common_theta + (bb - r) * S * carry * ndtr(-d1) + r * K * disc * ndtr(-d2)
        rho = -K * T * disc * ndtr(-d2) / 100.0

    return Greeks(
        delta=float(delta),
        gamma=float(gamma),
        theta=float(theta_year) / 365.0,
        vega=float(vega),
        rho=float(rho),
    )


def vega_raw(S: float, K: float, T: float, r: float, sigma: float, b: float | None = None) -> float:
    """Vega per unit σ (not per vol point). Used by the IV Newton step."""
    if T <= 0 or sigma <= 0:
        return 0.0
    bb = r if b is None else b
    sqrt_t = math.sqrt(T)
    d1, _ = d1_d2(S, K, T, sigma, bb)
    carry = math.exp((bb - r) * T)
    return S * carry * _norm_pdf(d1) * sqrt_t


def _scalarize(arr: np.ndarray):
    a = np.asarray(arr)
    return float(a) if a.ndim == 0 else a
