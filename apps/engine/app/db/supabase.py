"""Thin async Supabase (PostgREST) client for the engine.

Uses the service-role key, so it bypasses RLS — callers MUST scope every query to
a verified user_id themselves. Only the engine ever holds the service-role key.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


class SupabaseNotConfigured(RuntimeError):
    pass


def _base_and_headers() -> tuple[str, dict[str, str]]:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise SupabaseNotConfigured("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    base = f"{s.supabase_url}/rest/v1"
    headers = {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    return base, headers


async def upsert_broker_connection(
    *,
    user_id: str,
    broker: str,
    api_key: str | None = None,
    access_token_enc: str | None = None,
    analytics_token_enc: str | None = None,
    public_token: str | None = None,
    status: str = "active",
    expires_at: str | None = None,
) -> dict[str, Any]:
    """Insert or update the user's connection for `broker` (unique on user_id+broker).

    Only non-None fields are written, so storing the analytics token later doesn't
    wipe the access token (and vice-versa).
    """
    base, headers = _base_and_headers()
    row: dict[str, Any] = {"user_id": user_id, "broker": broker, "status": status}
    for key, val in (
        ("api_key", api_key),
        ("access_token_enc", access_token_enc),
        ("analytics_token_enc", analytics_token_enc),
        ("public_token", public_token),
        ("expires_at", expires_at),
    ):
        if val is not None:
            row[key] = val

    headers = {**headers, "Prefer": "resolution=merge-duplicates,return=representation"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base}/broker_connections",
            params={"on_conflict": "user_id,broker"},
            headers=headers,
            json=[row],
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else {}


async def get_broker_connection(user_id: str, broker: str = "upstox") -> dict[str, Any] | None:
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/broker_connections",
            params={
                "user_id": f"eq.{user_id}",
                "broker": f"eq.{broker}",
                "select": "*",
                "limit": "1",
            },
            headers=headers,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else None


# ── Paper-trading simulator (M-sim) ───────────────────────────────────────────
# The engine owns these writes (service role) so fills are priced server-side and
# can't be tampered by the client; every query is scoped to the verified user_id.
async def get_paper_account(user_id: str) -> dict[str, Any] | None:
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/paper_accounts",
            params={"user_id": f"eq.{user_id}", "select": "*", "limit": "1"},
            headers=headers,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else None


async def create_paper_account(user_id: str, capital: float) -> dict[str, Any]:
    base, headers = _base_and_headers()
    headers = {**headers, "Prefer": "return=representation"}
    row = {
        "user_id": user_id,
        "capital": capital,
        "cash": capital,
        "realized_pnl": 0,
        "clock_tick": 0,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{base}/paper_accounts", headers=headers, json=[row])
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else row


async def patch_paper_account(user_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    base, headers = _base_and_headers()
    headers = {**headers, "Prefer": "return=representation"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.patch(
            f"{base}/paper_accounts",
            params={"user_id": f"eq.{user_id}"},
            headers=headers,
            json=fields,
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else {}


async def list_paper_positions(
    user_id: str, status: str | None = None
) -> list[dict[str, Any]]:
    base, headers = _base_and_headers()
    params = {"user_id": f"eq.{user_id}", "select": "*", "order": "opened_at.asc"}
    if status:
        params["status"] = f"eq.{status}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{base}/paper_positions", params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def get_paper_position(user_id: str, position_id: str) -> dict[str, Any] | None:
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/paper_positions",
            params={
                "user_id": f"eq.{user_id}",
                "id": f"eq.{position_id}",
                "select": "*",
                "limit": "1",
            },
            headers=headers,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else None


async def insert_paper_position(row: dict[str, Any]) -> dict[str, Any]:
    base, headers = _base_and_headers()
    headers = {**headers, "Prefer": "return=representation"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{base}/paper_positions", headers=headers, json=[row])
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else row


async def patch_paper_position(
    user_id: str, position_id: str, fields: dict[str, Any]
) -> dict[str, Any]:
    base, headers = _base_and_headers()
    headers = {**headers, "Prefer": "return=representation"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.patch(
            f"{base}/paper_positions",
            params={"user_id": f"eq.{user_id}", "id": f"eq.{position_id}"},
            headers=headers,
            json=fields,
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else {}


async def delete_paper_positions(user_id: str) -> None:
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{base}/paper_positions",
            params={"user_id": f"eq.{user_id}"},
            headers=headers,
        )
        resp.raise_for_status()


# ── Monitoring + alerts (M8) ──────────────────────────────────────────────────
# Rules are user-owned config; alert events are written by the engine after it
# evaluates a rule (service role). Every query is scoped to the verified user_id.
async def list_alert_rules(user_id: str, enabled: bool | None = None) -> list[dict[str, Any]]:
    base, headers = _base_and_headers()
    params = {"user_id": f"eq.{user_id}", "select": "*", "order": "created_at.desc"}
    if enabled is not None:
        params["enabled"] = f"eq.{str(enabled).lower()}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{base}/alert_rules", params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def insert_alert_rule(row: dict[str, Any]) -> dict[str, Any]:
    base, headers = _base_and_headers()
    headers = {**headers, "Prefer": "return=representation"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{base}/alert_rules", headers=headers, json=[row])
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else row


async def patch_alert_rule(
    user_id: str, rule_id: str, fields: dict[str, Any]
) -> dict[str, Any] | None:
    base, headers = _base_and_headers()
    headers = {**headers, "Prefer": "return=representation"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.patch(
            f"{base}/alert_rules",
            params={"user_id": f"eq.{user_id}", "id": f"eq.{rule_id}"},
            headers=headers,
            json=fields,
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else None


async def delete_alert_rule(user_id: str, rule_id: str) -> None:
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{base}/alert_rules",
            params={"user_id": f"eq.{user_id}", "id": f"eq.{rule_id}"},
            headers=headers,
        )
        resp.raise_for_status()


async def list_alert_rule_user_ids() -> list[str]:
    """Distinct user_ids that have at least one enabled rule (monitor fan-out)."""
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/alert_rules",
            params={"select": "user_id", "enabled": "eq.true"},
            headers=headers,
        )
        resp.raise_for_status()
        return sorted({row["user_id"] for row in resp.json()})


async def list_alerts(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/alerts",
            params={
                "user_id": f"eq.{user_id}",
                "select": "*",
                "order": "created_at.desc",
                "limit": str(max(1, min(limit, 200))),
            },
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


async def insert_alert(row: dict[str, Any]) -> dict[str, Any]:
    base, headers = _base_and_headers()
    headers = {**headers, "Prefer": "return=representation"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{base}/alerts", headers=headers, json=[row])
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else row


async def patch_alert(
    user_id: str, alert_id: str, fields: dict[str, Any]
) -> dict[str, Any] | None:
    base, headers = _base_and_headers()
    headers = {**headers, "Prefer": "return=representation"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.patch(
            f"{base}/alerts",
            params={"user_id": f"eq.{user_id}", "id": f"eq.{alert_id}"},
            headers=headers,
            json=fields,
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else None


# ── Trade journal (M9) ────────────────────────────────────────────────────────
# journal_trades (migration 0001): id, user_id, opened_at, closed_at, legs_jsonb,
# realized_pnl, ai_review. All writes are service-role and scoped to user_id.
_JOURNAL_COLUMNS = "id,opened_at,closed_at,legs_jsonb,realized_pnl,ai_review"


async def list_journal_trades(user_id: str) -> list[dict[str, Any]]:
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/journal_trades",
            params={
                "user_id": f"eq.{user_id}",
                "select": _JOURNAL_COLUMNS,
                # No created_at column; newest closed first, then newest opened.
                "order": "closed_at.desc.nullslast,opened_at.desc.nullslast",
            },
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


async def get_journal_trade(user_id: str, trade_id: str) -> dict[str, Any] | None:
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/journal_trades",
            params={
                "user_id": f"eq.{user_id}",
                "id": f"eq.{trade_id}",
                "select": _JOURNAL_COLUMNS,
            },
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else None


async def insert_journal_trade(row: dict[str, Any]) -> dict[str, Any]:
    base, headers = _base_and_headers()
    headers = {**headers, "Prefer": "return=representation"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{base}/journal_trades", headers=headers, json=[row])
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else row


async def patch_journal_trade(
    user_id: str, trade_id: str, fields: dict[str, Any]
) -> dict[str, Any] | None:
    base, headers = _base_and_headers()
    headers = {**headers, "Prefer": "return=representation"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.patch(
            f"{base}/journal_trades",
            params={"user_id": f"eq.{user_id}", "id": f"eq.{trade_id}"},
            headers=headers,
            json=fields,
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else None


async def delete_journal_trade(user_id: str, trade_id: str) -> None:
    base, headers = _base_and_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{base}/journal_trades",
            params={"user_id": f"eq.{user_id}", "id": f"eq.{trade_id}"},
            headers=headers,
        )
        resp.raise_for_status()
