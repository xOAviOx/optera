/**
 * Client for monitoring + alerts (M8).
 *
 * Rules are user-defined thresholds on risk metrics; the engine evaluates them
 * (background monitor + on-demand check) and phrases breaches in plain Hinglish.
 * Education-only notifications — never buy/sell advice.
 */
import { createClient } from "./supabase/client";
import { ENGINE_URL } from "./utils";

export type AlertMetric =
  | "total_pnl"
  | "delta_rupees_per_pct"
  | "theta_rupees_per_day"
  | "vega_rupees_per_point"
  | "margin_utilization_pct"
  | "stress_loss_rupees";

export type AlertOperator = "gt" | "lt" | "abs_gt";

export const METRIC_LABELS: Record<AlertMetric, string> = {
  total_pnl: "Portfolio P&L (₹)",
  delta_rupees_per_pct: "Delta ₹ / 1% move",
  theta_rupees_per_day: "Theta ₹ / day",
  vega_rupees_per_point: "Vega ₹ / vol point",
  margin_utilization_pct: "Margin utilization %",
  stress_loss_rupees: "Stress loss ₹ (±3–5% move)",
};

export const OPERATOR_LABELS: Record<AlertOperator, string> = {
  gt: "goes above",
  lt: "goes below",
  abs_gt: "magnitude exceeds",
};

export interface AlertRule {
  id: string;
  name: string;
  metric: AlertMetric;
  operator: AlertOperator;
  threshold: number;
  enabled: boolean;
  cooldown_minutes: number;
  last_triggered_at: string | null;
  created_at: string | null;
}

export interface AlertEvent {
  id: string;
  rule_id: string | null;
  rule_name: string;
  metric: AlertMetric;
  operator: AlertOperator;
  threshold: number;
  observed: number;
  message: string;
  ai_phrased: boolean;
  acknowledged: boolean;
  created_at: string | null;
}

export interface RiskSnapshot {
  total_pnl: number | null;
  delta_rupees_per_pct: number | null;
  theta_rupees_per_day: number | null;
  vega_rupees_per_point: number | null;
  margin_utilization_pct: number | null;
  stress_loss_rupees: number | null;
  option_legs: number;
  underlyings: string[];
  skipped_underlyings: string[];
}

export interface AlertCheckResult {
  snapshot: RiskSnapshot;
  fired: AlertEvent[];
  checked_rules: number;
}

export interface RuleParams {
  name: string;
  metric: AlertMetric;
  operator: AlertOperator;
  threshold: number;
  enabled?: boolean;
  cooldown_minutes?: number;
}

/** Thrown when the alert tables aren't migrated yet (engine returns 503). */
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
    if (res.status === 503 && detail.toLowerCase().includes("0005_alerts")) {
      throw new MigrationNeeded(detail);
    }
    throw new Error(detail || `Engine returned ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function listRules(): Promise<AlertRule[]> {
  const data = await authed<{ rules: AlertRule[] }>("/alert-rules");
  return data.rules;
}

export function createRule(params: RuleParams): Promise<AlertRule> {
  return authed<AlertRule>("/alert-rules", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function updateRule(id: string, fields: Partial<RuleParams>): Promise<AlertRule> {
  return authed<AlertRule>(`/alert-rules/${id}`, {
    method: "PATCH",
    body: JSON.stringify(fields),
  });
}

export async function deleteRule(id: string): Promise<void> {
  await authed<{ deleted: boolean }>(`/alert-rules/${id}`, { method: "DELETE" });
}

export async function listAlerts(limit = 50): Promise<AlertEvent[]> {
  const data = await authed<{ alerts: AlertEvent[] }>(`/alerts?limit=${limit}`);
  return data.alerts;
}

export function ackAlert(id: string): Promise<AlertEvent> {
  return authed<AlertEvent>(`/alerts/${id}/ack`, { method: "POST" });
}

export function checkNow(): Promise<AlertCheckResult> {
  return authed<AlertCheckResult>("/alerts/check", { method: "POST" });
}
