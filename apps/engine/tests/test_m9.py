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


# ── journal stats (pure) ──────────────────────────────────────────────────────
def test_compute_stats_mixed_book():
    trades = [
        {"realized_pnl": 1000.0, "underlying": "NIFTY", "closed_at": "2026-06-01"},
        {"realized_pnl": -400.0, "underlying": "NIFTY", "closed_at": "2026-06-02"},
        {"realized_pnl": 600.0, "underlying": "BANKNIFTY", "closed_at": "2026-06-03"},
        {"realized_pnl": None, "underlying": "NIFTY", "closed_at": None},  # open
    ]
    s = journal_service.compute_stats(trades)
    assert s.closed_trades == 3
    assert s.open_trades == 1
    assert s.total_realized_pnl == 1200.0
    assert abs(s.win_rate - 2 / 3) < 1e-9
    assert s.avg_win == 800.0
    assert s.avg_loss == -400.0
    assert s.profit_factor == 4.0  # 1600 gross win / 400 gross loss
    assert s.best == 1000.0
    assert s.worst == -400.0
    assert s.pnl_by_underlying == {"NIFTY": 600.0, "BANKNIFTY": 600.0}
    assert s.equity_curve == [1000.0, 600.0, 1200.0]  # cumulative, close-time order


def test_compute_stats_empty_and_all_open():
    assert journal_service.compute_stats([]).closed_trades == 0
    open_only = journal_service.compute_stats([{"realized_pnl": None, "closed_at": None}])
    assert open_only.closed_trades == 0
    assert open_only.open_trades == 1
    assert open_only.win_rate is None
    assert open_only.equity_curve == []


def test_underlying_of_ignores_ui_placeholders():
    assert journal_service.underlying_of([{"symbol": "LEG1"}, {"symbol": "NIFTY"}]) == "NIFTY"
    assert journal_service.underlying_of([{"symbol": "LEG1"}]) is None
    assert journal_service.underlying_of([]) is None


def test_template_review_is_compliant_and_descriptive():
    review = journal_service.template_review(
        {
            "realized_pnl": -1500.0,
            "legs": [{"symbol": "NIFTY", "option_type": "CE", "strike": 22000, "side": "SELL",
                      "lots": 1}],
        }
    )
    _safe, flagged = advice_filter.screen(review)
    assert flagged is False  # never advises
    assert "advice nahi" in review.lower()

    open_review = journal_service.template_review({"realized_pnl": None, "legs": []})
    assert "open hai" in open_review.lower()


# ── endpoint auth gating ──────────────────────────────────────────────────────
def test_journal_endpoints_require_auth():
    assert client.get("/journal").status_code == 401
    assert client.post("/journal", json={"legs": []}).status_code == 401
    assert client.post("/journal/some-id/review").status_code == 401
    assert client.delete("/journal/some-id").status_code == 401
