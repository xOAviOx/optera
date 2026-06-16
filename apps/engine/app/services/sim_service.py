"""Paper-trading simulator orchestration.

Ties the deterministic market + accounting (pure) to the user's persisted paper
account (Supabase, service-role). Fills are priced server-side at the requested
tick so the client can't fabricate prices. Hypothetical/paper only — no real
orders, no advice.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.db import supabase
from app.sim import accounting, market
from app.sim.accounting import PaperPosition

STARTING_CAPITAL = 500_000.0


class PaperTablesMissing(RuntimeError):
    """The paper_* tables don't exist yet — migration 0004 hasn't been applied."""


class SimError(RuntimeError):
    """A bad simulator request (unknown symbol, position not open, etc.)."""


def _is_missing_tables(exc: httpx.HTTPStatusError) -> bool:
    if exc.response.status_code not in (400, 404):
        return False
    body = exc.response.text.lower()
    return "paper_" in body and ("does not exist" in body or "could not find the table" in body)


async def _guard(coro):
    """Await `coro`, translating a missing-table error into PaperTablesMissing."""
    try:
        return await coro
    except httpx.HTTPStatusError as exc:
        if _is_missing_tables(exc):
            raise PaperTablesMissing(
                "Paper-sim tables missing — run migration 0004_paper_sim.sql in Supabase."
            ) from exc
        raise


def _require_symbol(symbol: str) -> market.SymbolSpec:
    try:
        return market.SYMBOLS[symbol.upper()]
    except KeyError as exc:
        raise SimError(f"Unknown symbol {symbol!r}; trade {sorted(market.SYMBOLS)}.") from exc


async def _get_or_create_account(user_id: str) -> dict:
    account = await _guard(supabase.get_paper_account(user_id))
    if account is not None:
        return account
    try:
        return await _guard(supabase.create_paper_account(user_id, STARTING_CAPITAL))
    except httpx.HTTPStatusError as exc:
        # 409 = another concurrent request already created it (e.g. React
        # strict-mode double-fires the initial load). Re-fetch instead of failing.
        if exc.response.status_code == 409:
            existing = await _guard(supabase.get_paper_account(user_id))
            if existing is not None:
                return existing
        raise


async def _positions(user_id: str) -> list[PaperPosition]:
    rows = await _guard(supabase.list_paper_positions(user_id, status="open"))
    return [PaperPosition.from_row(r) for r in rows]


async def _snapshot(user_id: str, tick: int, account: dict) -> dict:
    return accounting.account_snapshot(account, await _positions(user_id), tick)


async def account_state(user_id: str, tick: int) -> dict:
    """Marked snapshot at `tick`; auto-creates the account and advances the clock."""
    account = await _get_or_create_account(user_id)
    tick = max(tick, int(account.get("clock_tick", 0)))
    if tick != int(account.get("clock_tick", 0)):
        account = await _guard(supabase.patch_paper_account(user_id, {"clock_tick": tick}))
    return await _snapshot(user_id, tick, account)


async def place_order(
    user_id: str,
    *,
    symbol: str,
    option_type: str,
    strike: float,
    lots: int,
    side: str,
    dte_days: float,
    tick: int,
) -> dict:
    spec = _require_symbol(symbol)
    account = await _get_or_create_account(user_id)

    expiry_tick = market.expiry_tick_for(tick, dte_days)
    entry_price = accounting.quote(spec.name, option_type, strike, expiry_tick, tick)
    sign = 1 if side.upper() == "BUY" else -1
    signed_qty = sign * lots * spec.lot_size
    cash_delta = accounting.open_cash_delta(entry_price, signed_qty)

    await _guard(
        supabase.insert_paper_position(
            {
                "user_id": user_id,
                "symbol": spec.name,
                "option_type": option_type,
                "strike": strike,
                "side": side.upper(),
                "lots": lots,
                "lot_size": spec.lot_size,
                "entry_tick": tick,
                "entry_spot": market.spot(spec.name, tick),
                "entry_price": entry_price,
                "expiry_tick": expiry_tick,
                "status": "open",
            }
        )
    )
    new_cash = round(float(account["cash"]) + cash_delta, 2)
    account = await _guard(
        supabase.patch_paper_account(user_id, {"cash": new_cash, "clock_tick": tick})
    )
    return await _snapshot(user_id, tick, account)


async def close_position(user_id: str, position_id: str, tick: int) -> dict:
    row = await _guard(supabase.get_paper_position(user_id, position_id))
    if row is None:
        raise SimError("Position not found.")
    if row.get("status") != "open":
        raise SimError("Position is already closed.")

    pos = PaperPosition.from_row(row)
    exit_price = accounting.mark_price(pos, tick)
    realized = accounting.realized_on_close(pos, exit_price)
    cash_delta = accounting.close_cash_delta(pos, exit_price)

    await _guard(
        supabase.patch_paper_position(
            user_id,
            position_id,
            {
                "status": "closed",
                "exit_tick": tick,
                "exit_spot": market.spot(pos.symbol, tick),
                "exit_price": exit_price,
                "realized_pnl": realized,
                "closed_at": datetime.now(UTC).isoformat(),
            },
        )
    )
    account = await _get_or_create_account(user_id)
    account = await _guard(
        supabase.patch_paper_account(
            user_id,
            {
                "cash": round(float(account["cash"]) + cash_delta, 2),
                "realized_pnl": round(float(account["realized_pnl"]) + realized, 2),
                "clock_tick": tick,
            },
        )
    )
    return await _snapshot(user_id, tick, account)


async def reset_account(user_id: str) -> dict:
    await _get_or_create_account(user_id)
    await _guard(supabase.delete_paper_positions(user_id))
    account = await _guard(
        supabase.patch_paper_account(
            user_id,
            {"cash": STARTING_CAPITAL, "realized_pnl": 0, "clock_tick": 0},
        )
    )
    return await _snapshot(user_id, 0, account)


def chain(symbol: str, tick: int, dte_days: float, depth: int = 6) -> dict:
    """Synthetic option chain for the order ticket (pure — no account needed)."""
    spec = _require_symbol(symbol)
    expiry_tick = market.expiry_tick_for(tick, dte_days)
    strikes = [
        {
            "strike": k,
            "ce": {"ltp": accounting.quote(spec.name, "CE", k, expiry_tick, tick)},
            "pe": {"ltp": accounting.quote(spec.name, "PE", k, expiry_tick, tick)},
        }
        for k in market.strike_ladder(spec.name, tick, depth)
    ]
    return {
        "symbol": spec.name,
        "spot": market.spot(spec.name, tick),
        "iv": market.iv(spec.name, tick),
        "dte_days": dte_days,
        "expiry_tick": expiry_tick,
        "lot_size": spec.lot_size,
        "strikes": strikes,
    }
