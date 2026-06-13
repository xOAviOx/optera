// Shared TS types. Keep in sync with apps/engine/app/models.py (Pydantic).

export type OptionType = "CE" | "PE";
export type Side = "BUY" | "SELL";
export type DeltaDirection = "bullish" | "bearish" | "neutral";

export interface Leg {
  symbol: string;
  optionType?: OptionType | null;
  strike?: number | null;
  expiry?: string | null;
  side: Side;
  lots: number;
  lotSize: number;
  entryPrice?: number | null;
  iv?: number | null;
}

export interface Greeks {
  delta: number;
  gamma: number;
  theta: number; // per day
  vega: number; // per 1 vol point
  rho: number;
}

export interface PortfolioGreeks {
  net: Greeks;
  deltaRupeesPerPct: number;
  thetaRupeesPerDay: number;
  vegaRupeesPerPoint: number;
  deltaDirection: DeltaDirection;
}

export interface NormalizedPosition {
  instrumentToken: string;
  tradingsymbol: string;
  name?: string | null;
  optionType?: OptionType | null;
  strike?: number | null;
  expiry?: string | null;
  quantity: number; // signed
  lotSize: number;
  averagePrice: number;
  lastPrice?: number | null;
  pnl?: number | null;
}

// Realtime stream frames (WS /stream)
export type StreamFrame =
  | { type: "hello"; msg: string }
  | { type: "tick"; positions: NormalizedPosition[]; net_pnl: number; ts: number }
  | {
      type: "risk";
      greeks: PortfolioGreeks;
      margin: { used: number; available: number };
      delta_direction: DeltaDirection;
      ts: number;
    }
  | { type: "broker_expired" };

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
}
