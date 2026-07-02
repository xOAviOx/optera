/**
 * Client for the trade journal (M9).
 *
 * Trades are user-owned and evaluated server-side (stats + descriptive AI
 * review), so calls go through the engine with the Supabase access token.
 * Education-only: the review describes a trade, it never advises.
 */
import { createClient } from "./supabase/client";
import { type WireLeg } from "./quant";
import { ENGINE_URL } from "./utils";

export interface JournalTrade {
  id: string;
  opened_at: string | null;
  closed_at: string | null;
  legs: WireLeg[];
  realized_pnl: number | null;
  ai_review: string | null;
  underlying: string | null;
}

export interface JournalStats {
  closed_trades: number;
  open_trades: number;
  total_realized_pnl: number;
  win_rate: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  profit_factor: number | null;
  best: number | null;
  worst: number | null;
  pnl_by_underlying: Record<string, number>;
  equity_curve: number[];
}

export interface JournalResponse {
  trades: JournalTrade[];
  stats: JournalStats;
}

export interface NewTrade {
  legs?: WireLeg[];
  opened_at?: string | null;
  closed_at?: string | null;
  realized_pnl?: number | null;
}

/** Thrown when the journal table isn't migrated yet (engine returns 503). */
export class MigrationNeeded extends Error {}

async function authed<T>(path: string, init?: RequestInit): Promise<T> {
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
  // DELETE returns a small ack; callers that don't need it can ignore.
  return (await res.json().catch(() => ({}))) as T;
}

export function getJournal(): Promise<JournalResponse> {
  return authed<JournalResponse>("/journal");
}

export function createTrade(payload: NewTrade): Promise<JournalTrade> {
  return authed<JournalTrade>("/journal", {
    method: "POST",
    body: JSON.stringify({ legs: [], ...payload }),
  });
}

export function reviewTrade(id: string): Promise<JournalTrade> {
  return authed<JournalTrade>(`/journal/${id}/review`, { method: "POST" });
}

export async function deleteTrade(id: string): Promise<void> {
  await authed<{ deleted: boolean }>(`/journal/${id}`, { method: "DELETE" });
}
