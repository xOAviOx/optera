"""Quant core — Black-Scholes, IV solver, Greeks, payoff, scenario, POP, Monte Carlo.

Every public function here is validated against textbook reference values in
tests/test_quant.py. Keep that suite green before relying on this code.
"""

from app.quant.black_scholes import bs_greeks, bs_price
from app.quant.iv import IVResult, implied_vol
from app.quant.payoff import PayoffResult, payoff
from app.quant.pop import pop_lognormal, pop_monte_carlo
from app.quant.portfolio import PortfolioRisk, leg_price, portfolio_greeks
from app.quant.scenario import ScenarioResult, run_scenario
from app.quant.types import Greeks, Leg, Market

__all__ = [
    "Greeks",
    "IVResult",
    "Leg",
    "Market",
    "PayoffResult",
    "PortfolioRisk",
    "ScenarioResult",
    "bs_greeks",
    "bs_price",
    "implied_vol",
    "leg_price",
    "payoff",
    "pop_lognormal",
    "pop_monte_carlo",
    "portfolio_greeks",
    "run_scenario",
]
