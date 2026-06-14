"use client";

import { Bot, Send } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Disclaimer } from "@optera/ui";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { sendChat, type ChatMessage } from "@/lib/copilot";
import { toWireLegs } from "@/lib/quant";
import { useStrategyStore } from "@/lib/strategy-store";

const STARTERS = [
  "Mere structure ka risk samjhao.",
  "What if NIFTY 3% gir jaye?",
  "Mera theta help kar raha hai ya hurt?",
  "Mere breakevens kya hain?",
];

export default function CopilotPage() {
  const spot = useStrategyStore((s) => s.spot);
  const ivPct = useStrategyStore((s) => s.ivPct);
  const dte = useStrategyStore((s) => s.dte);
  const legs = useStrategyStore((s) => s.legs);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || loading) return;
    setError(null);
    const next: ChatMessage[] = [...messages, { role: "user", content }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const context =
        legs.length > 0
          ? { legs: toWireLegs(legs, ivPct, dte), spot, iv_pct: ivPct, dte }
          : null;
      const reply = await sendChat(next, context);
      setMessages([...next, { role: "assistant", content: reply.reply }]);
    } catch (e) {
      setError((e as Error).message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Bot className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-semibold tracking-tight">Co-Pilot</h1>
          <span className="rounded bg-secondary px-2 py-0.5 font-mono text-xs text-primary">M7</span>
        </div>
        <p className="text-sm text-muted-foreground">
          Ask about your structure&apos;s risk in Hinglish. Education &amp; analytics only — no
          buy/sell calls.
        </p>
      </header>

      <StrategySummary spot={spot} ivPct={ivPct} dte={dte} legs={legs} />

      <Card className="flex min-h-[24rem] flex-col">
        <CardContent className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.length === 0 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Poochhein kuch bhi apne risk ke baare mein — ya in se shuru karein:
              </p>
              <div className="flex flex-wrap gap-2">
                {STARTERS.map((s) => (
                  <Button key={s} variant="outline" size="sm" onClick={() => send(s)}>
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <Bubble key={i} role={m.role} content={m.content} />
          ))}
          {loading && <Bubble role="assistant" content="…" />}
          {error && <p className="text-sm text-[hsl(var(--loss))]">⚠ {error}</p>}
          <div ref={endRef} />
        </CardContent>

        <div className="border-t border-border p-3">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-center gap-2"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your question…"
              className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <Button type="submit" size="icon" disabled={loading || !input.trim()} aria-label="Send">
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </Card>

      <Disclaimer />
    </div>
  );
}

function Bubble({ role, content }: { role: "user" | "assistant"; content: string }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "border border-border bg-background text-foreground"
        }`}
      >
        {content}
      </div>
    </div>
  );
}

interface SummaryLeg {
  id: string;
  side: string;
  lots: number;
  lotSize: number;
  strike: number;
  optionType: string;
}

function StrategySummary({
  spot,
  ivPct,
  dte,
  legs,
}: {
  spot: number;
  ivPct: number;
  dte: number;
  legs: SummaryLeg[];
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 py-3">
        <CardTitle className="text-sm">Structure being analyzed</CardTitle>
        <Link href="/risk" className="text-xs text-primary hover:underline">
          Edit in Risk →
        </Link>
      </CardHeader>
      <CardContent className="py-0 pb-4">
        {legs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No legs yet — build a structure in the Risk workbench first.
          </p>
        ) : (
          <div className="space-y-1 text-sm">
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>Spot {spot.toLocaleString("en-IN")}</span>
              <span>IV {ivPct}%</span>
              <span>{dte}d to expiry</span>
            </div>
            <ul className="flex flex-wrap gap-2">
              {legs.map((l) => (
                <li
                  key={l.id}
                  className="rounded border border-border bg-background px-2 py-0.5 font-mono text-xs"
                >
                  {l.side} {l.lots}×{l.lotSize} {l.strike} {l.optionType}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
