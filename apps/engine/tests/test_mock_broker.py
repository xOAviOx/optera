"""Demo-mode tests: the mock broker serves a synthetic book with no credentials.

Covers the MockBrokerAdapter data, factory selection via BROKER=mock, the
token-free positions path, and the synthetic /stream tick source.
"""

import random

import pytest

from app.brokers import factory
from app.brokers.mock import MockBrokerAdapter
from app.config import get_settings
from app.realtime import demo_feed
from app.services import positions_service, stream_service


@pytest.fixture
def demo_mode(monkeypatch):
    """Flip the shared settings singleton to BROKER=mock for the test."""
    monkeypatch.setattr(get_settings(), "broker", "mock")
    factory._instances.clear()
    yield
    factory._instances.clear()


# ── adapter data ──────────────────────────────────────────────────────────────
async def test_mock_positions_are_a_consistent_option_book():
    positions = await MockBrokerAdapter().get_positions("")
    assert len(positions) == 5

    by_symbol = {p.tradingsymbol: p for p in positions}
    short_call = by_symbol["NIFTY 25000 CE"]
    assert short_call.option_type == "CE"
    assert short_call.strike == 25_000.0
    assert short_call.quantity == -75  # short 1 lot
    assert short_call.lot_size == 75
    assert short_call.expiry  # a real ISO date string
    # PnL must follow signed qty: a short profits when the premium falls.
    assert short_call.pnl == pytest.approx((62.0 - 85.0) * -75)
    assert short_call.pnl > 0

    losing_put = by_symbol["NIFTY 24000 PE"]
    assert losing_put.pnl == pytest.approx((95.0 - 78.0) * -75)
    assert losing_put.pnl < 0


async def test_mock_holdings_are_equities():
    holdings = await MockBrokerAdapter().get_holdings("")
    assert holdings
    for h in holdings:
        assert h.option_type is None
        assert h.strike is None
        assert h.lot_size == 1


async def test_mock_margin_shape():
    m = await MockBrokerAdapter().get_margin("")
    assert m["used"] > 0 and m["available"] > 0
    assert m["equity"]["available_margin"] == m["available"]
    assert m["commodity"] is None


async def test_mock_option_chain_brackets_spot():
    chain = await MockBrokerAdapter().get_option_chain("", "NIFTY", "")
    assert chain["symbol"] == "NIFTY"
    assert chain["spot"] == 24_500.0
    assert len(chain["strikes"]) == 11  # ATM ±5
    sample = chain["strikes"][0]
    assert {"ltp", "iv", "oi"} <= sample["ce"].keys()
    assert {"ltp", "iv", "oi"} <= sample["pe"].keys()


# ── factory + service wiring ──────────────────────────────────────────────────
def test_factory_selects_mock_in_demo_mode(demo_mode):
    adapter = factory.get_broker_adapter()
    assert isinstance(adapter, MockBrokerAdapter)
    assert adapter.requires_auth is False


def test_factory_defaults_to_upstox(monkeypatch):
    from app.brokers.upstox import UpstoxAdapter

    # Pin the broker so the test is hermetic regardless of the dev's local .env
    # (which may set BROKER=mock for demo work).
    monkeypatch.setattr(get_settings(), "broker", "upstox")
    factory._instances.clear()
    assert isinstance(factory.get_broker_adapter(), UpstoxAdapter)


async def test_positions_service_needs_no_token_in_demo_mode(demo_mode, monkeypatch):
    # If the service touches Supabase in demo mode, this would blow up.
    async def boom(*a, **k):
        raise AssertionError("Supabase must not be queried in demo mode")

    monkeypatch.setattr(positions_service.supabase, "get_broker_connection", boom)
    positions = await positions_service.list_positions("any-user")
    assert len(positions) == 5


# ── demo stream feed ──────────────────────────────────────────────────────────
async def test_demo_feed_yields_ticks_with_greeks():
    keys = ["NSE_INDEX|Nifty 50", "NSE_FO|NIFTY25000CE"]
    batches = [
        b
        async for b in demo_feed.stream_ticks(
            "ignored", keys, "option_greeks", interval=0, max_batches=3, rng=random.Random(0)
        )
    ]
    assert len(batches) == 3
    for batch in batches:
        assert set(batch) == set(keys)
        assert all(t.ltp > 0 for t in batch.values())
    # Index has no option greeks; the option leg does.
    assert batches[0]["NSE_INDEX|Nifty 50"].greeks is None
    assert batches[0]["NSE_FO|NIFTY25000CE"].greeks is not None


async def test_stream_service_demo_token_and_source(demo_mode):
    assert stream_service.is_demo() is True
    assert await stream_service.resolve_feed_token("user") == "demo"
    assert stream_service.active_tick_source() is demo_feed.stream_ticks
