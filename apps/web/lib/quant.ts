/**
 * Client for the engine's quant endpoints (M3 — payoff / scenario / POP).
 *
 * These endpoints are unauthenticated and need no broker, so the Risk workbench
 * calls them straight from the browser. Types mirror the engine Pydantic models
 * on the wire (snake_case) — NOT the camelCase shapes in @optera/types.
 */
import { ENGINE_URL } from "./utils";

export type OptionType = "CE" | "PE";
export type Side = "BUY" | "SELL";
export type DeltaDirection = "bullish" | "bearish" | "neutral";

/** Wire shape of app.models.Leg. */
export interface WireLeg {
  symbol: string;
  option_type: OptionType | null;
  strike: number | null;
  expiry: string | null; // ISO date
  side: Side;
  lots: number;
  lot_size: number;
  entry_price: number | null; // ignored by the quant core, sent for completeness
  iv: number | null; // decimal, e.g. 0.14 == 14%
}

export interface PayoffResponse {
  spots: number[];
  pnl_expiry: number[];
  pnl_t0: number[];
  breakevens: number[];
  max_profit: number | null;
  max_loss: number | null;
}

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
  delta_direction: DeltaDirection;
}

export interface ScenarioResponse {
  pnl_delta: number;
  per_leg: Array<Record<string, unknown>>;
  new_greeks: PortfolioGreeks;
}

export interface PopResponse {
  probability_of_profit: number | null;
  mode: string;
}

async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${ENGINE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
    signal,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Engine returned ${res.status}`);
  }
  return (await res.json()) as T;
}

export interface PayoffParams {
  legs: WireLeg[];
  spot: number;
  spot_range_pct?: number;
  steps?: number;
  iv?: number | null;
  days_to_expiry?: number | null;
}

export function computePayoff(p: PayoffParams, signal?: AbortSignal): Promise<PayoffResponse> {
  return postJson<PayoffResponse>("/payoff", p, signal);
}

export interface ScenarioParams {
  legs: WireLeg[];
  spot: number;
  spot_move_pct?: number;
  iv_change_pts?: number;
  days_elapsed?: number;
}

export function computeScenario(p: ScenarioParams, signal?: AbortSignal): Promise<ScenarioResponse> {
  return postJson<ScenarioResponse>("/scenario", p, signal);
}

export interface PopParams {
  legs: WireLeg[];
  spot: number;
  atm_iv: number;
  days_to_expiry?: number | null;
  mode?: "lognormal" | "monte_carlo";
  n_paths?: number;
}

export function computePop(p: PopParams, signal?: AbortSignal): Promise<PopResponse> {
  return postJson<PopResponse>("/pop", p, signal);
}

/** A leg as edited in the UI (premium/expiry are derived, not entered). */
export interface UiLeg {
  id: string;
  optionType: OptionType;
  side: Side;
  strike: number;
  lots: number;
  lotSize: number;
}

/** Local-date ISO string `days` ahead of today (local, to match the engine host). */
export function expiryFromDte(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + Math.max(0, Math.round(days)));
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Convert UI legs to wire legs, stamping a shared IV (decimal) and a derived
 * expiry on each. Both are embedded per-leg because /scenario reads IV/expiry
 * only from the legs (not the request body).
 */
export function toWireLegs(legs: UiLeg[], ivPct: number, dte: number): WireLeg[] {
  const expiry = expiryFromDte(dte);
  const iv = ivPct / 100;
  return legs.map((l, i) => ({
    symbol: `LEG${i + 1}`,
    option_type: l.optionType,
    strike: l.strike,
    expiry,
    side: l.side,
    lots: l.lots,
    lot_size: l.lotSize,
    entry_price: null,
    iv,
  }));
}
