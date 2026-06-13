import { Disclaimer } from "@optera/ui";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getEngineHealth } from "@/lib/api";

const MODULES = [
  { id: "M2", title: "Auth + broker connect", note: "Upstox OAuth, encrypted tokens" },
  { id: "M3", title: "Quant core", note: "BS, IV, Greeks, payoff, scenario, POP" },
  { id: "M4", title: "Live positions + WS", note: "Streamed P&L, net delta, margin meter" },
  { id: "M5", title: "Risk visuals", note: "Payoff diagram, scenario simulator" },
  { id: "M6", title: "Chain + IV analytics", note: "Smile/skew, IV rank, OI/PCR" },
  { id: "M7", title: "AI co-pilot", note: "Gemini tool-calling, Hinglish chat" },
  { id: "M8", title: "Monitoring + alerts", note: "Market-hours worker, Telegram" },
  { id: "M9", title: "Journal + strategy", note: "Closed-trade stats, paper builder" },
];

export default async function DashboardPage() {
  const health = await getEngineHealth();
  const engineUp = health?.status === "ok";

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          Welcome to Optera
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Your F&O risk, explained clearly. Connect your broker to see live Greeks, payoff, and
          scenarios — with an AI co-pilot that watches your book and pings you in Hinglish the
          moment your risk character changes.
        </p>
      </section>

      <div className="flex flex-wrap gap-3">
        <StatusBadge label="Engine" ok={engineUp} detail={health?.version ? `v${health.version}` : "offline"} />
        <StatusBadge label="Broker" ok={false} detail="not connected" />
        <StatusBadge label="Market" ok={false} detail="09:15–15:30 IST" />
      </div>

      <Disclaimer />

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Build roadmap
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {MODULES.map((m) => (
            <Card key={m.id}>
              <CardHeader>
                <CardDescription className="text-xs font-mono text-primary">{m.id}</CardDescription>
                <CardTitle className="text-base">{m.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">{m.note}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}

function StatusBadge({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm">
      <span
        className={`h-2 w-2 rounded-full ${ok ? "bg-[hsl(var(--profit))]" : "bg-muted-foreground"}`}
        aria-hidden
      />
      <span className="font-medium">{label}</span>
      <span className="text-muted-foreground">{detail}</span>
    </div>
  );
}
