"""Paper-account marking & P&L accounting (pure — no DB, no HTTP).

Marks open positions against the deterministic market with the existing
Black–Scholes core, and books the cash flow of opening/closing. Cash convention
(signed_qty = ±lots·lot_size, + for BUY): opening moves cash by −price·signed_qty
(a long debits premium, a short credits it); closing reverses it, so a round trip
nets exactly the realized P&L = (exit − entry)·signed_qty.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.quant.portfolio import leg_price, leg_unit_greeks
from app.quant.types import Greeks, Leg, Market
from app.sim import market

# Rough SPAN-style reserve on short option legs (buying-power display only).
SHORT_MARGIN_PCT = 0.12
_DIRECTION_RATIO = 0.15  # matches quant.portfolio's neutral band


@dataclass(frozen=True)
class PaperPosition:
    id: str
    symbol: str
    option_type: str  # "CE" | "PE"
    strike: float
    side: str  # "BUY" | "SELL"
    lots: int
    lot_size: int
    entry_tick: int
    entry_spot: float
    entry_price: float
    expiry_tick: int
    status: str = "open"

    @classmethod
    def from_row(cls, row: dict) -> PaperPosition:
        return cls(
            id=str(row["id"]),
            symbol=row["symbol"],
            option_type=row["option_type"],
            strike=float(row["strike"]),
            side=row["side"],
            lots=int(row["lots"]),
            lot_size=int(row["lot_size"]),
            entry_tick=int(row["entry_tick"]),
            entry_spot=float(row["entry_spot"]),
            entry_price=float(row["entry_price"]),
            expiry_tick=int(row["expiry_tick"]),
            status=row.get("status", "open"),
        )

    @property
    def sign(self) -> int:
        return 1 if self.side.upper() == "BUY" else -1

    @property
    def signed_qty(self) -> int:
        return self.sign * self.lots * self.lot_size

    @property
    def qty_abs(self) -> int:
        return self.lots * self.lot_size


def _market(symbol: str, tick: int) -> Market:
    return Market(spot=market.spot(symbol, tick), r=get_settings().risk_free_rate)


def _quant_leg(pos: PaperPosition, tick: int) -> Leg:
    return Leg(
        option_type=pos.option_type,
        strike=pos.strike,
        t=market.years_to_expiry(tick, pos.expiry_tick),
        sigma=market.iv(pos.symbol, tick),
        side=pos.side,
        lots=pos.lots,
        lot_size=pos.lot_size,
    )


def mark_price(pos: PaperPosition, tick: int) -> float:
    """Theoretical premium of one contract of `pos` at `tick`."""
    return round(leg_price(_quant_leg(pos, tick), _market(pos.symbol, tick)), 2)


def quote(symbol: str, option_type: str, strike: float, expiry_tick: int, tick: int) -> float:
    """Premium for a prospective order leg (used for fills and the chain)."""
    leg = Leg(
        option_type=option_type,
        strike=strike,
        t=market.years_to_expiry(tick, expiry_tick),
        sigma=market.iv(symbol, tick),
        side="BUY",
        lots=1,
        lot_size=1,
    )
    return round(leg_price(leg, _market(symbol, tick)), 2)


def open_cash_delta(price: float, signed_qty: int) -> float:
    """Cash change when opening: −price·signed_qty (long debits, short credits)."""
    return round(-price * signed_qty, 2)


def realized_on_close(pos: PaperPosition, exit_price: float) -> float:
    return round((exit_price - pos.entry_price) * pos.signed_qty, 2)


def close_cash_delta(pos: PaperPosition, exit_price: float) -> float:
    """Cash change when closing: +exit·signed_qty (reverses the open)."""
    return round(exit_price * pos.signed_qty, 2)


def marked_position(pos: PaperPosition, tick: int) -> dict:
    mark = mark_price(pos, tick)
    return {
        "id": pos.id,
        "symbol": pos.symbol,
        "option_type": pos.option_type,
        "strike": pos.strike,
        "side": pos.side,
        "lots": pos.lots,
        "lot_size": pos.lot_size,
        "entry_tick": pos.entry_tick,
        "entry_price": pos.entry_price,
        "expiry_tick": pos.expiry_tick,
        "dte_days": round(max(pos.expiry_tick - tick, 0) / market.TICKS_PER_DAY, 2),
        "mark_price": mark,
        "unrealized_pnl": round((mark - pos.entry_price) * pos.signed_qty, 2),
        "value": round(mark * pos.signed_qty, 2),
    }


def _portfolio_greeks(positions: list[PaperPosition], tick: int) -> dict:
    """Net Greeks across (possibly multi-underlying) open legs.

    Aggregates per-leg unit Greeks scaled by signed qty, using each leg's own
    underlying spot for the rupee conversions (so NIFTY/BANKNIFTY mix correctly).
    """
    net = Greeks(0.0, 0.0, 0.0, 0.0, 0.0)
    delta_rupees = 0.0
    net_delta_qty = 0.0
    gross_delta_qty = 0.0
    for pos in positions:
        mkt = _market(pos.symbol, tick)
        g = leg_unit_greeks(_quant_leg(pos, tick), mkt).scaled(pos.signed_qty)
        net = Greeks(
            delta=net.delta + g.delta,
            gamma=net.gamma + g.gamma,
            theta=net.theta + g.theta,
            vega=net.vega + g.vega,
            rho=net.rho + g.rho,
        )
        delta_rupees += g.delta * mkt.spot * 0.01
        net_delta_qty += g.delta
        gross_delta_qty += abs(g.delta)

    ratio = net_delta_qty / gross_delta_qty if gross_delta_qty > 1e-9 else 0.0
    if ratio > _DIRECTION_RATIO:
        direction = "bullish"
    elif ratio < -_DIRECTION_RATIO:
        direction = "bearish"
    else:
        direction = "neutral"
    return {
        "net": {
            "delta": round(net.delta, 4),
            "gamma": round(net.gamma, 6),
            "theta": round(net.theta, 2),
            "vega": round(net.vega, 2),
            "rho": round(net.rho, 2),
        },
        "delta_rupees_per_pct": round(delta_rupees, 2),
        "theta_rupees_per_day": round(net.theta, 2),
        "vega_rupees_per_point": round(net.vega, 2),
        "delta_direction": direction,
    }


def account_snapshot(account: dict, positions: list[PaperPosition], tick: int) -> dict:
    """Full marked snapshot of the paper account at `tick`."""
    open_positions = [p for p in positions if p.status == "open"]
    marked = [marked_position(p, tick) for p in open_positions]

    cash = float(account.get("cash", 0.0))
    capital = float(account.get("capital", cash))
    realized = float(account.get("realized_pnl", 0.0))
    unrealized = round(sum(m["unrealized_pnl"] for m in marked), 2)
    position_value = round(sum(m["value"] for m in marked), 2)
    equity = round(cash + position_value, 2)

    margin_used = 0.0
    for pos in open_positions:
        if pos.sign < 0:  # short option leg reserves buying power
            margin_used += SHORT_MARGIN_PCT * market.spot(pos.symbol, tick) * pos.qty_abs
    margin_used = round(margin_used, 2)

    return {
        "capital": round(capital, 2),
        "cash": round(cash, 2),
        "realized_pnl": round(realized, 2),
        "unrealized_pnl": unrealized,
        "equity": equity,
        "total_pnl": round(equity - capital, 2),
        "margin_used": margin_used,
        "available": round(equity - margin_used, 2),
        "clock_tick": tick,
        "positions": marked,
        "greeks": _portfolio_greeks(open_positions, tick),
        "market": [
            {"symbol": s, "spot": market.spot(s, tick), "iv": market.iv(s, tick)}
            for s in market.SYMBOLS
        ],
    }
