"""Phase 1 tests: Upstox positions/holdings/margin normalization (offline).

Instrument metadata is injected via instruments.load_records, and the broker
HTTP call is monkeypatched, so these run with no network access.
"""

import pytest
from fastapi.testclient import TestClient

from app.brokers import instruments
from app.brokers.instruments import _parse_expiry
from app.brokers.upstox import UpstoxAdapter, _normalize_margin, _normalize_position
from app.main import app

client = TestClient(app)

SAMPLE_INSTRUMENTS = [
    {
        "instrument_key": "NSE_FO|44120",
        "trading_symbol": "NIFTY 24500 CE",
        "name": "NIFTY",
        "exchange": "NSE",
        "instrument_type": "CE",
        "segment": "NSE_FO",
        "lot_size": 50,
        "strike_price": 24500,
        "expiry": 1700000000000,  # 2023-11-14 (epoch ms)
        "underlying_key": "NSE_INDEX|Nifty 50",
    },
    {
        "instrument_key": "NSE_FO|55000",
        "trading_symbol": "NIFTY FUT",
        "name": "NIFTY",
        "exchange": "NSE",
        "instrument_type": "FUT",
        "segment": "NSE_FO",
        "lot_size": 50,
        "expiry": 1700000000000,
        "underlying_key": "NSE_INDEX|Nifty 50",
    },
]


@pytest.fixture
def loaded_instruments():
    instruments.load_records(SAMPLE_INSTRUMENTS)
    yield
    instruments.load_records([])  # reset global registry


# ── pure helpers ──────────────────────────────────────────────────────────────
def test_parse_expiry_epoch_ms():
    assert _parse_expiry(1700000000000) == "2023-11-14"
    assert _parse_expiry(None) is None
    assert _parse_expiry(0) is None


def test_normalize_option_position(loaded_instruments):
    rec = {
        "instrument_token": "NSE_FO|44120",
        "trading_symbol": "NIFTY 24500 CE",
        "quantity": -100,  # short 2 lots
        "average_price": 120.5,
        "last_price": 98.0,
        "pnl": 2250.0,
    }
    pos = _normalize_position(rec)
    assert pos.option_type == "CE"
    assert pos.strike == 24500.0
    assert pos.expiry == "2023-11-14"
    assert pos.lot_size == 50
    assert pos.quantity == -100
    assert pos.name == "NIFTY"


def test_normalize_future_has_no_option_fields(loaded_instruments):
    rec = {"instrument_token": "NSE_FO|55000", "quantity": 50, "average_price": 24000.0}
    pos = _normalize_position(rec)
    assert pos.option_type is None
    assert pos.strike is None
    assert pos.lot_size == 50


def test_normalize_unknown_instrument_degrades():
    instruments.load_records([])  # nothing known
    rec = {"instrument_token": "NSE_FO|99999", "trading_symbol": "X", "quantity": 50}
    pos = _normalize_position(rec)
    assert pos.lot_size == 1  # safe fallback
    assert pos.option_type is None and pos.strike is None


def test_normalize_margin_sums_segments():
    data = {
        "equity": {"used_margin": 1000.0, "available_margin": 5000.0},
        "commodity": {"used_margin": 500.0, "available_margin": 2000.0},
    }
    m = _normalize_margin(data)
    assert m["used"] == 1500.0
    assert m["available"] == 7000.0
    assert m["equity"]["available_margin"] == 5000.0


# ── adapter wiring (HTTP mocked) ──────────────────────────────────────────────
async def test_get_positions_calls_and_normalizes(loaded_instruments, monkeypatch):
    adapter = UpstoxAdapter()

    async def fake_get(path, token):
        assert path == "/portfolio/short-term-positions"
        assert token == "decrypted-token"
        return {
            "status": "success",
            "data": [
                {
                    "instrument_token": "NSE_FO|44120",
                    "trading_symbol": "NIFTY 24500 CE",
                    "quantity": 50,
                    "average_price": 100.0,
                    "last_price": 120.0,
                    "pnl": 1000.0,
                }
            ],
        }

    monkeypatch.setattr(adapter, "_get", fake_get)
    positions = await adapter.get_positions("decrypted-token")
    assert len(positions) == 1
    assert positions[0].option_type == "CE"
    assert positions[0].strike == 24500.0


async def test_get_margin_normalizes(monkeypatch):
    adapter = UpstoxAdapter()

    async def fake_get(path, token):
        assert path == "/user/get-funds-and-margin"
        return {"data": {"equity": {"used_margin": 10.0, "available_margin": 90.0}}}

    monkeypatch.setattr(adapter, "_get", fake_get)
    m = await adapter.get_margin("tok")
    assert m["used"] == 10.0
    assert m["available"] == 90.0
    assert m["equity"] == {"used_margin": 10.0, "available_margin": 90.0}
    assert m["commodity"] is None


# ── endpoint auth gating ──────────────────────────────────────────────────────
def test_positions_requires_auth():
    assert client.get("/positions").status_code == 401


def test_margin_requires_auth():
    assert client.get("/margin").status_code == 401
