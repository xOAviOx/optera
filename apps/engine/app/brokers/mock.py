"""Mock broker adapter — synthetic demo book (no credentials).

Lets the whole product be driven end-to-end without connecting a real broker:
positions, holdings, margin and an option chain are generated from a fixed,
internally-consistent NIFTY/BANKNIFTY book. Activate with `BROKER=mock`.

Education/analytics only — these are hypothetical numbers, never live or advice.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.brokers.base import BrokerAdapter, NormalizedPosition

# Plausible mid-2026 index levels the demo book is priced around.
NIFTY_SPOT = 24_500.0
BANKNIFTY_SPOT = 52_000.0
NIFTY_LOT = 75
BANKNIFTY_LOT = 30


def _next_weekly_expiry(today: date | None = None) -> str:
    """Next Thursday (NSE weekly expiry), ISO date. Always at least 1 day out."""
    today = today or date.today()
    days_ahead = (3 - today.weekday()) % 7  # Monday=0 ... Thursday=3
    if days_ahead == 0:
        days_ahead = 7
    return (today + timedelta(days=days_ahead)).isoformat()


# A classic retail short-premium book: a NIFTY iron-condor-ish structure with
# protective wings, plus a short BANKNIFTY call. (name, opt, strike, lot, qty,
# avg, ltp) — qty is signed (short < 0), already in units (lots * lot_size).
_OPTION_LEGS = [
    ("NIFTY", "CE", 25_000.0, NIFTY_LOT, -NIFTY_LOT, 85.0, 62.0),
    ("NIFTY", "PE", 24_000.0, NIFTY_LOT, -NIFTY_LOT, 78.0, 95.0),
    ("NIFTY", "CE", 25_500.0, NIFTY_LOT, NIFTY_LOT, 30.0, 18.0),
    ("NIFTY", "PE", 23_500.0, NIFTY_LOT, NIFTY_LOT, 25.0, 32.0),
    ("BANKNIFTY", "CE", 52_000.0, BANKNIFTY_LOT, -BANKNIFTY_LOT, 240.0, 205.0),
]

# Longer-term equity holdings (no option fields, lot size 1).
# (symbol, name, qty, avg, ltp)
_HOLDINGS = [
    ("RELIANCE", "Reliance Industries", 50, 2_850.0, 2_960.0),
    ("INFY", "Infosys", 100, 1_450.0, 1_422.0),
]


def _option_position(
    name: str, opt: str, strike: float, lot: int, qty: int, avg: float, ltp: float
) -> NormalizedPosition:
    return NormalizedPosition(
        instrument_token=f"NSE_FO|{name}{int(strike)}{opt}",
        tradingsymbol=f"{name} {int(strike)} {opt}",
        name=name,
        option_type=opt,
        strike=strike,
        expiry=_next_weekly_expiry(),
        quantity=qty,
        lot_size=lot,
        average_price=avg,
        last_price=ltp,
        pnl=round((ltp - avg) * qty, 2),  # signed qty makes shorts profit when ltp falls
    )


def _equity_position(
    symbol: str, name: str, qty: int, avg: float, ltp: float
) -> NormalizedPosition:
    return NormalizedPosition(
        instrument_token=f"NSE_EQ|{symbol}",
        tradingsymbol=symbol,
        name=name,
        option_type=None,
        strike=None,
        expiry=None,
        quantity=qty,
        lot_size=1,
        average_price=avg,
        last_price=ltp,
        pnl=round((ltp - avg) * qty, 2),
    )


class MockBrokerAdapter(BrokerAdapter):
    """Serves a fixed synthetic book. Ignores the (absent) access token."""

    broker_name = "mock"
    requires_auth = False

    async def get_positions(self, access_token: str) -> list[NormalizedPosition]:
        return [_option_position(*leg) for leg in _OPTION_LEGS]

    async def get_holdings(self, access_token: str) -> list[NormalizedPosition]:
        return [_equity_position(*h) for h in _HOLDINGS]

    async def get_margin(self, access_token: str) -> dict:
        equity = {"used_margin": 185_000.0, "available_margin": 315_000.0}
        return {
            "used": equity["used_margin"],
            "available": equity["available_margin"],
            "equity": equity,
            "commodity": None,
        }

    async def get_option_chain(self, analytics_token: str, symbol: str, expiry: str) -> dict:
        """A small synthetic chain (±5 strikes) with IV/Greeks/OI per strike."""
        spot = BANKNIFTY_SPOT if symbol.upper().startswith("BANK") else NIFTY_SPOT
        step = 100.0 if symbol.upper().startswith("BANK") else 50.0
        atm = round(spot / step) * step
        strikes = []
        for i in range(-5, 6):
            strike = atm + i * step
            moneyness = strike - spot
            ce_ltp = max(round(spot * 0.012 - moneyness * 0.45, 2), 1.0)
            pe_ltp = max(round(spot * 0.012 + moneyness * 0.45, 2), 1.0)
            strikes.append(
                {
                    "strike": strike,
                    "ce": {"ltp": ce_ltp, "iv": 0.14, "oi": 120_000 - abs(i) * 8_000},
                    "pe": {"ltp": pe_ltp, "iv": 0.15, "oi": 110_000 - abs(i) * 7_000},
                }
            )
        return {
            "symbol": symbol.upper(),
            "expiry": expiry or _next_weekly_expiry(),
            "spot": spot,
            "strikes": strikes,
        }
