"""Quant reference tests — fleshed out in M3 against textbook Black-Scholes values.

Placeholder so the suite is wired and the expectation ('quant ships with reference
tests') is visible from M1.
"""

import pytest


@pytest.mark.skip(reason="Quant core implemented in M3")
def test_black_scholes_reference_price():
    # e.g. S=100, K=100, T=1, r=0.05, sigma=0.20 -> call ≈ 10.4506 (textbook)
    ...
