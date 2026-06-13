"""Integration tests for the live quant HTTP endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

LONG_CALL = {
    "symbol": "NIFTY",
    "option_type": "CE",
    "strike": 100.0,
    "side": "BUY",
    "lots": 1,
    "lot_size": 50,
    "iv": 0.20,
}


def test_payoff_endpoint():
    res = client.post(
        "/payoff",
        json={
            "legs": [LONG_CALL],
            "spot": 100.0,
            "days_to_expiry": 365,
            "steps": 400,
            "spot_range_pct": 0.3,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["spots"]) == 400
    assert len(body["breakevens"]) == 1
    assert body["max_loss"] < 0 < body["max_profit"]


def test_scenario_endpoint_spot_up():
    res = client.post(
        "/scenario",
        json={"legs": [LONG_CALL], "spot": 100.0, "spot_move_pct": 0.02},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["pnl_delta"] > 0
    assert body["new_greeks"]["delta_direction"] == "bullish"


def test_pop_endpoint_lognormal():
    res = client.post(
        "/pop",
        json={"legs": [LONG_CALL], "spot": 100.0, "atm_iv": 0.20, "days_to_expiry": 365},
    )
    assert res.status_code == 200
    prob = res.json()["probability_of_profit"]
    assert 0.0 < prob < 1.0
