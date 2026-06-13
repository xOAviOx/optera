"""Quant core reference tests.

Black-Scholes values are checked against textbook references (Hull, et al.) for the
canonical case S=100, K=100, T=1, r=0.05, sigma=0.20:
    call = 10.4506, put = 5.5735
    delta_call = 0.6368, gamma = 0.0188, vega(1pt) = 0.3752,
    theta_call/yr = -6.414, rho_call(1%) = 0.5323
"""

import math

import numpy as np
import pytest

from app.quant import (
    Leg,
    Market,
    bs_greeks,
    bs_price,
    implied_vol,
    payoff,
    pop_lognormal,
    pop_monte_carlo,
    portfolio_greeks,
    run_scenario,
)
from app.quant.black_scholes import vega_raw

# Canonical reference inputs
S, K, T, R, SIG = 100.0, 100.0, 1.0, 0.05, 0.20


# ── Black-Scholes price ───────────────────────────────────────────────────────
def test_bs_call_price_textbook():
    assert math.isclose(bs_price(S, K, T, R, SIG, "CE"), 10.4506, abs_tol=1e-3)


def test_bs_put_price_textbook():
    assert math.isclose(bs_price(S, K, T, R, SIG, "PE"), 5.5735, abs_tol=1e-3)


def test_put_call_parity():
    c = bs_price(S, K, T, R, SIG, "CE")
    p = bs_price(S, K, T, R, SIG, "PE")
    assert math.isclose(c - p, S - K * math.exp(-R * T), abs_tol=1e-9)


def test_price_at_expiry_is_intrinsic():
    assert bs_price(110, 100, 0.0, R, SIG, "CE") == 10.0
    assert bs_price(90, 100, 0.0, R, SIG, "PE") == 10.0
    assert bs_price(90, 100, 0.0, R, SIG, "CE") == 0.0


def test_bs_price_vectorized_over_spot():
    spots = np.array([90.0, 100.0, 110.0])
    px = bs_price(spots, K, T, R, SIG, "CE")
    assert isinstance(px, np.ndarray)
    assert px.shape == (3,)
    # monotonic increasing in spot for a call
    assert px[0] < px[1] < px[2]


# ── Greeks ────────────────────────────────────────────────────────────────────
def test_call_greeks_textbook():
    g = bs_greeks(S, K, T, R, SIG, "CE")
    assert math.isclose(g.delta, 0.636831, abs_tol=1e-4)
    assert math.isclose(g.gamma, 0.018762, abs_tol=1e-5)
    assert math.isclose(g.vega, 0.375240, abs_tol=1e-4)  # per 1 vol point
    assert math.isclose(g.theta, -6.41403 / 365.0, abs_tol=1e-5)  # per day
    assert math.isclose(g.rho, 0.532325, abs_tol=1e-4)  # per 1%


def test_put_call_delta_relationship():
    gc = bs_greeks(S, K, T, R, SIG, "CE")
    gp = bs_greeks(S, K, T, R, SIG, "PE")
    assert math.isclose(gc.delta - gp.delta, 1.0, abs_tol=1e-9)  # carry=1 when b=r


def test_gamma_and_vega_equal_for_call_and_put():
    gc = bs_greeks(S, K, T, R, SIG, "CE")
    gp = bs_greeks(S, K, T, R, SIG, "PE")
    assert math.isclose(gc.gamma, gp.gamma, abs_tol=1e-12)
    assert math.isclose(gc.vega, gp.vega, abs_tol=1e-12)


def test_vega_matches_finite_difference():
    base = bs_price(S, K, T, R, SIG, "CE")
    bumped = bs_price(S, K, T, R, SIG + 0.01, "CE")
    g = bs_greeks(S, K, T, R, SIG, "CE")
    assert math.isclose(g.vega, bumped - base, abs_tol=2e-3)  # vega ≈ ΔP per 1 vol pt


# ── Black-76 (options on a future, b=0) ───────────────────────────────────────
def test_black76_matches_discounted_intrinsic_form():
    F = 100.0
    price = bs_price(F, K, T, R, SIG, "CE", b=0.0)
    # closed form: e^{-rT}[F N(d1) - K N(d2)]
    vt = SIG * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * SIG * SIG * T) / vt
    d2 = d1 - vt
    from scipy.special import ndtr

    expected = math.exp(-R * T) * (F * ndtr(d1) - K * ndtr(d2))
    assert math.isclose(price, expected, abs_tol=1e-9)


# ── Implied volatility ────────────────────────────────────────────────────────
@pytest.mark.parametrize("true_sigma", [0.08, 0.15, 0.25, 0.45, 0.80])
@pytest.mark.parametrize("opt", ["CE", "PE"])
def test_iv_round_trip(true_sigma, opt):
    price = bs_price(S, K, T, R, true_sigma, opt)
    res = implied_vol(price, S, K, T, R, opt)
    assert res.converged
    assert res.iv is not None
    assert math.isclose(res.iv, true_sigma, abs_tol=1e-4)


def test_iv_round_trip_otm_strike():
    price = bs_price(S, 110, T, R, 0.3, "CE")
    res = implied_vol(price, S, 110, T, R, "CE")
    assert res.iv is not None and math.isclose(res.iv, 0.3, abs_tol=1e-4)


def test_iv_below_intrinsic_returns_none():
    # A call can't trade below its discounted intrinsic -> no real IV.
    res = implied_vol(0.01, 130, 100, T, R, "CE")
    assert res.iv is None
    assert res.low_confidence


# ── Portfolio Greeks ──────────────────────────────────────────────────────────
def _mkt():
    return Market(spot=100.0, r=R)


def test_portfolio_scales_with_lots_and_lotsize():
    leg = Leg("CE", 100.0, T, SIG, "BUY", lots=2, lot_size=50)
    risk = portfolio_greeks([leg], _mkt())
    unit = bs_greeks(100.0, 100.0, T, R, SIG, "CE")
    assert math.isclose(risk.net.delta, unit.delta * 2 * 50, abs_tol=1e-6)


def test_long_call_is_bullish():
    leg = Leg("CE", 100.0, T, SIG, "BUY", lots=1, lot_size=50)
    assert portfolio_greeks([leg], _mkt()).delta_direction == "bullish"


def test_short_call_is_bearish():
    leg = Leg("CE", 100.0, T, SIG, "SELL", lots=1, lot_size=50)
    assert portfolio_greeks([leg], _mkt()).delta_direction == "bearish"


def test_long_straddle_is_delta_neutral():
    # Realistic short-dated (1 week) straddle: net delta ≈ 0 vs gross delta ≈ 1.
    t = 7.0 / 365.0
    call = Leg("CE", 100.0, t, SIG, "BUY", 1, 50)
    put = Leg("PE", 100.0, t, SIG, "BUY", 1, 50)
    risk = portfolio_greeks([call, put], _mkt())
    assert risk.delta_direction == "neutral"
    assert risk.net.vega > 0  # long vol


def test_short_put_is_bullish():
    leg = Leg("PE", 100.0, T, SIG, "SELL", 1, 50)
    assert portfolio_greeks([leg], _mkt()).delta_direction == "bullish"


# ── Payoff ────────────────────────────────────────────────────────────────────
def test_long_call_payoff_shape():
    leg = Leg("CE", 100.0, T, SIG, "BUY", lots=1, lot_size=50)
    res = payoff([leg], _mkt(), range_pct=0.30, steps=400)
    premium = bs_price(100.0, 100.0, T, R, SIG, "CE")
    # max loss ≈ -premium * qty (paid premium), occurs deep OTM at expiry
    assert math.isclose(res.max_loss, -premium * 50, abs_tol=premium * 50 * 0.02)
    # one breakeven, near K + premium
    assert len(res.breakevens) == 1
    assert math.isclose(res.breakevens[0], 100.0 + premium, abs_tol=1.0)
    # upside profit
    assert res.max_profit > 0


def test_short_put_max_profit_is_premium():
    leg = Leg("PE", 100.0, T, SIG, "SELL", lots=1, lot_size=50)
    res = payoff([leg], _mkt(), range_pct=0.30, steps=400)
    premium = bs_price(100.0, 100.0, T, R, SIG, "PE")
    assert math.isclose(res.max_profit, premium * 50, abs_tol=premium * 50 * 0.02)


# ── Scenario ──────────────────────────────────────────────────────────────────
def test_scenario_no_change_is_zero():
    leg = Leg("CE", 100.0, T, SIG, "BUY", 1, 50)
    res = run_scenario([leg], _mkt(), 0.0, 0.0, 0.0)
    assert abs(res.pnl_delta) < 1e-6


def test_scenario_spot_up_helps_long_call():
    leg = Leg("CE", 100.0, T, SIG, "BUY", 1, 50)
    res = run_scenario([leg], _mkt(), spot_move_pct=0.02)
    assert res.pnl_delta > 0
    assert len(res.per_leg) == 1


def test_scenario_iv_crush_hurts_long_option():
    leg = Leg("CE", 100.0, T, SIG, "BUY", 1, 50)
    res = run_scenario([leg], _mkt(), iv_change_pts=-5.0)
    assert res.pnl_delta < 0  # long vega loses on IV drop


def test_scenario_theta_decay_hurts_long_option():
    leg = Leg("CE", 100.0, T, SIG, "BUY", 1, 50)
    res = run_scenario([leg], _mkt(), days_elapsed=7.0)
    assert res.pnl_delta < 0


# ── Probability of Profit ─────────────────────────────────────────────────────
def test_pop_long_call_matches_analytic():
    leg = Leg("CE", 100.0, T, SIG, "BUY", 1, 50)
    mkt = _mkt()
    pop = pop_lognormal([leg], mkt, sigma=SIG, t=T)
    # profit iff S_T > K + premium; analytic P(S_T > B) under drift r
    premium = bs_price(100.0, 100.0, T, R, SIG, "CE")
    B = 100.0 + premium
    from scipy.special import ndtr

    d = (math.log(100.0 / B) + (R - 0.5 * SIG * SIG) * T) / (SIG * math.sqrt(T))
    analytic = float(ndtr(d))
    assert math.isclose(pop, analytic, abs_tol=2e-3)


def test_pop_monte_carlo_agrees_with_lognormal():
    leg = Leg("CE", 100.0, T, SIG, "BUY", 1, 50)
    mkt = _mkt()
    pl = pop_lognormal([leg], mkt, sigma=SIG, t=T)
    pmc = pop_monte_carlo([leg], mkt, sigma=SIG, t=T, n_paths=40_000, seed=42)
    assert math.isclose(pl, pmc, abs_tol=0.01)


def test_pop_in_unit_interval():
    legs = [
        Leg("CE", 105.0, T, SIG, "SELL", 1, 50),
        Leg("PE", 95.0, T, SIG, "SELL", 1, 50),
    ]
    pop = pop_lognormal(legs, _mkt(), sigma=SIG, t=T)
    assert 0.0 <= pop <= 1.0


# ── sanity: vega_raw used by IV ───────────────────────────────────────────────
def test_vega_raw_positive_atm():
    assert vega_raw(S, K, T, R, SIG) > 0
