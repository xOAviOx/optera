"""Monitoring + alerts orchestration (M8).

Builds a risk snapshot from the user's live positions (works in demo/mock mode
with zero credentials), evaluates the user's alert rules against it, phrases any
breach via the alert LLM (deterministic fallback), and persists the alert event.
A background loop re-checks every user with enabled rules during market hours.

Education/analytics only: alerts describe risk, they never advise.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx

from app.ai import alert_writer
from app.brokers.base import BrokerAdapter, NormalizedPosition
from app.brokers.factory import get_broker_adapter
from app.config import get_settings
from app.db import supabase
from app.models import (
    AlertEvent,
    AlertRule,
    Leg,
    OptionType,
    RiskSnapshot,
    ScenarioRequest,
    Side,
)
from app.services import positions_service, quant_service, stream_service

logger = logging.getLogger("optera.alerts")

_IST = timezone(timedelta(hours=5, minutes=30))
_STRESS_MOVES_PCT = (-5.0, -3.0, 3.0, 5.0)
DEFAULT_ATM_IV = 0.14  # used when a chain lookup yields no usable IV


class AlertError(RuntimeError):
    """User-facing alert failure (bad rule, etc.)."""


class AlertTablesMissing(RuntimeError):
    """alert_rules/alerts tables are absent or still the pre-M8 placeholder
    shape from migration 0001 — migration 0005 not applied."""

    def __init__(self) -> None:
        super().__init__(
            "Alert tables missing or outdated. Apply supabase/migrations/0005_alerts.sql "
            "in the Supabase SQL editor, then retry."
        )


def _map_missing_tables(exc: httpx.HTTPStatusError) -> Exception:
    # 404/PGRST205 = table absent; PGRST204 = unknown column, i.e. the old
    # 0001 placeholder alert_rules is still in place.
    if exc.response.status_code == 404:
        return AlertTablesMissing()
    body = exc.response.text or ""
    if "PGRST204" in body or "PGRST205" in body:
        return AlertTablesMissing()
    return exc


# ── rule evaluation (pure, unit-tested) ───────────────────────────────────────
def rule_breached(observed: float, operator: str, threshold: float) -> bool:
    if operator == "gt":
        return observed > threshold
    if operator == "lt":
        return observed < threshold
    if operator == "abs_gt":
        return abs(observed) > abs(threshold)
    raise AlertError(f"Unknown operator {operator!r}")


def in_cooldown(
    last_triggered_at: str | None, cooldown_minutes: int, now: datetime | None = None
) -> bool:
    if not last_triggered_at:
        return False
    try:
        last = datetime.fromisoformat(last_triggered_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    now = now or datetime.now(UTC)
    return now < last + timedelta(minutes=cooldown_minutes)


def is_market_hours(now: datetime | None = None) -> bool:
    """NSE hours: Mon–Fri 09:15–15:30 IST."""
    now = (now or datetime.now(_IST)).astimezone(_IST)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 15 <= minutes <= 15 * 60 + 30


# ── risk snapshot ─────────────────────────────────────────────────────────────
def _to_leg(pos: NormalizedPosition, iv: float) -> Leg:
    lots = max(1, round(abs(pos.quantity) / max(pos.lot_size, 1)))
    return Leg(
        symbol=pos.name or pos.tradingsymbol,
        option_type=OptionType(pos.option_type),
        strike=pos.strike or 0.0,
        expiry=pos.expiry,
        side=Side.BUY if pos.quantity > 0 else Side.SELL,
        lots=lots,
        lot_size=pos.lot_size,
        entry_price=pos.average_price,
        iv=iv,
    )


async def _spot_and_iv(
    adapter: BrokerAdapter, user_id: str, symbol: str
) -> tuple[float, float] | None:
    """Underlying spot + ATM IV via the adapter's chain. None when unavailable."""
    token = ""
    if adapter.requires_auth:
        try:
            token = await stream_service.resolve_feed_token(user_id)
        except Exception:  # noqa: BLE001 — no analytics token => no live spot
            return None
    try:
        chain = await adapter.get_option_chain(token, symbol, "")
    except Exception:  # noqa: BLE001 — chain down => degrade, don't fail the check
        return None
    spot = chain.get("spot")
    if not spot:
        return None
    iv = DEFAULT_ATM_IV
    strikes = chain.get("strikes") or []
    if strikes:
        atm = min(strikes, key=lambda s: abs(s.get("strike", 0) - spot))
        iv = (atm.get("ce") or {}).get("iv") or (atm.get("pe") or {}).get("iv") or iv
    return float(spot), float(iv)


async def build_snapshot(user_id: str) -> RiskSnapshot:
    """Current risk metrics for the user's live book. Metrics degrade to None
    individually — a missing spot must not take down P&L/margin alerts."""
    adapter = get_broker_adapter()
    positions = await positions_service.list_positions(user_id)

    snapshot = RiskSnapshot(
        total_pnl=round(sum(p.pnl or 0.0 for p in positions), 2) if positions else 0.0
    )

    try:
        margin = await positions_service.get_margin(user_id)
        total = margin.used + margin.available
        if total > 0:
            snapshot.margin_utilization_pct = round(margin.used / total * 100.0, 2)
    except Exception:  # noqa: BLE001 — margin API down => that metric is just absent
        pass

    options = [p for p in positions if p.option_type in ("CE", "PE") and p.strike]
    snapshot.option_legs = len(options)
    if not options:
        return snapshot

    by_underlying: dict[str, list[NormalizedPosition]] = {}
    for pos in options:
        by_underlying.setdefault(pos.name or pos.tradingsymbol, []).append(pos)
    snapshot.underlyings = sorted(by_underlying)

    delta_r = theta_r = vega_r = 0.0
    stress: dict[float, float] = dict.fromkeys(_STRESS_MOVES_PCT, 0.0)
    priced_any = False
    for symbol, group in by_underlying.items():
        market = await _spot_and_iv(adapter, user_id, symbol)
        if market is None:
            snapshot.skipped_underlyings.append(symbol)
            continue
        spot, iv = market
        legs = [_to_leg(p, iv) for p in group]
        base = quant_service.compute_scenario(ScenarioRequest(legs=legs, spot=spot))
        delta_r += base.new_greeks.delta_rupees_per_pct
        theta_r += base.new_greeks.theta_rupees_per_day
        vega_r += base.new_greeks.vega_rupees_per_point
        for move in _STRESS_MOVES_PCT:
            sc = quant_service.compute_scenario(
                ScenarioRequest(legs=legs, spot=spot, spot_move_pct=move / 100.0)
            )
            stress[move] += sc.pnl_delta
        priced_any = True

    if priced_any:
        snapshot.delta_rupees_per_pct = round(delta_r, 2)
        snapshot.theta_rupees_per_day = round(theta_r, 2)
        snapshot.vega_rupees_per_point = round(vega_r, 2)
        worst = min(stress.values())
        snapshot.stress_loss_rupees = round(abs(min(0.0, worst)), 2)
    return snapshot


# ── check + fire ──────────────────────────────────────────────────────────────
def _rule_model(row: dict[str, Any]) -> AlertRule:
    if "metric" not in row:  # row from the pre-M8 placeholder schema
        raise AlertTablesMissing()
    return AlertRule(
        id=str(row["id"]),
        name=row["name"],
        metric=row["metric"],
        operator=row["operator"],
        threshold=float(row["threshold"]),
        enabled=bool(row["enabled"]),
        cooldown_minutes=int(row["cooldown_minutes"]),
        last_triggered_at=row.get("last_triggered_at"),
        created_at=row.get("created_at"),
    )


def _event_model(row: dict[str, Any]) -> AlertEvent:
    return AlertEvent(
        id=str(row["id"]),
        rule_id=str(row["rule_id"]) if row.get("rule_id") else None,
        rule_name=row["rule_name"],
        metric=row["metric"],
        operator=row["operator"],
        threshold=float(row["threshold"]),
        observed=float(row["observed"]),
        message=row["message"],
        ai_phrased=bool(row.get("ai_phrased", False)),
        acknowledged=bool(row.get("acknowledged", False)),
        created_at=row.get("created_at"),
    )


async def check_user(user_id: str) -> tuple[RiskSnapshot, list[AlertEvent], int]:
    """Evaluate every enabled rule for the user. Returns (snapshot, fired, checked)."""
    try:
        rows = await supabase.list_alert_rules(user_id, enabled=True)
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc

    snapshot = await build_snapshot(user_id)
    fired: list[AlertEvent] = []
    for row in rows:
        rule = _rule_model(row)
        observed = getattr(snapshot, rule.metric.value, None)
        if observed is None:
            continue
        if not rule_breached(observed, rule.operator.value, rule.threshold):
            continue
        if in_cooldown(rule.last_triggered_at, rule.cooldown_minutes):
            continue

        phrased = await alert_writer.phrase_alert(
            rule.name, rule.metric.value, rule.operator.value, observed, rule.threshold
        )
        now_iso = datetime.now(UTC).isoformat()
        alert_row = await supabase.insert_alert(
            {
                "user_id": user_id,
                "rule_id": rule.id,
                "rule_name": rule.name,
                "metric": rule.metric.value,
                "operator": rule.operator.value,
                "threshold": rule.threshold,
                "observed": observed,
                "message": phrased.message,
                "ai_phrased": phrased.ai_phrased,
            }
        )
        await supabase.patch_alert_rule(user_id, rule.id, {"last_triggered_at": now_iso})
        fired.append(_event_model(alert_row))

    return snapshot, fired, len(rows)


# ── rules / alerts CRUD passthrough (user_id always verified by the caller) ───
async def list_rules(user_id: str) -> list[AlertRule]:
    try:
        return [_rule_model(r) for r in await supabase.list_alert_rules(user_id)]
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc


async def create_rule(user_id: str, fields: dict[str, Any]) -> AlertRule:
    try:
        row = await supabase.insert_alert_rule({**fields, "user_id": user_id})
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc
    return _rule_model(row)


async def update_rule(user_id: str, rule_id: str, fields: dict[str, Any]) -> AlertRule:
    if not fields:
        raise AlertError("No fields to update.")
    try:
        row = await supabase.patch_alert_rule(user_id, rule_id, fields)
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc
    if row is None:
        raise AlertError("Rule not found.")
    return _rule_model(row)


async def delete_rule(user_id: str, rule_id: str) -> None:
    try:
        await supabase.delete_alert_rule(user_id, rule_id)
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc


async def list_events(user_id: str, limit: int = 50) -> list[AlertEvent]:
    try:
        return [_event_model(r) for r in await supabase.list_alerts(user_id, limit)]
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc


async def acknowledge(user_id: str, alert_id: str) -> AlertEvent:
    try:
        row = await supabase.patch_alert(user_id, alert_id, {"acknowledged": True})
    except httpx.HTTPStatusError as exc:
        raise _map_missing_tables(exc) from exc
    if row is None:
        raise AlertError("Alert not found.")
    return _event_model(row)


# ── background monitor ────────────────────────────────────────────────────────
def _should_run_now() -> bool:
    # Demo book is synthetic and always "open"; real brokers only in market hours.
    if get_broker_adapter().requires_auth:
        return is_market_hours()
    return True


async def _run_cycle() -> None:
    if not _should_run_now():
        return
    try:
        user_ids = await supabase.list_alert_rule_user_ids()
    except supabase.SupabaseNotConfigured:
        return  # engine running without storage — nothing to monitor
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return  # migration 0005 not applied yet — silently idle
        raise
    for user_id in user_ids:
        try:
            _, fired, _ = await check_user(user_id)
            if fired:
                logger.info("alerts fired user=%s count=%d", user_id, len(fired))
        except Exception:  # noqa: BLE001 — one user must not break the sweep
            logger.warning("alert check failed user=%s", user_id, exc_info=True)


async def monitor_loop() -> None:
    """Run forever: evaluate all users' rules every interval. Started in main.py."""
    interval = max(10, get_settings().alert_check_interval_seconds)
    logger.info("alert monitor started (interval=%ss)", interval)
    while True:
        try:
            await _run_cycle()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — the loop must survive any cycle error
            logger.exception("alert monitor cycle failed")
        await asyncio.sleep(interval)


# Referenced by tests to build stress scenarios the same way the service does.
def stress_moves_pct() -> tuple[float, ...]:
    return _STRESS_MOVES_PCT


__all__ = [
    "AlertError",
    "AlertTablesMissing",
    "acknowledge",
    "build_snapshot",
    "check_user",
    "create_rule",
    "delete_rule",
    "in_cooldown",
    "is_market_hours",
    "list_events",
    "list_rules",
    "monitor_loop",
    "rule_breached",
    "update_rule",
]
