/**
 * Client for the read-only portfolio endpoints (GET /positions, /margin).
 *
 * Runs in the browser: pulls the Supabase access token from the client session
 * and sends it as a Bearer token (the engine verifies it). When the engine runs
 * with BROKER=mock these return a synthetic demo book; otherwise they reflect
 * the connected broker. Read-only — no orders, no advice.
 */
import { createClient } from "./supabase/client";
import { ENGINE_URL } from "./utils";

export interface Position {
  instrument_token: string;
  tradingsymbol: string;
  name: string | null;
  option_type: string | null; // CE / PE / null(=FUT/EQ)
  strike: number | null;
  expiry: string | null;
  quantity: number; // signed: long > 0, short < 0
  lot_size: number;
  average_price: number;
  last_price: number | null;
  pnl: number | null;
}

export interface Margin {
  used: number;
  available: number;
  equity: Record<string, number> | null;
  commodity: Record<string, number> | null;
}

async function authedGet<T>(path: string): Promise<T> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) throw new Error("Please sign in again — your session expired.");

  const res = await fetch(`${ENGINE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    if (res.status === 409) {
      throw new Error(
        "No broker connected. Enable demo mode (BROKER=mock in the engine) or connect Upstox.",
      );
    }
    if (res.status === 503) throw new Error("Broker/storage not configured on the server yet.");
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Engine returned ${res.status}`);
  }
  return (await res.json()) as T;
}

export function getPositions(): Promise<Position[]> {
  return authedGet<Position[]>("/positions");
}

export function getMargin(): Promise<Margin> {
  return authedGet<Margin>("/margin");
}
