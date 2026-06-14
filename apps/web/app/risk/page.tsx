"use client";

import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Disclaimer } from "@optera/ui";

import { PayoffChart } from "@/components/risk/payoff-chart";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  computePayoff,
  computePop,
  computeScenario,
  toWireLegs,
  type OptionType,
  type PayoffResponse,
  type PopResponse,
  type ScenarioResponse,
  type Side,
  type UiLeg,
} from "@/lib/quant";
import { formatRupees } from "@/lib/utils";

const DEFAULT_LOT = 75; // NIFTY; editable per leg

const newId = () =>
  typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : String(Math.random());

function leg(optionType: OptionType, side: Side, strike: number, lots = 1): UiLeg {
  return { id: newId(), optionType, side, strike, lots, lotSize: DEFAULT_LOT };
}

/** Educational structures (building blocks) seeded around the current spot. */
function presets(spot: number): Record<string, UiLeg[]> {
  const atm = Math.round(spot / 100) * 100;
  return {
    "Long straddle": [leg("CE", "BUY", atm), leg("PE", "BUY", atm)],
    "Long strangle": [leg("CE", "BUY", atm + 200), leg("PE", "BUY", atm - 200)],
    "Call spread": [leg("CE", "BUY", atm), leg("CE", "SELL", atm + 200)],
    "Iron condor": [
      leg("PE", "BUY", atm - 400),
      leg("PE", "SELL", atm - 200),
      leg("CE", "SELL", atm + 200),
      leg("CE", "BUY", atm + 400),
    ],
  };
}

export default function RiskPage() {
  const [spot, setSpot] = useState(23500);
  const [ivPct, setIvPct] = useState(14);
  const [dte, setDte] = useState(7);
  const [legs, setLegs] = useState<UiLeg[]>(() => {
    const atm = 23500;
    return [leg("CE", "BUY", atm), leg("PE", "BUY", atm)];
  });

  const [payoff, setPayoff] = useState<PayoffResponse | null>(null);
  const [pop, setPop] = useState<PopResponse | null>(null);
  const [scenario, setScenario] = useState<ScenarioResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [spotMovePct, setSpotMovePct] = useState(0);
  const [ivChangePts, setIvChangePts] = useState(0);
  const [daysElapsed, setDaysElapsed] = useState(0);

  // Recompute payoff + POP whenever the book or market inputs change.
  useEffect(() => {
    if (legs.length === 0) {
      setPayoff(null);
      setPop(null);
      setError(null);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const wire = toWireLegs(legs, ivPct, dte);
        const [pf, pp] = await Promise.all([
          computePayoff(
            { legs: wire, spot, spot_range_pct: 0.15, steps: 220, iv: ivPct / 100, days_to_expiry: dte },
            ctrl.signal,
          ),
          computePop(
            { legs: wire, spot, atm_iv: ivPct / 100, days_to_expiry: dte, mode: "lognormal" },
            ctrl.signal,
          ),
        ]);
        setPayoff(pf);
        setPop(pp);
      } catch (e) {
        if (!(e instanceof DOMException && e.name === "AbortError")) {
          setError((e as Error).message || "Compute failed");
        }
      } finally {
        setLoading(false);
      }
    }, 180);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [legs, spot, ivPct, dte]);

  // Recompute the scenario when its knobs (or the base book) change.
  useEffect(() => {
    if (legs.length === 0) {
      setScenario(null);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      try {
        const wire = toWireLegs(legs, ivPct, dte);
        const sc = await computeScenario(
          {
            legs: wire,
            spot,
            spot_move_pct: spotMovePct / 100,
            iv_change_pts: ivChangePts,
            days_elapsed: daysElapsed,
          },
          ctrl.signal,
        );
        setScenario(sc);
      } catch {
        /* base effect surfaces errors; ignore aborts here */
      }
    }, 180);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [legs, spot, ivPct, dte, spotMovePct, ivChangePts, daysElapsed]);

  const updateLeg = (id: string, patch: Partial<UiLeg>) =>
    setLegs((ls) => ls.map((l) => (l.id === id ? { ...l, ...patch } : l)));
  const removeLeg = (id: string) => setLegs((ls) => ls.filter((l) => l.id !== id));
  const addLeg = () => setLegs((ls) => [...ls, leg("CE", "BUY", Math.round(spot / 100) * 100)]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">Risk workbench</h1>
            <span className="rounded bg-secondary px-2 py-0.5 font-mono text-xs text-primary">M5</span>
          </div>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Build a hypothetical options structure and see how it behaves across price, time and
            volatility. Paper only — nothing here is a trade or a recommendation.
          </p>
        </div>
        {loading && <span className="text-xs text-muted-foreground">computing…</span>}
      </header>

      <Disclaimer />

      <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        {/* ── Builder ─────────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Strategy builder</CardTitle>
            <CardDescription>Underlying assumptions apply to every leg.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <NumberField label="Spot" value={spot} step={50} onChange={setSpot} />
              <NumberField label="IV %" value={ivPct} step={0.5} onChange={setIvPct} />
              <NumberField label="Days to expiry" value={dte} step={1} onChange={setDte} />
            </div>

            <div className="flex flex-wrap gap-2">
              {Object.entries(presets(spot)).map(([name, ls]) => (
                <Button
                  key={name}
                  variant="outline"
                  size="sm"
                  onClick={() => setLegs(ls.map((l) => ({ ...l, id: newId() })))}
                >
                  {name}
                </Button>
              ))}
            </div>

            <div className="space-y-2">
              {legs.length === 0 && (
                <p className="text-sm text-muted-foreground">No legs — add one or pick a structure.</p>
              )}
              {legs.map((l) => (
                <LegRow key={l.id} leg={l} onChange={updateLeg} onRemove={removeLeg} />
              ))}
            </div>

            <Button variant="secondary" size="sm" onClick={addLeg}>
              + Add leg
            </Button>

            {error && <p className="text-sm text-[hsl(var(--loss))]">⚠ {error}</p>}
          </CardContent>
        </Card>

        {/* ── Payoff ──────────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Payoff</CardTitle>
            <CardDescription>
              <span className="text-foreground">━</span> at expiry &nbsp;·&nbsp;
              <span className="text-muted-foreground">╴╴</span> now (T+0)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <PayoffChart
              spots={payoff?.spots ?? []}
              pnlExpiry={payoff?.pnl_expiry ?? []}
              pnlT0={payoff?.pnl_t0 ?? []}
              breakevens={payoff?.breakevens ?? []}
              spot={spot}
            />
            <div className="grid grid-cols-3 gap-3">
              <Stat label="Max profit" value={fmtMaybe(payoff?.max_profit)} tone="profit" />
              <Stat label="Max loss" value={fmtMaybe(payoff?.max_loss)} tone="loss" />
              <Stat
                label="Prob. of profit"
                value={pop?.probability_of_profit != null ? `${(pop.probability_of_profit * 100).toFixed(1)}%` : "—"}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ── Greeks ──────────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Portfolio Greeks</CardTitle>
            <CardDescription>Net sensitivities of the whole book.</CardDescription>
          </CardHeader>
          <CardContent>
            <GreeksPanel scenario={scenario} />
          </CardContent>
        </Card>

        {/* ── Scenario ────────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">What-if simulator</CardTitle>
            <CardDescription>Stress the book; P&amp;L is vs. now.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Slider
              label="Spot move"
              value={spotMovePct}
              min={-10}
              max={10}
              step={0.5}
              suffix="%"
              onChange={setSpotMovePct}
            />
            <Slider
              label="IV change"
              value={ivChangePts}
              min={-15}
              max={15}
              step={0.5}
              suffix=" pts"
              onChange={setIvChangePts}
            />
            <Slider
              label="Days elapsed"
              value={daysElapsed}
              min={0}
              max={Math.max(1, dte)}
              step={1}
              suffix="d"
              onChange={setDaysElapsed}
            />

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => preset(setSpotMovePct, setIvChangePts, setDaysElapsed, 2, -2, 0)}>
                Gap up +2%
              </Button>
              <Button variant="outline" size="sm" onClick={() => preset(setSpotMovePct, setIvChangePts, setDaysElapsed, -2, 3, 0)}>
                Gap down −2%
              </Button>
              <Button variant="outline" size="sm" onClick={() => preset(setSpotMovePct, setIvChangePts, setDaysElapsed, 0, -5, 0)}>
                IV crush −5
              </Button>
              <Button variant="outline" size="sm" onClick={() => preset(setSpotMovePct, setIvChangePts, setDaysElapsed, 0, 0, 0)}>
                Reset
              </Button>
            </div>

            <div className="rounded-md border border-border bg-background p-4">
              <p className="text-xs text-muted-foreground">Estimated P&amp;L impact</p>
              {scenario ? (
                <p
                  className={`text-2xl font-semibold ${
                    scenario.pnl_delta >= 0 ? "text-[hsl(var(--profit))]" : "text-[hsl(var(--loss))]"
                  }`}
                >
                  {scenario.pnl_delta >= 0 ? "+" : ""}
                  {formatRupees(scenario.pnl_delta)}
                </p>
              ) : (
                <p className="text-2xl font-semibold text-muted-foreground">—</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ── small components ──────────────────────────────────────────────────────────
function preset(
  setMove: (n: number) => void,
  setIv: (n: number) => void,
  setDays: (n: number) => void,
  move: number,
  iv: number,
  days: number,
) {
  setMove(move);
  setIv(iv);
  setDays(days);
}

function fmtMaybe(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "Unlimited";
  return formatRupees(v);
}

function NumberField({
  label,
  value,
  step,
  onChange,
}: {
  label: string;
  value: number;
  step: number;
  onChange: (n: number) => void;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        type="number"
        value={value}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
      />
    </label>
  );
}

function LegRow({
  leg,
  onChange,
  onRemove,
}: {
  leg: UiLeg;
  onChange: (id: string, patch: Partial<UiLeg>) => void;
  onRemove: (id: string) => void;
}) {
  const sideClr =
    leg.side === "BUY" ? "text-[hsl(var(--profit))]" : "text-[hsl(var(--loss))]";
  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-background px-2 py-1.5">
      <select
        value={leg.side}
        onChange={(e) => onChange(leg.id, { side: e.target.value as Side })}
        className={`bg-transparent text-sm font-medium outline-none ${sideClr}`}
      >
        <option value="BUY">BUY</option>
        <option value="SELL">SELL</option>
      </select>
      <input
        type="number"
        value={leg.lots}
        min={1}
        onChange={(e) => onChange(leg.id, { lots: Math.max(1, Number(e.target.value)) })}
        className="w-12 rounded border border-border bg-background px-1.5 py-1 text-sm outline-none"
        aria-label="lots"
      />
      <span className="text-xs text-muted-foreground">×{leg.lotSize}</span>
      <input
        type="number"
        value={leg.strike}
        step={50}
        onChange={(e) => onChange(leg.id, { strike: Number(e.target.value) })}
        className="w-24 rounded border border-border bg-background px-1.5 py-1 text-sm outline-none"
        aria-label="strike"
      />
      <select
        value={leg.optionType}
        onChange={(e) => onChange(leg.id, { optionType: e.target.value as OptionType })}
        className="rounded bg-transparent text-sm font-medium outline-none"
      >
        <option value="CE">CE</option>
        <option value="PE">PE</option>
      </select>
      <button
        onClick={() => onRemove(leg.id)}
        className="ml-auto text-muted-foreground hover:text-[hsl(var(--loss))]"
        aria-label="remove leg"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "profit" | "loss";
}) {
  const clr = tone === "profit" ? "text-[hsl(var(--profit))]" : tone === "loss" ? "text-[hsl(var(--loss))]" : "text-foreground";
  return (
    <div className="rounded-md border border-border bg-background p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-sm font-semibold ${clr}`}>{value}</p>
    </div>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix: string;
  onChange: (n: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono">
          {value > 0 ? "+" : ""}
          {value}
          {suffix}
        </span>
      </div>
      <input
        type="range"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[hsl(var(--primary))]"
      />
    </div>
  );
}

function GreeksPanel({ scenario }: { scenario: ScenarioResponse | null }) {
  if (!scenario) {
    return <p className="text-sm text-muted-foreground">Build a structure to see Greeks.</p>;
  }
  const g = scenario.new_greeks;
  const theta = g.theta_rupees_per_day;
  const thetaCaption =
    theta >= 0
      ? `Time decay is adding ~${formatRupees(theta)}/day to this book.`
      : `Time decay is costing ~${formatRupees(Math.abs(theta))}/day.`;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-5 gap-2 text-center">
        {(["delta", "gamma", "theta", "vega", "rho"] as const).map((k) => (
          <div key={k} className="rounded-md border border-border bg-background p-2">
            <p className="text-[10px] uppercase text-muted-foreground">{k}</p>
            <p className="text-sm font-semibold tabular-nums">{g.net[k].toFixed(2)}</p>
          </div>
        ))}
      </div>
      <ul className="space-y-1.5 text-sm text-muted-foreground">
        <li>
          Net delta is <span className="text-foreground">{g.delta_direction}</span> — about{" "}
          <span className="text-foreground">{formatRupees(g.delta_rupees_per_pct)}</span> per 1% move
          in the underlying.
        </li>
        <li>{thetaCaption}</li>
        <li>
          A 1-point IV change moves P&amp;L by ~
          <span className="text-foreground">{formatRupees(g.vega_rupees_per_point)}</span>.
        </li>
      </ul>
    </div>
  );
}
