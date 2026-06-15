"""Paper-trading simulator: deterministic market + accounting (pure, offline).

The DB-backed service path isn't exercised here (needs Supabase); these cover the
quant-critical pieces — the market function and the P&L/cash/Greeks math.
"""

import pytest

from app.services import sim_service
from app.sim import accounting, market
from app.sim.accounting import PaperPosition


def _pos(**kw) -> PaperPosition:
    base = {
        "id": "p1",
        "symbol": "NIFTY",
        "option_type": "CE",
        "strike": 24_500.0,
        "side": "BUY",
        "lots": 1,
        "lot_size": 75,
        "entry_tick": 0,
        "entry_spot": 24_500.0,
        "entry_price": 200.0,
        "expiry_tick": market.expiry_tick_for(0, 7),
        "status": "open",
    }
    base.update(kw)
    return PaperPosition(**base)


# ── deterministic market ──────────────────────────────────────────────────────
def test_spot_is_deterministic_and_bounded():
    for tick in (0, 1, 37, 500, 9999):
        a = market.spot("NIFTY", tick)
        b = market.spot("NIFTY", tick)
        assert a == b  # pure function of tick
        # value-noise log-return is bounded by the symbol amplitude (~±3%).
        assert 24_500.0 * 0.95 < a < 24_500.0 * 1.05


def test_spot_actually_moves():
    series = [market.spot("NIFTY", t) for t in range(0, 200, 10)]
    assert len(set(series)) > 5  # not a flat line


def test_unknown_symbol_raises():
    with pytest.raises(KeyError):
        market.spot("RELIANCE", 0)


def test_expiry_and_year_fraction():
    assert market.expiry_tick_for(0, 7) == 7 * market.TICKS_PER_DAY
    yte = market.years_to_expiry(0, market.expiry_tick_for(0, 7))
    assert yte == pytest.approx(7 * 375 / (375 * 252))
    # decays to zero at/after expiry
    assert market.years_to_expiry(10_000, market.expiry_tick_for(0, 7)) == 0.0


# ── cash / P&L accounting ─────────────────────────────────────────────────────
def test_open_cash_delta_signs():
    # BUY (signed_qty > 0) debits premium; SELL credits it.
    assert accounting.open_cash_delta(200.0, 75) == -15_000.0
    assert accounting.open_cash_delta(200.0, -75) == 15_000.0


def test_round_trip_cash_equals_realized():
    pos = _pos(side="SELL", entry_price=200.0)
    sq = pos.signed_qty
    exit_price = 150.0  # short premium fell -> profit
    realized = accounting.realized_on_close(pos, exit_price)
    cash_cycle = accounting.open_cash_delta(pos.entry_price, sq) + accounting.close_cash_delta(
        pos, exit_price
    )
    assert cash_cycle == pytest.approx(realized)
    assert realized > 0  # sold at 200, bought back at 150


def test_mark_equals_quote_at_same_tick():
    # A freshly opened leg marks to its own fill at the same tick (realized ≈ 0).
    tick = 0
    expiry = market.expiry_tick_for(tick, 7)
    fill = accounting.quote("NIFTY", "CE", 24_500.0, expiry, tick)
    pos = _pos(entry_price=fill, expiry_tick=expiry)
    assert accounting.mark_price(pos, tick) == pytest.approx(fill, abs=0.01)


def test_marked_position_unrealized_follows_sign():
    long_call = _pos(side="BUY", entry_price=100.0)
    m = accounting.marked_position(long_call, 0)
    expected = (m["mark_price"] - 100.0) * long_call.signed_qty
    assert m["unrealized_pnl"] == pytest.approx(expected, abs=0.01)


# ── snapshot identities ───────────────────────────────────────────────────────
def test_snapshot_equity_identity():
    account = {"capital": 500_000.0, "cash": 485_000.0, "realized_pnl": 0.0}
    positions = [_pos(side="BUY", entry_price=200.0)]
    snap = accounting.account_snapshot(account, positions, 5)
    # equity = cash + marked value of open positions
    position_value = sum(p["value"] for p in snap["positions"])
    assert snap["equity"] == pytest.approx(snap["cash"] + position_value)
    assert snap["total_pnl"] == pytest.approx(snap["equity"] - snap["capital"])
    assert snap["unrealized_pnl"] == pytest.approx(
        sum(p["unrealized_pnl"] for p in snap["positions"])
    )


def test_short_option_reserves_margin_long_does_not():
    account = {"capital": 500_000.0, "cash": 500_000.0, "realized_pnl": 0.0}
    long_only = accounting.account_snapshot(account, [_pos(side="BUY")], 0)
    short_only = accounting.account_snapshot(account, [_pos(side="SELL")], 0)
    assert long_only["margin_used"] == 0.0
    assert short_only["margin_used"] > 0.0


def test_net_delta_direction():
    account = {"capital": 500_000.0, "cash": 500_000.0, "realized_pnl": 0.0}
    long_call = accounting.account_snapshot(account, [_pos(side="BUY", option_type="CE")], 0)
    short_call = accounting.account_snapshot(account, [_pos(side="SELL", option_type="CE")], 0)
    assert long_call["greeks"]["net"]["delta"] > 0
    assert short_call["greeks"]["net"]["delta"] < 0


# ── chain (pure service helper) ───────────────────────────────────────────────
def test_chain_brackets_spot_with_positive_premiums():
    chain = sim_service.chain("NIFTY", 0, 7.0, depth=6)
    assert chain["symbol"] == "NIFTY"
    assert chain["lot_size"] == 75
    assert len(chain["strikes"]) == 13  # ATM ±6
    assert all(s["ce"]["ltp"] >= 0 and s["pe"]["ltp"] >= 0 for s in chain["strikes"])
    # deep ITM call (low strike) is worth more than a deep OTM call (high strike)
    assert chain["strikes"][0]["ce"]["ltp"] > chain["strikes"][-1]["ce"]["ltp"]


def test_chain_unknown_symbol_raises_sim_error():
    with pytest.raises(sim_service.SimError):
        sim_service.chain("RELIANCE", 0, 7.0)
