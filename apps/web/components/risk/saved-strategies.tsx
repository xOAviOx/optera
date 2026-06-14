"use client";

import { Bookmark, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  deleteStrategy,
  listStrategies,
  saveStrategy,
  type SavedStrategy,
} from "@/lib/strategies";
import { useStrategyStore } from "@/lib/strategy-store";

export function SavedStrategies() {
  const spot = useStrategyStore((s) => s.spot);
  const ivPct = useStrategyStore((s) => s.ivPct);
  const dte = useStrategyStore((s) => s.dte);
  const legs = useStrategyStore((s) => s.legs);
  const setSpot = useStrategyStore((s) => s.setSpot);
  const setIvPct = useStrategyStore((s) => s.setIvPct);
  const setDte = useStrategyStore((s) => s.setDte);
  const setLegs = useStrategyStore((s) => s.setLegs);

  const [items, setItems] = useState<SavedStrategy[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setItems(await listStrategies());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onSave() {
    const trimmed = name.trim();
    if (!trimmed || legs.length === 0 || busy) return;
    setBusy(true);
    setError(null);
    try {
      await saveStrategy({ name: trimmed, spot, ivPct, dte, legs });
      setName("");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onLoad(s: SavedStrategy) {
    setSpot(s.spot);
    setIvPct(s.ivPct);
    setDte(s.dte);
    setLegs(s.legs);
  }

  async function onDelete(id: string) {
    try {
      await deleteStrategy(id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Bookmark className="h-4 w-4 text-primary" /> Saved strategies
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pb-4">
        <div className="flex items-center gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSave()}
            placeholder="Name this structure…"
            className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
          />
          <Button size="sm" onClick={onSave} disabled={busy || !name.trim() || legs.length === 0}>
            Save
          </Button>
        </div>

        {items.length > 0 ? (
          <ul className="space-y-1.5">
            {items.map((s) => (
              <li
                key={s.id}
                className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-1.5 text-sm"
              >
                <button onClick={() => onLoad(s)} className="flex-1 text-left hover:text-primary">
                  <span className="font-medium">{s.name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {s.legs.length} leg{s.legs.length === 1 ? "" : "s"} · spot{" "}
                    {s.spot.toLocaleString("en-IN")} · {s.dte}d
                  </span>
                </button>
                <button
                  onClick={() => onDelete(s.id)}
                  className="text-muted-foreground hover:text-[hsl(var(--loss))]"
                  aria-label={`delete ${s.name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        ) : (
          !error && <p className="text-xs text-muted-foreground">No saved structures yet.</p>
        )}

        {error && <p className="text-xs text-[hsl(var(--loss))]">⚠ {error}</p>}
      </CardContent>
    </Card>
  );
}
