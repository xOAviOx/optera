"""Tests for the Upstox V3 feed client (M4 Phase 2), offline.

The upstream raw-frame source is injected, so `stream_ticks` is exercised against
real serialized protobuf frames without a live analytics token or network.
"""

import json

import pytest

from app.realtime import upstox_feed
from app.realtime.proto import MarketDataFeed_pb2 as pb

OPTION = "NSE_FO|44120"


def _option_frame() -> bytes:
    resp = pb.FeedResponse(type=pb.live_feed)
    flg = resp.feeds[OPTION].firstLevelWithGreeks
    flg.ltpc.ltp = 120.50
    flg.iv = 0.182
    flg.oi = 1_000
    flg.optionGreeks.delta = 0.55
    return resp.SerializeToString()


# ── build_sub_message ─────────────────────────────────────────────────────────
def test_build_sub_message_shape():
    raw = upstox_feed.build_sub_message([OPTION], mode="option_greeks", guid="abc")
    msg = json.loads(raw)
    assert msg == {
        "guid": "abc",
        "method": "sub",
        "data": {"mode": "option_greeks", "instrumentKeys": [OPTION]},
    }


def test_build_sub_message_defaults_guid():
    msg = json.loads(upstox_feed.build_sub_message([OPTION]))
    assert msg["data"]["mode"] == upstox_feed.DEFAULT_MODE
    assert msg["guid"]  # auto-generated


def test_build_sub_message_rejects_bad_mode():
    with pytest.raises(ValueError):
        upstox_feed.build_sub_message([OPTION], mode="nonsense")


def test_build_sub_message_rejects_empty_keys():
    with pytest.raises(ValueError):
        upstox_feed.build_sub_message([])


# ── stream_ticks (injected upstream) ──────────────────────────────────────────
async def test_stream_ticks_decodes_and_skips_empty():
    async def fake_frames(token, keys, mode):
        assert token == "analytics-tok"
        assert keys == [OPTION]
        yield _option_frame()
        yield pb.FeedResponse(type=pb.live_feed).SerializeToString()  # empty -> skipped

    batches = [
        b
        async for b in upstox_feed.stream_ticks(
            "analytics-tok", [OPTION], "option_greeks", raw_frames=fake_frames
        )
    ]
    assert len(batches) == 1  # the empty frame produced no tick
    tick = batches[0][OPTION]
    assert tick.ltp == 120.50
    assert tick.iv == 0.182
    assert tick.greeks["delta"] == 0.55
