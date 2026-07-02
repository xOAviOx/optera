"""Trade journal orchestration (M9).

Lists a user's logged trades, computes performance stats (pure, unit-tested), and
generates a *descriptive* post-trade review via the LLM gateway with a
deterministic fallback. Education/analytics only: the review describes what
happened and what the risk looked like — it never judges or advises.

All DB access is service-role and scoped to the verified user_id.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.ai import advice_filter
from app.ai.alert_writer import fmt_inr
from app.ai.gateway import chat_providers
from app.ai.providers.base import LLMError, LLMNotConfigured
from app.db import supabase
from app.models import JournalResponse, JournalStats, JournalTrade, JournalTradeCreate

logger = logging.getLogger("optera.journal")

_LEG_PLACEHOLDER = re.compile(r"^LEG\d+$", re.IGNORECASE)


class JournalError(RuntimeError):
    """User-facing journal failure (missing trade, etc.)."""


class JournalTablesMissing(RuntimeError):
    """journal_trades table absent — migration 0001 not applied."""

    def __init__(self) -> None:
        super().__init__(
            "Journal table missing. Apply supabase/migrations/0001_init.sql in the "
            "Supabase SQL editor, then retry."
        )


def _map_missing_tables(exc: httpx.HTTPStatusError) -> Exception:
    if exc.response.status_code == 404:
        return JournalTablesMissing()
    body = exc.response.text or ""
    if "PGRST204" in body or "PGRST205" in body:
        return JournalTablesMissing()
    return exc


# ── derivations + pure stats (unit-tested) ────────────────────────────────────
def underlying_of(legs: list[dict[str, Any]] | None) -> str | None:
    """First real instrument symbol in the legs, ignoring UI placeholders (LEG1…)."""
    for leg in legs or []:
        sym = str(leg.get("symbol") or "").strip()
        if sym and not _LEG_PLACEHOLDER.match(sym):
            return sym
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_stats(trades: list[dict[str, Any]]) -> JournalStats:
    """Performance stats over closed trades (realized_pnl present). Pure."""
    closed = [t for t in trades if t.get("realized_pnl") is not None]
    open_count = len(trades) - len(closed)
    if not closed:
        return JournalStats(closed_trades=0, open_trades=open_count)

    pnls = [float(t["realized_pnl"]) for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)  # positive magnitude

    by_underlying: dict[str, float] = {}
    for t in closed:
        key = t.get("underlying") or "—"
        by_underlying[key] = by_underlying.get(key, 0.0) + float(t["realized_pnl"])

    # Equity curve: cumulative realized P&L in close-time order (unknown close last).
    ordered = sorted(closed, key=lambda t: (t.get("closed_at") is None, t.get("closed_at") or ""))
    equity: list[float] = []
    running = 0.0
    for t in ordered:
        running += float(t["realized_pnl"])
        equity.append(round(running, 2))

    return JournalStats(
        closed_trades=len(closed),
        open_trades=open_count,
        total_realized_pnl=round(sum(pnls), 2),
        win_rate=len(wins) / len(closed),
        avg_win=(gross_win / len(wins)) if wins else None,
        avg_loss=(sum(losses) / len(losses)) if losses else None,
        profit_factor=(gross_win / gross_loss) if gross_loss > 0 else None,
        best=max(pnls),
        worst=min(pnls),
        pnl_by_underlying={k: round(v, 2) for k, v in by_underlying.items()},
        equity_curve=equity,
    )


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    legs = row.get("legs_jsonb") or []
    return {
        "id": row["id"],
        "opened_at": row.get("opened_at"),
        "closed_at": row.get("closed_at"),
        "legs": legs,
        "realized_pnl": _as_float(row.get("realized_pnl")),
        "ai_review": row.get("ai_review"),
        "underlying": underlying_of(legs),
    }


# ── orchestration (async, DB-backed) ──────────────────────────────────────────
async def list_trades_with_stats(user_id: str) -> JournalResponse:
    try:
        rows = await supabase.list_journal_trades(user_id)
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc
    normalized = [_normalize(r) for r in rows]
    stats = compute_stats(normalized)
    return JournalResponse(
        trades=[JournalTrade(**t) for t in normalized],
        stats=stats,
    )


async def create_trade(user_id: str, payload: JournalTradeCreate) -> JournalTrade:
    row = {
        "user_id": user_id,
        "opened_at": payload.opened_at,
        "closed_at": payload.closed_at,
        "legs_jsonb": [leg.model_dump(mode="json") for leg in payload.legs],
        "realized_pnl": payload.realized_pnl,
    }
    try:
        created = await supabase.insert_journal_trade(row)
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc
    return JournalTrade(**_normalize(created))


async def delete_trade(user_id: str, trade_id: str) -> None:
    try:
        await supabase.delete_journal_trade(user_id, trade_id)
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc


# ── AI post-trade review (descriptive, never advice) ──────────────────────────
SYSTEM_PROMPT = (
    "You write ONE short, descriptive post-trade review (max 3 sentences) in friendly "
    "Hinglish (Hindi-English mix) for Optera, an options risk-analytics education tool for "
    "Indian retail F&O traders. You are given a trade the user already closed (or is still "
    "holding): its structure, realized P&L, and dates. Describe factually what the structure "
    "was and how it turned out. Use ₹ and Indian conventions (lakh/crore).\n\n"
    "HARD RULES — non-negotiable:\n"
    "1. EDUCATION ONLY. NEVER judge the user or suggest any action — no buy/sell/exit/hold/"
    "adjust/hedge, no 'next time', no 'aapko ... karna chahiye', no predictions.\n"
    "2. Be neutral and supportive; describe, don't grade.\n"
    "3. Output ONLY the review text — no preamble, no quotes, no markdown."
)


def _summarize_legs(legs: list[dict[str, Any]]) -> str:
    if not legs:
        return "no legs recorded"
    parts: list[str] = []
    for leg in legs:
        side = str(leg.get("side") or "").upper() or "?"
        lots = leg.get("lots") or "?"
        sym = str(leg.get("symbol") or "").strip()
        strike = leg.get("strike")
        opt = leg.get("option_type")
        bits = [f"{side} {lots}x"]
        if sym and not _LEG_PLACEHOLDER.match(sym):
            bits.append(sym)
        if strike is not None and opt:
            bits.append(f"{strike:g} {opt}")
        elif strike is not None:
            bits.append(f"{strike:g}")
        parts.append(" ".join(bits))
    return ", ".join(parts)


def _outcome(pnl: float | None) -> str:
    if pnl is None:
        return "open"
    if pnl > 0:
        return "profit"
    if pnl < 0:
        return "loss"
    return "breakeven"


def template_review(trade: dict[str, Any]) -> str:
    """Deterministic fallback review (no LLM). Descriptive only."""
    summary = _summarize_legs(trade.get("legs") or [])
    pnl = trade.get("realized_pnl")
    if pnl is None:
        return (
            f"Yeh trade abhi open hai. Structure: {summary}. "
            "(Descriptive review — koi advice nahi.)"
        )
    outcome = {"profit": "profit mein", "loss": "loss mein", "breakeven": "breakeven pe"}[
        _outcome(pnl)
    ]
    return (
        f"Yeh trade {outcome} close hua, realized P&L {fmt_inr(pnl)}. "
        f"Structure: {summary}. (Descriptive review — koi advice nahi.)"
    )


async def review_trade(user_id: str, trade_id: str) -> JournalTrade:
    try:
        row = await supabase.get_journal_trade(user_id, trade_id)
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc
    if not row:
        raise JournalError("Trade not found.")

    trade = _normalize(row)
    review = template_review(trade)
    ai_used = False

    payload = json.dumps(
        {
            "structure": _summarize_legs(trade["legs"]),
            "underlying": trade["underlying"],
            "outcome": _outcome(trade["realized_pnl"]),
            "realized_pnl": trade["realized_pnl"],
            "realized_pnl_formatted": (
                fmt_inr(trade["realized_pnl"]) if trade["realized_pnl"] is not None else None
            ),
            "opened_at": trade["opened_at"],
            "closed_at": trade["closed_at"],
        }
    )
    try:
        providers = chat_providers()
    except LLMNotConfigured:
        providers = []
    for provider in providers:
        try:
            resp = await provider.complete(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": payload}],
                tools=[],
            )
        except LLMError:
            continue  # failover
        text = (resp.text or "").strip()
        if not text:
            continue
        safe, flagged = advice_filter.screen(text)
        if flagged:
            break  # model tried to advise — keep the deterministic template
        review, ai_used = safe, True
        break

    try:
        updated = await supabase.patch_journal_trade(
            user_id, trade_id, {"ai_review": review}
        )
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc
    logger.info("journal review for %s ai_used=%s", trade_id, ai_used)
    return JournalTrade(**_normalize(updated or row))
