"use client";

import { Pause, Play, RotateCcw, Zap } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Disclaimer } from "@optera/ui";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  clockLabel,
  closePosition,
  getAccount,
  getChain,
  MigrationNeeded,
  placeOrder,
  resetAccount,
  type ChainStrike,
  type OptionType,
  type SimAccount,
  type SimChain,
  type Side,
} from "@/lib/sim";
import { formatRupees } from "@/lib/utils";

const SYMBOLS = ["NIFTY", "BANKNIFTY"];

export default function SimulatorPage() {
  const [account, setAccount] = useState<SimAccount | null>(null);
  const [chain, setChain] = useState<SimChain | null>(null);
  const [tick, setTick] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [symbol, setSymbol] = useState("NIFTY");
  const [dte, setDte] = useState(7);
  const [lots, setLots] = useState(1);
  const [strike, setStrike] = useState<number | null>(null);
  const [optionType, setOptionType] = useState<OptionType>("CE");
  const [error, setError] = useState<string | null>(null);
  const [migration, setMigration] = useState(false);
  const [busy, setBusy] = useState(false);

  const tickRef = useRef(tick);
  tickRef.current = tick;

  const handleError = useCallback((e: unknown) => {
    if (e instanceof MigrationNeeded) setMigration(true);
    else setError((e as Error).message);
  }, []);

  // Initial load — resume from the account's persisted clock.
  useEffect(() => {
    getAccount(0)
      .then((acc) => {
        setAccount(acc);
        setTick(acc.clock_tick);
      })
      .catch(handleError);
  }, [handleError]);

  // Playback: advance the sim clock by `speed` ticks every second while playing.
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setTick((t) => t + speed), 1000);
    return () => clearInterval(id);
  }, [playing, speed]);

  // Re-mark the account each tick while playing (server prices at that tick).
  useEffect(() => {
    if (!playing || migration) return;
    let cancelled = false;
    getAccount(tick)
      .then((acc) => !cancelled && setAccount(acc))
      .catch((e) => !cancelled && handleError(e));
    return () => {
      cancelled = true;
    };
  }, [tick, playing, migration, handleError]);

  // Keep the order ticket's chain live (pure market data, no auth).
  useEffect(() => {
    if (migration) return;
    let cancelled = false;
    getChain(symbol, tick, dte)
      .then((c) => {
        if (cancelled) return;
        setChain(c);
        const mid = c.strikes[Math.floor(c.strikes.length / 2)];
        if (mid) setStrike((s) => (s == null ? mid.strike : s));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [symbol, tick, dte, migration]);

  const order = useCallback(
    async (side: Side) => {
      if (strike == null || busy) return;
      setBusy(true);
      setError(null);
      try {
        const acc = await placeOrder({
          symbol,
          option_type: optionType,
          strike,
          lots,
          side,
          dte_days: dte,
          tick: tickRef.current,
        });
        setAccount(acc);
      } catch (e) {
        handleError(e);
      } finally {
        setBusy(false);
      }
    },
    [strike, busy, symbol, optionType, lots, dte, handleError],
  );

  const close = useCallback(
    async (id: string) => {
      setBusy(true);
      try {
        setAccount(await closePosition(id, tickRef.current));
      } catch (e) {
        handleError(e);
      } finally {
        setBusy(false);
      }
    },
    [handleError],
  );

  const reset = useCallback(async () => {
    setBusy(true);
    setPlaying(false);
    try {
      const acc = await resetAccount();
      setAccount(acc);
      setTick(0);
      setError(null);
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }, [handleError]);

  if (migration) return <MigrationBanner />;

  const selectedQuote =
    chain?.strikes.find((s) => s.strike === strike)?.[optionType === "CE" ? "ce" : "pe"].ltp ?? null;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Zap className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-semibold tracking-tight">Paper Simulator</h1>
            <span className="rounded bg-secondary px-2 py-0.5 font-mono text-xs text-primary">
              SIM
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Practice option trading against a simulated market. Hypothetical only — no real orders,
            no advice.
          </p>
        </div>
        <Controls
          playing={playing}
          speed={speed}
          tick={tick}
          busy={busy}
          onToggle={() => setPlaying((p) => !p)}
          onSpeed={() => setSpeed((s) => (s === 1 ? 5 : 1))}
          onReset={reset}
        />
      </header>

      {error && (
        <Card>
          <CardContent className="py-3 text-sm text-[hsl(var(--loss))]">⚠ {error}</CardContent>
        </Card>
      )}

      <MarketTape account={account} />

      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <div className="space-y-5">
          <AccountPanel account={account} />
          <PositionsTable account={account} onClose={close} busy={busy} />
        </div>

        <OrderTicket
          chain={chain}
          symbol={symbol}
          onSymbol={(s) => {
            setSymbol(s);
            setStrike(null);
          }}
          dte={dte}
          onDte={setDte}
          lots={lots}
          onLots={setLots}
          strike={strike}
          onStrike={setStrike}
          optionType={optionType}
          onOptionType={setOptionType}
          quote={selectedQuote}
          onOrder={order}
          busy={busy}
        />
      </div>

      <Disclaimer />
    </div>
  );
}

// ── controls ──────────────────────────────────────────────────────────────────
function Controls({
  playing,
  speed,
  tick,
  busy,
  onToggle,
  onSpeed,
  onReset,
}: {
  playing: boolean;
  speed: number;
  tick: number;
  busy: boolean;
  onToggle: () => void;
  onSpeed: () => void;
  onReset: () => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="rounded-md border border-border bg-card px-2.5 py-1.5 font-mono text-xs text-muted-foreground">
        {clockLabel(tick)}
      </span>
      <Button size="sm" variant={playing ? "secondary" : "default"} onClick={onToggle}>
        {playing ? <Pause className="mr-1 h-4 w-4" /> : <Play className="mr-1 h-4 w-4" />}
        {playing ? "Pause" : "Play"}
      </Button>
      <Button size="sm" variant="outline" onClick={onSpeed}>
        {speed}×
      </Button>
      <Button size="sm" variant="ghost" onClick={onReset} disabled={busy} aria-label="Reset">
        <RotateCcw className="h-4 w-4" />
      </Button>
    </div>
  );
}

// ── market tape ─────────────────────────────────────────────────────────────
function MarketTape({ account }: { account: SimAccount | null }) {
  const quotes = account?.market ?? [];
  return (
    <div className="flex flex-wrap gap-3">
      {quotes.map((q) => (
        <div
          key={q.symbol}
          className="flex items-baseline gap-2 rounded-md border border-border bg-card px-3 py-2"
        >
          <span className="text-sm font-medium">{q.symbol}</span>
          <span className="font-mono text-lg tabular-nums">{q.spot.toLocaleString("en-IN")}</span>
          <span className="text-xs text-muted-foreground">IV {(q.iv * 100).toFixed(1)}%</span>
        </div>
      ))}
      {quotes.length === 0 && <p className="text-sm text-muted-foreground">Loading market…</p>}
    </div>
  );
}

// ── account panel ─────────────────────────────────────────────────────────────
function AccountPanel({ account }: { account: SimAccount | null }) {
  if (!account) return null;
  const g = account.greeks;
  const tone = (v: number) =>
    v > 0 ? "text-[hsl(var(--profit))]" : v < 0 ? "text-[hsl(var(--loss))]" : "text-foreground";
  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-sm">Paper account</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-x-6 gap-y-3 py-0 pb-4 sm:grid-cols-4">
        <Stat label="Equity" value={formatRupees(account.equity)} />
        <Stat label="Total P&L" value={formatRupees(account.total_pnl)} className={tone(account.total_pnl)} />
        <Stat label="Realized" value={formatRupees(account.realized_pnl)} className={tone(account.realized_pnl)} />
        <Stat label="Unrealized" value={formatRupees(account.unrealized_pnl)} className={tone(account.unrealized_pnl)} />
        <Stat label="Cash" value={formatRupees(account.cash)} />
        <Stat label="Margin (approx)" value={formatRupees(account.margin_used)} />
        <Stat label="Available" value={formatRupees(account.available)} />
        <Stat label="Direction" value={g.delta_direction} className="capitalize" />
        <Stat label="Net δ (₹/1%)" value={formatRupees(g.delta_rupees_per_pct)} className={tone(g.delta_rupees_per_pct)} />
        <Stat label="Theta (₹/day)" value={formatRupees(g.theta_rupees_per_day)} className={tone(g.theta_rupees_per_day)} />
        <Stat label="Vega (₹/pt)" value={formatRupees(g.vega_rupees_per_point)} />
        <Stat label="Capital" value={formatRupees(account.capital)} />
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="space-y-0.5">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`text-sm font-semibold tabular-nums ${className}`}>{value}</p>
    </div>
  );
}

// ── positions ───────────────────────────────────────────────────────────────
function PositionsTable({
  account,
  onClose,
  busy,
}: {
  account: SimAccount | null;
  onClose: (id: string) => void;
  busy: boolean;
}) {
  const positions = account?.positions ?? [];
  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-sm">Open positions</CardTitle>
      </CardHeader>
      <CardContent className="py-0 pb-4">
        {positions.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No open positions — place a paper order to start.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Position</th>
                  <th className="py-2 pr-3 text-right font-medium">Entry</th>
                  <th className="py-2 pr-3 text-right font-medium">Mark</th>
                  <th className="py-2 pr-3 text-right font-medium">P&L</th>
                  <th className="py-2 text-right font-medium" />
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => {
                  const tone =
                    p.unrealized_pnl > 0
                      ? "text-[hsl(var(--profit))]"
                      : p.unrealized_pnl < 0
                        ? "text-[hsl(var(--loss))]"
                        : "text-muted-foreground";
                  return (
                    <tr key={p.id} className="border-b border-border/50 last:border-0">
                      <td className="py-2 pr-3">
                        <span className={p.side === "BUY" ? "text-[hsl(var(--profit))]" : "text-[hsl(var(--loss))]"}>
                          {p.side}
                        </span>{" "}
                        <span className="font-medium">
                          {p.symbol} {p.strike} {p.option_type}
                        </span>
                        <span className="ml-1 text-xs text-muted-foreground">
                          ×{p.lots} · {p.dte_days}d
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {formatRupees(p.entry_price, { decimals: 2 })}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {formatRupees(p.mark_price, { decimals: 2 })}
                      </td>
                      <td className={`py-2 pr-3 text-right font-medium tabular-nums ${tone}`}>
                        {formatRupees(p.unrealized_pnl)}
                      </td>
                      <td className="py-2 text-right">
                        <Button size="sm" variant="outline" onClick={() => onClose(p.id)} disabled={busy}>
                          Close
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── order ticket ──────────────────────────────────────────────────────────────
function OrderTicket({
  chain,
  symbol,
  onSymbol,
  dte,
  onDte,
  lots,
  onLots,
  strike,
  onStrike,
  optionType,
  onOptionType,
  quote,
  onOrder,
  busy,
}: {
  chain: SimChain | null;
  symbol: string;
  onSymbol: (s: string) => void;
  dte: number;
  onDte: (n: number) => void;
  lots: number;
  onLots: (n: number) => void;
  strike: number | null;
  onStrike: (n: number) => void;
  optionType: OptionType;
  onOptionType: (t: OptionType) => void;
  quote: number | null;
  onOrder: (side: Side) => void;
  busy: boolean;
}) {
  const lotSize = chain?.lot_size ?? 0;
  const cost = quote != null ? quote * lots * lotSize : null;

  const pickFromLadder = (s: ChainStrike, t: OptionType) => {
    onStrike(s.strike);
    onOptionType(t);
  };

  return (
    <Card className="h-fit">
      <CardHeader className="py-3">
        <CardTitle className="text-sm">Order ticket</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 py-0 pb-4">
        <div className="flex gap-2">
          {SYMBOLS.map((s) => (
            <Button
              key={s}
              size="sm"
              variant={s === symbol ? "default" : "outline"}
              className="flex-1"
              onClick={() => onSymbol(s)}
            >
              {s}
            </Button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Field label="DTE (days)">
            <NumberInput value={dte} min={0} onChange={onDte} />
          </Field>
          <Field label="Lots">
            <NumberInput value={lots} min={1} onChange={onLots} />
          </Field>
        </div>

        <Field label="Strike & type — tap a price">
          <div className="max-h-56 overflow-y-auto rounded-md border border-border">
            <table className="w-full text-xs">
              <tbody>
                {chain?.strikes.map((s) => {
                  const atm = chain.strikes.reduce((a, b) =>
                    Math.abs(b.strike - chain.spot) < Math.abs(a.strike - chain.spot) ? b : a,
                  ).strike;
                  const sel = (t: OptionType) => strike === s.strike && optionType === t;
                  return (
                    <tr
                      key={s.strike}
                      className={s.strike === atm ? "bg-secondary/40" : undefined}
                    >
                      <td className="p-1">
                        <button
                          onClick={() => pickFromLadder(s, "CE")}
                          className={`w-full rounded px-1.5 py-1 text-right tabular-nums hover:bg-accent ${
                            sel("CE") ? "bg-primary text-primary-foreground" : ""
                          }`}
                        >
                          {s.ce.ltp.toFixed(1)}
                        </button>
                      </td>
                      <td className="px-1 text-center font-mono text-muted-foreground tabular-nums">
                        {s.strike}
                      </td>
                      <td className="p-1">
                        <button
                          onClick={() => pickFromLadder(s, "PE")}
                          className={`w-full rounded px-1.5 py-1 text-left tabular-nums hover:bg-accent ${
                            sel("PE") ? "bg-primary text-primary-foreground" : ""
                          }`}
                        >
                          {s.pe.ltp.toFixed(1)}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Field>

        <div className="rounded-md border border-border bg-background px-3 py-2 text-sm">
          {strike != null ? (
            <div className="flex items-center justify-between">
              <span className="font-medium">
                {symbol} {strike} {optionType}
              </span>
              <span className="text-muted-foreground">
                @ {quote != null ? quote.toFixed(2) : "—"}
                {cost != null && ` · ${formatRupees(cost)}`}
              </span>
            </div>
          ) : (
            <span className="text-muted-foreground">Pick a strike above</span>
          )}
        </div>

        <div className="flex gap-2">
          <Button
            className="flex-1 bg-[hsl(var(--profit))] text-white hover:opacity-90"
            disabled={busy || strike == null}
            onClick={() => onOrder("BUY")}
          >
            Buy
          </Button>
          <Button
            className="flex-1 bg-[hsl(var(--loss))] text-white hover:opacity-90"
            disabled={busy || strike == null}
            onClick={() => onOrder("SELL")}
          >
            Sell
          </Button>
        </div>
        <p className="text-[11px] text-muted-foreground">
          Simulated fills at the live mark. Buying debits premium; selling credits it and reserves
          margin.
        </p>
      </CardContent>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function NumberInput({
  value,
  min,
  onChange,
}: {
  value: number;
  min: number;
  onChange: (n: number) => void;
}) {
  return (
    <input
      type="number"
      min={min}
      value={value}
      onChange={(e) => onChange(Math.max(min, Number(e.target.value) || min))}
      className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
    />
  );
}

// ── migration gate ────────────────────────────────────────────────────────────
function MigrationBanner() {
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-tight">Paper Simulator</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">One-time setup needed</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            The simulator stores your paper account in Supabase. Run the migration{" "}
            <code className="rounded bg-secondary px-1.5 py-0.5 font-mono text-xs">
              0004_paper_sim.sql
            </code>{" "}
            in the Supabase SQL editor (the repo has a ready-to-paste{" "}
            <code className="rounded bg-secondary px-1.5 py-0.5 font-mono text-xs">
              APPLY_THIS_IN_SUPABASE_0004.sql
            </code>
            ), then reload this page.
          </p>
        </CardContent>
      </Card>
      <Disclaimer />
    </div>
  );
}
