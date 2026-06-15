/**
 * Client for the paper-trading simulator (/sim/*).
 *
 * Account mutations are authenticated (Supabase Bearer token, verified by the
 * engine, which prices fills server-side). The chain is pure simulated market
 * data, so it needs no auth. Hypothetical/paper only — no real orders, no advice.
 */
import { createClient } from "./supabase/client";
import { ENGINE_URL } from "./utils";

export type OptionType = "CE" | "PE";
export type Side = "BUY" | "SELL";

export interface Greeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface PortfolioGreeks {
  net: Greeks;
  delta_rupees_per_pct: number;
  theta_rupees_per_day: number;
  vega_rupees_per_point: number;
  delta_direction: "bullish" | "bearish" | "neutral";
}

export interface MarkedPosition {
  id: string;
  symbol: string;
  option_type: OptionType;
  strike: number;
  side: Side;
  lots: number;
  lot_size: number;
  entry_tick: number;
  entry_price: number;
  expiry_tick: number;
  dte_days: number;
  mark_price: number;
  unrealized_pnl: number;
  value: number;
}

export interface SimMarketQuote {
  symbol: string;
  spot: number;
  iv: number;
}

export interface SimAccount {
  capital: number;
  cash: number;
  realized_pnl: number;
  unrealized_pnl: number;
  equity: number;
  total_pnl: number;
  margin_used: number;
  available: number;
  clock_tick: number;
  positions: MarkedPosition[];
  greeks: PortfolioGreeks;
  market: SimMarketQuote[];
}

export interface ChainStrike {
  strike: number;
  ce: { ltp: number };
  pe: { ltp: number };
}

export interface SimChain {
  symbol: string;
  spot: number;
  iv: number;
  dte_days: number;
  expiry_tick: number;
  lot_size: number;
  strikes: ChainStrike[];
}

/** Thrown when the paper_* tables aren't migrated yet (engine returns 503). */
export class MigrationNeeded extends Error {}

async function authed(path: string, init?: RequestInit): Promise<SimAccount> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) throw new Error("Please sign in again — your session expired.");

  const res = await fetch(`${ENGINE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    if (res.status === 503 && detail.toLowerCase().includes("migration")) {
      throw new MigrationNeeded(detail);
    }
    throw new Error(detail || `Engine returned ${res.status}`);
  }
  return (await res.json()) as SimAccount;
}

export function getAccount(tick: number): Promise<SimAccount> {
  return authed(`/sim/account?tick=${tick}`);
}

export interface OrderParams {
  symbol: string;
  option_type: OptionType;
  strike: number;
  lots: number;
  side: Side;
  dte_days: number;
  tick: number;
}

export function placeOrder(p: OrderParams): Promise<SimAccount> {
  return authed("/sim/order", { method: "POST", body: JSON.stringify(p) });
}

export function closePosition(positionId: string, tick: number): Promise<SimAccount> {
  return authed("/sim/close", {
    method: "POST",
    body: JSON.stringify({ position_id: positionId, tick }),
  });
}

export function resetAccount(): Promise<SimAccount> {
  return authed("/sim/reset", { method: "POST" });
}

export async function getChain(
  symbol: string,
  tick: number,
  dteDays: number,
): Promise<SimChain> {
  const res = await fetch(
    `${ENGINE_URL}/sim/chain/${symbol}?tick=${tick}&dte_days=${dteDays}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(`Chain request failed (${res.status})`);
  return (await res.json()) as SimChain;
}

/** NSE trading minutes per day; ticks since open → a readable "Day N, HH:MM". */
const TICKS_PER_DAY = 375;
export function clockLabel(tick: number): string {
  const day = Math.floor(tick / TICKS_PER_DAY) + 1;
  const minOfDay = tick % TICKS_PER_DAY;
  const total = 9 * 60 + 15 + minOfDay; // session opens 09:15
  const hh = String(Math.floor(total / 60)).padStart(2, "0");
  const mm = String(total % 60).padStart(2, "0");
  return `Day ${day} · ${hh}:${mm}`;
}
