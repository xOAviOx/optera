"use client";

import { Briefcase, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Disclaimer } from "@optera/ui";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getMargin, getPositions, type Margin, type Position } from "@/lib/positions";
import { formatRupees } from "@/lib/utils";

export default function PositionsPage() {
  const [positions, setPositions] = useState<Position[] | null>(null);
  const [margin, setMargin] = useState<Margin | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, m] = await Promise.all([getPositions(), getMargin()]);
      setPositions(p);
      setMargin(m);
    } catch (e) {
      setError((e as Error).message || "Could not load positions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const totalPnl = positions?.reduce((sum, p) => sum + (p.pnl ?? 0), 0) ?? 0;

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Briefcase className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-semibold tracking-tight">Positions</h1>
            <span className="rounded bg-secondary px-2 py-0.5 font-mono text-xs text-primary">
              M4
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Read-only view of your F&amp;O book and margin. No orders, ever.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={`mr-1.5 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </header>

      <div className="grid gap-3 sm:grid-cols-3">
        <SummaryCard
          label="Day P&L"
          value={formatRupees(totalPnl)}
          tone={totalPnl > 0 ? "profit" : totalPnl < 0 ? "loss" : "neutral"}
        />
        <SummaryCard label="Margin used" value={margin ? formatRupees(margin.used) : "—"} />
        <SummaryCard
          label="Margin available"
          value={margin ? formatRupees(margin.available) : "—"}
        />
      </div>

      {error && (
        <Card>
          <CardContent className="py-4 text-sm text-[hsl(var(--loss))]">⚠ {error}</CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm">Open positions</CardTitle>
        </CardHeader>
        <CardContent className="py-0 pb-4">
          {loading && !positions ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Loading positions…</p>
          ) : positions && positions.length > 0 ? (
            <PositionsTable positions={positions} />
          ) : (
            !error && (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No open positions.
              </p>
            )
          )}
        </CardContent>
      </Card>

      <Disclaimer />
    </div>
  );
}

function SummaryCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "profit" | "loss" | "neutral";
}) {
  const color =
    tone === "profit"
      ? "text-[hsl(var(--profit))]"
      : tone === "loss"
        ? "text-[hsl(var(--loss))]"
        : "text-foreground";
  return (
    <Card>
      <CardContent className="space-y-1 py-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className={`text-xl font-semibold tabular-nums ${color}`}>{value}</p>
      </CardContent>
    </Card>
  );
}

function kind(p: Position): string {
  if (p.option_type) return p.option_type;
  return p.instrument_token.startsWith("NSE_EQ") ? "EQ" : "FUT";
}

function PositionsTable({ positions }: { positions: Position[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th className="py-2 pr-3 font-medium">Instrument</th>
            <th className="py-2 pr-3 font-medium">Type</th>
            <th className="py-2 pr-3 text-right font-medium">Qty</th>
            <th className="py-2 pr-3 text-right font-medium">Avg</th>
            <th className="py-2 pr-3 text-right font-medium">LTP</th>
            <th className="py-2 text-right font-medium">P&L</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const lots = p.lot_size ? p.quantity / p.lot_size : p.quantity;
            const pnl = p.pnl ?? 0;
            const pnlColor =
              pnl > 0
                ? "text-[hsl(var(--profit))]"
                : pnl < 0
                  ? "text-[hsl(var(--loss))]"
                  : "text-muted-foreground";
            return (
              <tr key={p.instrument_token} className="border-b border-border/50 last:border-0">
                <td className="py-2 pr-3">
                  <span className="font-medium">{p.tradingsymbol}</span>
                  {p.expiry && (
                    <span className="ml-2 text-xs text-muted-foreground">{p.expiry}</span>
                  )}
                </td>
                <td className="py-2 pr-3">
                  <span className="rounded bg-secondary px-1.5 py-0.5 font-mono text-xs">
                    {kind(p)}
                  </span>
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {p.quantity > 0 ? "+" : ""}
                  {p.quantity}
                  <span className="ml-1 text-xs text-muted-foreground">
                    ({lots > 0 ? "+" : ""}
                    {lots} lot)
                  </span>
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {formatRupees(p.average_price, { decimals: 2 })}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {p.last_price != null ? formatRupees(p.last_price, { decimals: 2 }) : "—"}
                </td>
                <td className={`py-2 text-right font-medium tabular-nums ${pnlColor}`}>
                  {formatRupees(pnl)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
