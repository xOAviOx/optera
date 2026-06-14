"""Round-trip tests for the Upstox market-data feed decoder (M4 Phase 0).

We build a FeedResponse with the generated protobuf classes, serialize it to the
same binary wire format Upstox sends, then assert our decoder recovers the ticks.
This proves the vendored .proto + generated bindings + decoder agree, offline.
"""

from app.realtime import feed_decode
from app.realtime.proto import MarketDataFeed_pb2 as pb

NIFTY = "NSE_INDEX|Nifty 50"
OPTION = "NSE_FO|44120"


def _sample_frame() -> bytes:
    resp = pb.FeedResponse(type=pb.live_feed, currentTs=1718000000000)

    # Index in ltpc mode.
    resp.feeds[NIFTY].ltpc.ltp = 23456.70
    resp.feeds[NIFTY].ltpc.cp = 23400.00

    # Option leg in option_greeks (first-level-with-greeks) mode.
    flg = resp.feeds[OPTION].firstLevelWithGreeks
    flg.ltpc.ltp = 120.50
    flg.ltpc.cp = 110.00
    flg.oi = 1_500_000
    flg.iv = 0.182
    flg.optionGreeks.delta = 0.55
    flg.optionGreeks.theta = -8.4
    flg.optionGreeks.gamma = 0.0012
    flg.optionGreeks.vega = 14.2
    flg.optionGreeks.rho = 3.1

    return resp.SerializeToString()


def test_decode_index_ltpc():
    ticks = feed_decode.decode_ticks(_sample_frame())
    assert NIFTY in ticks
    t = ticks[NIFTY]
    assert t.ltp == 23456.70
    assert t.close_price == 23400.00
    assert t.oi is None and t.iv is None and t.greeks is None  # index has no greeks


def test_decode_option_with_greeks():
    ticks = feed_decode.decode_ticks(_sample_frame())
    t = ticks[OPTION]
    assert t.ltp == 120.50
    assert t.iv == 0.182
    assert t.oi == 1_500_000
    assert t.greeks is not None
    assert t.greeks["delta"] == 0.55
    assert t.greeks["vega"] == 14.2


def test_decode_full_feed_market_ff():
    """`full` mode wraps LTPC inside fullFeed.marketFF — decoder must reach it."""
    resp = pb.FeedResponse(type=pb.live_feed)
    mff = resp.feeds[OPTION].fullFeed.marketFF
    mff.ltpc.ltp = 99.9
    mff.oi = 42_000
    mff.iv = 0.21
    ticks = feed_decode.decode_ticks(resp.SerializeToString())
    assert ticks[OPTION].ltp == 99.9
    assert ticks[OPTION].oi == 42_000
    assert ticks[OPTION].iv == 0.21


def test_empty_frame_yields_no_ticks():
    assert feed_decode.decode_ticks(pb.FeedResponse(type=pb.live_feed).SerializeToString()) == {}
