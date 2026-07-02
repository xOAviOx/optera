"use client";

import { Plus, RefreshCw, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Disclaimer } from "@optera/ui";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  createTrade,
  deleteTrade,
  getJournal,
  MigrationNeeded,
  reviewTrade,
  type JournalResponse,
  type JournalStats,
  type JournalTrade,
} from "@/lib/journal";
import { toWireLegs, type WireLeg } from "@/lib/quant";
import { useStrategyStore } from "@/lib/strategy-store";
import { formatRupees } from "@/lib/utils";

const inputCls =
  "h-9 w-full rounded-md border border-border bg-background px-3 text-sm " +
  "focus:outline-none focus:ring-1 focus:ring-ring";

const money = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : formatRupees(n);

const pnlColor = (n: number | null) =>
  n === null ? "text-muted-foreground" : n > 0 ? "text-emerald-500" : n < 0 ? "text-red-500" : "";

function structureLabel(t: JournalTrade): string {
  if (!t.legs?.length) return "—";
  return t.legs
    .map((l) => {
      const side = (l.side || "").toUpperCase();
      const type = l.option_type ? ` ${l.strike ?? ""} ${l.option_type}` : "";
      return `${side} ${l.lots}x${type}`.trim();
    })
    .join(", ");
}

/** Cumulative-P&L sparkline. Pure SVG, no chart dependency. */
function EquityCurve({ points }: { points: number[] }) {
  const { path, zeroY, w, h } = useMemo(() => {
    const width = 560;
    const height = 120;
    if (points.length === 0) return { path: "", zeroY: height / 2, w: width, h: height };
    const series = [0, ...points];
    const min = Math.min(...series);
    const max = Math.max(...series);
    const span = max - min || 1;
    const x = (i: number) => (i / (series.length - 1 || 1)) * width;
    const y = (v: number) => height - ((v - min) / span) * height;
    const d = series.map((v, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`);
    return { path: d.join(" "), zeroY: y(0), w: width, h: height };
  }, [points]);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-32 w-full" preserveAspectRatio="none">
      <line x1={0} x2={w} y1={zeroY} y2={zeroY} className="stroke-border" strokeDasharray="4 4" />
      {path && <path d={path} fill="none" className="stroke-primary" strokeWidth={2} />}
    </svg>
  );
}

function StatTile({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`mt-1 text-lg font-semibold tabular-nums ${tone ?? ""}`}>{value}</p>
    </div>
  );
}

export default function JournalPage() {
  const [data, setData] = useState<JournalResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [migration, setMigration] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Add-trade form
  const [underlying, setUnderlying] = useState("NIFTY");
  const [openedAt, setOpenedAt] = useState("");
  const [closedAt, setClosedAt] = useState("");
  const [pnl, setPnl] = useState("");
  const [attach, setAttach] = useState(false);
  const [saving, setSaving] = useState(false);

  // Optional: attach the structure currently open in the Risk workbench.
  const storeLegs = useStrategyStore((s) => s.legs);
  const storeIv = useStrategyStore((s) => s.ivPct);
  const storeDte = useStrategyStore((s) => s.dte);

  const load = useCallback(async () => {
    try {
      setData(await getJournal());
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

  const buildLegs = (): WireLeg[] => {
    const sym = underlying.trim() || "NIFTY";
    if (attach && storeLegs.length) {
      return toWireLegs(storeLegs, storeIv, storeDte).map((l) => ({ ...l, symbol: sym }));
    }
    // A single underlying marker leg so the trade groups by instrument.
    return [
      {
        symbol: sym,
        option_type: null,
        strike: null,
        expiry: null,
        side: "BUY",
        lots: 1,
        lot_size: 1,
        entry_price: null,
        iv: null,
      },
    ];
  };

  const onAdd = async () => {
    setSaving(true);
    setError(null);
    try {
      await createTrade({
        legs: buildLegs(),
        opened_at: openedAt || null,
        closed_at: closedAt || null,
        realized_pnl: pnl.trim() === "" ? null : Number(pnl),
      });
      setOpenedAt("");
      setClosedAt("");
      setPnl("");
      setAttach(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const onReview = async (id: string) => {
    setBusyId(id);
    setError(null);
    try {
      await reviewTrade(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const onDelete = async (id: string) => {
    setBusyId(id);
    try {
      await deleteTrade(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const stats: JournalStats | null = data?.stats ?? null;

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">Trade Journal</h1>
          <span className="rounded bg-secondary px-2 py-0.5 font-mono text-xs text-primary">M9</span>
        </div>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Log your closed trades, track performance, and get a descriptive (non-judgmental)
          post-trade review. Analytics only — never buy/sell advice.
        </p>
      </section>

      <Disclaimer />

      {migration ? (
        <Card>
          <CardContent className="py-6 text-sm text-muted-foreground">
            The journal table isn’t set up yet. Apply{" "}
            <code className="font-mono text-primary">supabase/migrations/0001_init.sql</code> in the
            Supabase SQL editor, then reload.
          </CardContent>
        </Card>
      ) : (
        <>
          {error && (
            <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-400">
              {error}
            </div>
          )}

          {/* Stats */}
          {stats && stats.closed_trades > 0 && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <StatTile
                label="Realized P&L"
                value={money(stats.total_realized_pnl)}
                tone={pnlColor(stats.total_realized_pnl)}
              />
              <StatTile
                label="Win rate"
                value={stats.win_rate === null ? "—" : `${(stats.win_rate * 100).toFixed(0)}%`}
              />
              <StatTile
                label="Profit factor"
                value={stats.profit_factor === null ? "—" : stats.profit_factor.toFixed(2)}
              />
              <StatTile label="Avg win" value={money(stats.avg_win)} tone="text-emerald-500" />
              <StatTile label="Avg loss" value={money(stats.avg_loss)} tone="text-red-500" />
              <StatTile
                label="Closed / open"
                value={`${stats.closed_trades} / ${stats.open_trades}`}
              />
            </div>
          )}

          {/* Equity curve */}
          {stats && stats.equity_curve.length > 1 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Equity curve</CardTitle>
              </CardHeader>
              <CardContent>
                <EquityCurve points={stats.equity_curve} />
              </CardContent>
            </Card>
          )}

          {/* Add trade */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Log a trade</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">Underlying</span>
                  <input
                    className={inputCls}
                    value={underlying}
                    onChange={(e) => setUnderlying(e.target.value)}
                    placeholder="NIFTY"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">Opened</span>
                  <input
                    type="date"
                    className={inputCls}
                    value={openedAt}
                    onChange={(e) => setOpenedAt(e.target.value)}
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">Closed</span>
                  <input
                    type="date"
                    className={inputCls}
                    value={closedAt}
                    onChange={(e) => setClosedAt(e.target.value)}
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">Realized P&L (₹)</span>
                  <input
                    type="number"
                    className={inputCls}
                    value={pnl}
                    onChange={(e) => setPnl(e.target.value)}
                    placeholder="blank = still open"
                  />
                </label>
              </div>
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={attach}
                    disabled={!storeLegs.length}
                    onChange={(e) => setAttach(e.target.checked)}
                  />
                  Attach current Risk workbench structure
                  {storeLegs.length ? ` (${storeLegs.length} legs)` : " (none open)"}
                </label>
                <Button size="sm" onClick={onAdd} disabled={saving}>
                  <Plus className="mr-1 h-4 w-4" />
                  {saving ? "Saving…" : "Add trade"}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Trades */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Trades</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {loading ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : !data?.trades.length ? (
                <p className="text-sm text-muted-foreground">
                  No trades logged yet. Add one above to start tracking your performance.
                </p>
              ) : (
                data.trades.map((t) => (
                  <div key={t.id} className="rounded-lg border border-border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="space-y-0.5">
                        <p className="text-sm font-medium">
                          {t.underlying ?? "—"}
                          <span className="ml-2 font-normal text-muted-foreground">
                            {structureLabel(t)}
                          </span>
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {t.opened_at?.slice(0, 10) ?? "—"} → {t.closed_at?.slice(0, 10) ?? "open"}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <span
                          className={`text-sm font-semibold tabular-nums ${pnlColor(t.realized_pnl)}`}
                        >
                          {t.realized_pnl === null ? "Open" : money(t.realized_pnl)}
                        </span>
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={busyId === t.id}
                          onClick={() => onReview(t.id)}
                        >
                          <Sparkles className="mr-1 h-3.5 w-3.5" />
                          {t.ai_review ? "Re-review" : "AI review"}
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          disabled={busyId === t.id}
                          onClick={() => onDelete(t.id)}
                          aria-label="Delete trade"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    {t.ai_review && (
                      <p className="mt-2 rounded-md bg-secondary/50 p-2 text-sm text-muted-foreground">
                        {t.ai_review}
                      </p>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button size="sm" variant="ghost" onClick={() => void load()}>
              <RefreshCw className="mr-1 h-4 w-4" /> Refresh
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
