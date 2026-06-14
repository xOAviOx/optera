"""Tests for the /stream WebSocket bridge (M4 Phase 2), offline.

`forward_ticks` is driven with a fake tick source + fake sender (no network), and
the endpoint's auth gating is checked via the FastAPI test client.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.realtime import upstox_feed
from app.realtime.feed_decode import Tick
from app.services import stream_service
from app.services.stream_service import JsonSender

client = TestClient(app)

NIFTY = "NSE_INDEX|Nifty 50"
OPTION = "NSE_FO|44120"


# ── tick_to_payload ───────────────────────────────────────────────────────────
def test_tick_to_payload_drops_none():
    t = Tick(instrument_key=NIFTY, ltp=23456.7, close_price=23400.0)
    assert stream_service.tick_to_payload(t) == {"ltp": 23456.7, "close": 23400.0}


def test_tick_to_payload_includes_greeks():
    t = Tick(instrument_key=OPTION, ltp=120.5, iv=0.18, oi=1000, greeks={"delta": 0.5})
    payload = stream_service.tick_to_payload(t)
    assert payload == {"ltp": 120.5, "iv": 0.18, "oi": 1000, "greeks": {"delta": 0.5}}


# ── forward_ticks ─────────────────────────────────────────────────────────────
def _collector() -> tuple[list[dict], JsonSender]:
    sent: list[dict] = []

    async def send(msg: dict) -> None:
        sent.append(msg)

    return sent, send


async def test_forward_ticks_pumps_batches_then_closes():
    sent, send = _collector()

    async def fake_source(token, keys, mode):
        yield {NIFTY: Tick(instrument_key=NIFTY, ltp=23456.7, close_price=23400.0)}
        yield {OPTION: Tick(instrument_key=OPTION, ltp=120.5, iv=0.18)}

    await stream_service.forward_ticks(
        send, "tok", [NIFTY, OPTION], "option_greeks", tick_source=fake_source
    )

    assert [m["type"] for m in sent] == ["ticks", "ticks", "feed_closed"]
    assert sent[0]["data"][NIFTY] == {"ltp": 23456.7, "close": 23400.0}
    assert sent[1]["data"][OPTION] == {"ltp": 120.5, "iv": 0.18}


async def test_forward_ticks_reports_feed_error():
    sent, send = _collector()

    async def boom_source(token, keys, mode):
        raise upstox_feed.FeedError("upstream down")
        yield  # pragma: no cover — makes this an async generator

    await stream_service.forward_ticks(send, "tok", [NIFTY], "ltpc", tick_source=boom_source)

    assert len(sent) == 1
    assert sent[0]["type"] == "error"
    assert "upstream down" in sent[0]["detail"]


# ── endpoint auth gating ──────────────────────────────────────────────────────
def test_stream_rejects_missing_token():
    with client.websocket_connect("/stream") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "token" in msg["detail"].lower()


def test_stream_rejects_invalid_token():
    with client.websocket_connect("/stream?token=not-a-jwt") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "invalid token" in msg["detail"].lower()
