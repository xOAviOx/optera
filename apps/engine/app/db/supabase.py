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
