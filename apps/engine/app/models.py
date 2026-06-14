"""Pydantic models — keep in sync with packages/types (shared TS types)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class OptionType(StrEnum):
    CALL = "CE"
    PUT = "PE"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class Leg(BaseModel):
    """A single option (or future) leg of a position/strategy."""

    symbol: str
    option_type: OptionType | None = None  # None => future/underlying
    strike: float | None = None
    expiry: str | None = None  # ISO date
    side: Side
    lots: int = Field(gt=0)
    lot_size: int = Field(gt=0)
    entry_price: float | None = None
    iv: float | None = None  # decimal (e.g. 0.18 == 18%)


class Greeks(BaseModel):
    delta: float
    gamma: float
    theta: float  # per day
    vega: float  # per 1 vol point
    rho: float


class PortfolioGreeks(BaseModel):
    net: Greeks
    delta_rupees_per_pct: float  # ₹ P&L per 1% underlying move
    theta_rupees_per_day: float
    vega_rupees_per_point: float
    delta_direction: str  # "bullish" | "bearish" | "neutral"


class PayoffRequest(BaseModel):
    legs: list[Leg]
    spot: float
    spot_range_pct: float = 0.15
    steps: int = 200
    iv: float | None = None
    days_to_expiry: float | None = None


class PayoffResponse(BaseModel):
    spots: list[float]
    pnl_expiry: list[float]
    pnl_t0: list[float]
    breakevens: list[float]
    max_profit: float | None
    max_loss: float | None


class ScenarioRequest(BaseModel):
    legs: list[Leg]
    spot: float
    spot_move_pct: float = 0.0
    iv_change_pts: float = 0.0
    days_elapsed: float = 0.0


class ScenarioResponse(BaseModel):
    pnl_delta: float
    per_leg: list[dict]
    new_greeks: PortfolioGreeks


class PopRequest(BaseModel):
    legs: list[Leg]
    spot: float
    atm_iv: float  # decimal, e.g. 0.18
    days_to_expiry: float | None = None  # falls back to legs' expiry horizon
    mode: str = "lognormal"  # "lognormal" | "monte_carlo"
    n_paths: int = 10_000


class PopResponse(BaseModel):
    probability_of_profit: float | None
    mode: str


class LoginUrlResponse(BaseModel):
    url: str


class BrokerConnectRequest(BaseModel):
    code: str
    state: str | None = None


class AnalyticsTokenRequest(BaseModel):
    analytics_token: str


class BrokerConnectResponse(BaseModel):
    connected: bool
    broker: str
    status: str
    expires_at: str | None = None


class BrokerStatusResponse(BaseModel):
    connected: bool
    broker: str = "upstox"
    status: str | None = None
    expires_at: str | None = None
    reconnect_needed: bool = True
    has_analytics_token: bool = False


class MarginResponse(BaseModel):
    used: float
    available: float
    equity: dict | None = None
    commodity: dict | None = None


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class StrategyContext(BaseModel):
    """The user's current hypothetical structure, sent so the co-pilot's tools
    can analyze it. Legs carry the same fields the quant endpoints expect."""

    legs: list[Leg] = Field(default_factory=list)
    spot: float
    iv_pct: float = 14.0  # ATM IV in percent
    dte: float = 7.0  # days to expiry


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: StrategyContext | None = None


class ChatResponse(BaseModel):
    reply: str
    flagged: bool = False  # advice filter replaced the model's output


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
