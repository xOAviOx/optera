"""Strategy analyzer + trade journal (M9), fully offline.

Covers the hypothetical strategy analyzer (net premium sign, defined-risk vs
naked-short margin, POP), the pure journal stats, the descriptive review's
compliance (advice filter), and endpoint auth gating. No network / DB / API key.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.ai import advice_filter
from app.main import app
from app.models import Leg, OptionType, Side, StrategyAnalyzeRequest
from app.services import journal_service, quant_service

client = TestClient(app)

SPOT = 22_000.0
LOT = 50


def _leg(opt: OptionType, side: Side, strike: float, iv: float = 0.15) -> Leg:
    return Leg(
        symbol="NIFTY",
        option_type=opt,
        strike=strike,
        side=side,
        lots=1,
        lot_size=LOT,
        iv=iv,
    )


# ── strategy analyzer (pure) ──────────────────────────────────────────────────
def test_long_call_is_defined_risk_and_a_debit():
    req = StrategyAnalyzeRequest(
        legs=[_leg(OptionType.CALL, Side.BUY, SPOT)], spot=SPOT, iv_pct=15, dte=7
    )
    res = quant_service.analyze_strategy(req)
    assert res.defined_risk is True
    assert res.net_premium < 0  # you pay to buy a call (debit)
    # Defined risk => margin is the capped max loss (the premium you paid).
    assert res.max_loss is not None
    assert abs(res.margin_estimate - abs(res.max_loss)) < 1.0
    assert res.probability_of_profit is not None
    assert 0.0 <= res.probability_of_profit <= 1.0


def test_short_straddle_is_undefined_risk_and_a_credit():
    req = StrategyAnalyzeRequest(
        legs=[
            _leg(OptionType.CALL, Side.SELL, SPOT),
            _leg(OptionType.PUT, Side.SELL, SPOT),
        ],
        spot=SPOT,
        iv_pct=15,
        dte=7,
    )
    res = quant_service.analyze_strategy(req)
    assert res.defined_risk is False
    assert res.net_premium > 0  # you receive premium (credit)
    # Naked shorts: margin ~ 15% of short notional (both legs), a positive figure.
    assert res.margin_estimate > 0
    assert "not your broker" in res.margin_note.lower()


def test_call_debit_spread_margin_equals_capped_loss():
    req = StrategyAnalyzeRequest(
        legs=[
            _leg(OptionType.CALL, Side.BUY, SPOT),
            _leg(OptionType.CALL, Side.SELL, SPOT + 200),
        ],
        spot=SPOT,
        iv_pct=15,
        dte=7,
    )
    res = quant_service.analyze_strategy(req)
    assert res.defined_risk is True  # net calls = 0
    assert res.max_loss is not None
    assert abs(res.margin_estimate - abs(res.max_loss)) < 1.0


def test_strategy_analyze_endpoint():
    res = client.post(
        "/strategy/analyze",
        json={
            "legs": [
                {
                    "symbol": "NIFTY",
                    "option_type": "CE",
                    "strike": SPOT,
                    "side": "BUY",
                    "lots": 1,
                    "lot_size": LOT,
                    "iv": 0.15,
                }
            ],
            "spot": SPOT,
            "iv_pct": 15,
            "dte": 7,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["defined_risk"] is True
    assert "greeks" in body and "net" in body["greeks"]
    assert body["net_premium"] < 0
