"use client";

import { Bell, BellOff, Check, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Disclaimer } from "@optera/ui";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ackAlert,
  checkNow,
  createRule,
  deleteRule,
  listAlerts,
  listRules,
  METRIC_LABELS,
  MigrationNeeded,
  OPERATOR_LABELS,
  updateRule,
  type AlertCheckResult,
  type AlertEvent,
  type AlertMetric,
  type AlertOperator,
  type AlertRule,
} from "@/lib/alerts";
import { formatRupees } from "@/lib/utils";

const METRICS = Object.keys(METRIC_LABELS) as AlertMetric[];
const OPERATORS = Object.keys(OPERATOR_LABELS) as AlertOperator[];

function fmtMetric(metric: AlertMetric, value: number | null): string {
  if (value === null || value === undefined) return "—";
  if (metric === "margin_utilization_pct") return `${value.toFixed(1)}%`;
  return formatRupees(value);
}

const inputCls =
  "h-9 w-full rounded-md border border-border bg-background px-3 text-sm " +
  "focus:outline-none focus:ring-1 focus:ring-ring";

export default function AlertsPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [check, setCheck] = useState<AlertCheckResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [migration, setMigration] = useState(false);

  // New-rule form
  const [name, setName] = useState("");
  const [metric, setMetric] = useState<AlertMetric>("total_pnl");
  const [operator, setOperator] = useState<AlertOperator>("lt");
  const [threshold, setThreshold] = useState("");
  const [cooldown, setCooldown] = useState(60);

  const load = useCallback(async () => {
    try {
      const [r, a] = await Promise.all([listRules(), listAlerts()]);
      setRules(r);
      setAlerts(a);
      setError(null);
    } catch (e) {
      if (e instanceof MigrationNeeded) setMigration(true);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onCheckNow = async () => {
    setChecking(true);
    try {
      const result = await checkNow();
      setCheck(result);
      if (result.fired.length > 0) await load();
      setError(null);
    } catch (e) {
      if (e instanceof MigrationNeeded) setMigration(true);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  };

  const onCreate = async () => {
    const value = Number(threshold);
    if (!name.trim() || Number.isNaN(value)) {
      setError("Rule needs a name and a numeric threshold.");
      return;
    }
    try {
      const rule = await createRule({
        name: name.trim(),
        metric,
        operator,
        threshold: value,
        cooldown_minutes: cooldown,
      });
      setRules((prev) => [rule, ...prev]);
      setName("");
      setThreshold("");
      setError(null);
    } catch (e) {
      if (e instanceof MigrationNeeded) setMigration(true);
      else setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onToggle = async (rule: AlertRule) => {
    try {
      const updated = await updateRule(rule.id, { enabled: !rule.enabled });
      setRules((prev) => prev.map((r) => (r.id === rule.id ? updated : r)));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onDelete = async (rule: AlertRule) => {
    try {
      await deleteRule(rule.id);
      setRules((prev) => prev.filter((r) => r.id !== rule.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onAck = async (alert: AlertEvent) => {
    try {
      const updated = await ackAlert(alert.id);
      setAlerts((prev) => prev.map((a) => (a.id === alert.id ? updated : a)));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (migration) {
    return (
      <main className="container py-8">
        <Card>
          <CardHeader>
            <CardTitle>Alerts — one-time setup needed</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Run <code className="rounded bg-secondary px-1">supabase/migrations/0005_alerts.sql</code>{" "}
            in the Supabase SQL editor, then reload this page.
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="container space-y-6 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
          <p className="text-sm text-muted-foreground">
            Set your own risk thresholds — Optera watches your book and tells you when they’re
            crossed. Education only, never advice.
          </p>
        </div>
        <Button onClick={onCheckNow} disabled={checking}>
          <RefreshCw className={`mr-1.5 h-4 w-4 ${checking ? "animate-spin" : ""}`} />
          Check now
        </Button>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {check && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Current risk snapshot{" "}
              <span className="text-xs font-normal text-muted-foreground">
                ({check.checked_rules} rule{check.checked_rules === 1 ? "" : "s"} checked
                {check.fired.length > 0 ? `, ${check.fired.length} fired` : ", none fired"})
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {METRICS.map((m) => (
                <div key={m} className="rounded-md border border-border p-2.5">
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                    {METRIC_LABELS[m]}
                  </p>
                  <p className="mt-1 text-sm font-medium tabular-nums">
                    {fmtMetric(m, check.snapshot[m])}
                  </p>
                </div>
              ))}
            </div>
            {check.snapshot.skipped_underlyings.length > 0 && (
              <p className="mt-2 text-xs text-muted-foreground">
                Live spot unavailable for {check.snapshot.skipped_underlyings.join(", ")} — Greek
                metrics exclude those legs.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ── Rules ── */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Alert rules</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2 rounded-md border border-border p-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <input
                  className={inputCls}
                  placeholder="Rule name (e.g. Theta guard)"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <select
                  className={inputCls}
                  value={metric}
                  onChange={(e) => setMetric(e.target.value as AlertMetric)}
                >
                  {METRICS.map((m) => (
                    <option key={m} value={m}>
                      {METRIC_LABELS[m]}
                    </option>
                  ))}
                </select>
                <select
                  className={inputCls}
                  value={operator}
                  onChange={(e) => setOperator(e.target.value as AlertOperator)}
                >
                  {OPERATORS.map((o) => (
                    <option key={o} value={o}>
                      {OPERATOR_LABELS[o]}
                    </option>
                  ))}
                </select>
                <input
                  className={inputCls}
                  type="number"
                  placeholder="Threshold (e.g. -2000)"
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                />
              </div>
              <div className="flex items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  Cooldown
                  <select
                    className="h-8 rounded-md border border-border bg-background px-2 text-xs"
                    value={cooldown}
                    onChange={(e) => setCooldown(Number(e.target.value))}
                  >
                    <option value={15}>15 min</option>
                    <option value={60}>1 hour</option>
                    <option value={240}>4 hours</option>
                    <option value={1440}>1 day</option>
                  </select>
                </label>
                <Button size="sm" onClick={onCreate}>
                  <Plus className="mr-1 h-4 w-4" /> Add rule
                </Button>
              </div>
            </div>

            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : rules.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No rules yet. Example: “Portfolio P&L goes below -2,000” or “Margin utilization
                goes above 80”.
              </p>
            ) : (
              <ul className="space-y-2">
                {rules.map((rule) => (
                  <li
                    key={rule.id}
                    className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {rule.name}
                        {!rule.enabled && (
                          <span className="ml-2 rounded bg-secondary px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
                            paused
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {METRIC_LABELS[rule.metric]} {OPERATOR_LABELS[rule.operator]}{" "}
                        {rule.metric === "margin_utilization_pct"
                          ? `${rule.threshold}%`
                          : formatRupees(rule.threshold)}
                        {" · "}cooldown {rule.cooldown_minutes} min
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onToggle(rule)}
                        title={rule.enabled ? "Pause rule" : "Resume rule"}
                      >
                        {rule.enabled ? (
                          <Bell className="h-4 w-4" />
                        ) : (
                          <BellOff className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDelete(rule)}
                        title="Delete rule"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* ── Alert feed ── */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent alerts</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : alerts.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nothing fired yet. The monitor checks your book automatically during market hours
                (and continuously in demo mode).
              </p>
            ) : (
              <ul className="space-y-2">
                {alerts.map((alert) => (
                  <li
                    key={alert.id}
                    className={`rounded-md border px-3 py-2 ${
                      alert.acknowledged
                        ? "border-border opacity-60"
                        : "border-amber-500/40 bg-amber-500/5"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm">{alert.message}</p>
                      {!alert.acknowledged && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="shrink-0"
                          onClick={() => onAck(alert)}
                          title="Acknowledge"
                        >
                          <Check className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {alert.rule_name} · observed{" "}
                      {fmtMetric(alert.metric, alert.observed)} vs limit{" "}
                      {fmtMetric(alert.metric, alert.threshold)}
                      {alert.created_at
                        ? ` · ${new Date(alert.created_at).toLocaleString("en-IN", {
                            timeZone: "Asia/Kolkata",
                            dateStyle: "medium",
                            timeStyle: "short",
                          })} IST`
                        : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Disclaimer />
    </main>
  );
}
