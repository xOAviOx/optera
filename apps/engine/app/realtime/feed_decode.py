"""Decode Upstox market-data feed frames (protobuf) into plain ticks.

The feed sends binary `FeedResponse` messages: a map of instrument_key -> Feed,
where each Feed is a oneof across subscription modes (ltpc / full / option_greeks).
We normalize all of them down to a single `Tick` carrying at least the LTP, plus
OI / IV / Greeks when the mode provides them.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.realtime.proto import MarketDataFeed_pb2 as pb


@dataclass(frozen=True)
class Tick:
    instrument_key: str
    ltp: float
    close_price: float | None = None
    oi: float | None = None
    iv: float | None = None  # decimal (0.18 == 18%), as supplied by Upstox
    greeks: dict[str, float] | None = None  # Upstox-supplied delta/theta/gamma/vega/rho


def parse(raw: bytes) -> pb.FeedResponse:
    resp = pb.FeedResponse()
    resp.ParseFromString(raw)
    return resp


def _ltpc_of(feed: pb.Feed) -> pb.LTPC | None:
    """Pull the LTPC sub-message regardless of which feed mode is set."""
    which = feed.WhichOneof("FeedUnion")
    if which == "ltpc":
        return feed.ltpc
    if which == "firstLevelWithGreeks":
        return feed.firstLevelWithGreeks.ltpc
    if which == "fullFeed":
        ff = feed.fullFeed
        sub = ff.WhichOneof("FullFeedUnion")
        if sub == "marketFF":
            return ff.marketFF.ltpc
        if sub == "indexFF":
            return ff.indexFF.ltpc
    return None


def _greeks_of(g: pb.OptionGreeks) -> dict[str, float] | None:
    vals = {
        "delta": g.delta,
        "theta": g.theta,
        "gamma": g.gamma,
        "vega": g.vega,
        "rho": g.rho,
    }
    return vals if any(v != 0.0 for v in vals.values()) else None


def _nonzero(x: float) -> float | None:
    # Proto3 scalars default to 0.0 when unset; treat 0 OI/IV as "absent".
    return x if x else None


def extract_ticks(resp: pb.FeedResponse) -> dict[str, Tick]:
    """Map instrument_key -> Tick for every feed in the frame that carries an LTP."""
    ticks: dict[str, Tick] = {}
    for key, feed in resp.feeds.items():
        ltpc = _ltpc_of(feed)
        if ltpc is None:
            continue

        oi = iv = None
        greeks = None
        which = feed.WhichOneof("FeedUnion")
        if which == "firstLevelWithGreeks":
            flg = feed.firstLevelWithGreeks
            oi, iv = _nonzero(flg.oi), _nonzero(flg.iv)
            greeks = _greeks_of(flg.optionGreeks)
        elif which == "fullFeed" and feed.fullFeed.WhichOneof("FullFeedUnion") == "marketFF":
            mff = feed.fullFeed.marketFF
            oi, iv = _nonzero(mff.oi), _nonzero(mff.iv)
            greeks = _greeks_of(mff.optionGreeks)

        ticks[key] = Tick(
            instrument_key=key,
            ltp=ltpc.ltp,
            close_price=_nonzero(ltpc.cp),
            oi=oi,
            iv=iv,
            greeks=greeks,
        )
    return ticks


def decode_ticks(raw: bytes) -> dict[str, Tick]:
    """Convenience: bytes -> {instrument_key: Tick}."""
    return extract_ticks(parse(raw))
