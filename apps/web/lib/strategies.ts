/**
 * Saved paper strategies (M9) — direct web↔Supabase CRUD under RLS.
 *
 * These are pure user-owned records, so they don't go through the engine; the
 * browser Supabase client + row-level security scope everything to the user.
 */
import { createClient } from "./supabase/client";
import { type UiLeg } from "./quant";

export interface SavedStrategy {
  id: string;
  name: string;
  spot: number;
  ivPct: number;
  dte: number;
  legs: UiLeg[];
  createdAt: string;
}

interface StrategyRow {
  id: string;
  name: string;
  spot: number | string;
  iv_pct: number | string;
  dte: number | string;
  legs_jsonb: UiLeg[] | null;
  created_at: string;
}

const COLUMNS = "id,name,spot,iv_pct,dte,legs_jsonb,created_at";

function toStrategy(r: StrategyRow): SavedStrategy {
  return {
    id: r.id,
    name: r.name,
    spot: Number(r.spot),
    ivPct: Number(r.iv_pct),
    dte: Number(r.dte),
    legs: r.legs_jsonb ?? [],
    createdAt: r.created_at,
  };
}

export async function listStrategies(): Promise<SavedStrategy[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("strategies")
    .select(COLUMNS)
    .order("created_at", { ascending: false });
  if (error) throw new Error(error.message);
  return (data as StrategyRow[]).map(toStrategy);
}

export interface NewStrategy {
  name: string;
  spot: number;
  ivPct: number;
  dte: number;
  legs: UiLeg[];
}

export async function saveStrategy(input: NewStrategy): Promise<SavedStrategy> {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error("Please sign in again — your session expired.");

  const { data, error } = await supabase
    .from("strategies")
    .insert({
      user_id: user.id,
      name: input.name,
      spot: input.spot,
      iv_pct: input.ivPct,
      dte: input.dte,
      legs_jsonb: input.legs,
    })
    .select(COLUMNS)
    .single();
  if (error) throw new Error(error.message);
  return toStrategy(data as StrategyRow);
}

export async function deleteStrategy(id: string): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase.from("strategies").delete().eq("id", id);
  if (error) throw new Error(error.message);
}
