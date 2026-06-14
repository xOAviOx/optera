/**
 * Shared hypothetical-strategy state, used by both the Risk workbench (/risk) and
 * the AI co-pilot (/copilot) so the co-pilot can analyze the structure you built.
 *
 * In-memory (survives client-side navigation between pages; resets on full reload)
 * — deliberately not persisted, to avoid SSR hydration mismatches.
 */
import { create } from "zustand";

import type { UiLeg } from "./quant";

const DEFAULT_LOT = 75; // NIFTY

// Stable ids for the seeded structure (deterministic across SSR/CSR).
const DEFAULT_LEGS: UiLeg[] = [
  { id: "seed-ce", optionType: "CE", side: "BUY", strike: 23500, lots: 1, lotSize: DEFAULT_LOT },
  { id: "seed-pe", optionType: "PE", side: "BUY", strike: 23500, lots: 1, lotSize: DEFAULT_LOT },
];

interface StrategyState {
  spot: number;
  ivPct: number;
  dte: number;
  legs: UiLeg[];
  setSpot: (n: number) => void;
  setIvPct: (n: number) => void;
  setDte: (n: number) => void;
  setLegs: (legs: UiLeg[]) => void;
}

export const useStrategyStore = create<StrategyState>((set) => ({
  spot: 23500,
  ivPct: 14,
  dte: 7,
  legs: DEFAULT_LEGS,
  setSpot: (spot) => set({ spot }),
  setIvPct: (ivPct) => set({ ivPct }),
  setDte: (dte) => set({ dte }),
  setLegs: (legs) => set({ legs }),
}));
