"""Pydantic models — keep in sync with packages/types (shared TS types)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

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


# ── Paper-trading simulator (hypothetical/paper only — no real orders, no advice)
class SimMarketQuote(BaseModel):
    symbol: str
    spot: float
    iv: float  # decimal


class MarkedPosition(BaseModel):
    id: str
    symbol: str
    option_type: str
    strike: float
    side: str
    lots: int
    lot_size: int
    entry_tick: int
    entry_price: float
    expiry_tick: int
    dte_days: float
    mark_price: float
    unrealized_pnl: float
    value: float


class SimAccountResponse(BaseModel):
    capital: float
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    equity: float
    total_pnl: float
    margin_used: float
    available: float
    clock_tick: int
    positions: list[MarkedPosition]
    greeks: PortfolioGreeks
    market: list[SimMarketQuote]


class SimOrderRequest(BaseModel):
    symbol: str
    option_type: OptionType
    strike: float = Field(gt=0)
    lots: int = Field(gt=0)
    side: Side
    dte_days: float = Field(default=7.0, ge=0)
    tick: int = Field(ge=0)


class SimCloseRequest(BaseModel):
    position_id: str
    tick: int = Field(ge=0)


class SimChainQuote(BaseModel):
    ltp: float


class SimChainStrike(BaseModel):
    strike: float
    ce: SimChainQuote
    pe: SimChainQuote


class SimChainResponse(BaseModel):
    symbol: str
    spot: float
    iv: float
    dte_days: float
    expiry_tick: int
    lot_size: int
    strikes: list[SimChainStrike]


# ── Monitoring + alerts (M8) — education-only notifications, never advice ─────
class AlertMetric(StrEnum):
    """Risk metrics a rule can watch. All are read from the user's risk snapshot."""

    TOTAL_PNL = "total_pnl"  # ₹, signed
    DELTA_RUPEES_PER_PCT = "delta_rupees_per_pct"  # ₹ per 1% underlying move
    THETA_RUPEES_PER_DAY = "theta_rupees_per_day"  # ₹ per day (decay is negative)
    VEGA_RUPEES_PER_POINT = "vega_rupees_per_point"  # ₹ per 1 vol point
    MARGIN_UTILIZATION_PCT = "margin_utilization_pct"  # 0–100
    STRESS_LOSS_RUPEES = "stress_loss_rupees"  # ₹, worst loss over ±3/±5% moves


class AlertOperator(StrEnum):
    GT = "gt"
    LT = "lt"
    ABS_GT = "abs_gt"


class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    metric: AlertMetric
    operator: AlertOperator
    threshold: float
    enabled: bool = True
    cooldown_minutes: int = Field(default=60, ge=1, le=24 * 60)


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    metric: AlertMetric | None = None
    operator: AlertOperator | None = None
    threshold: float | None = None
    enabled: bool | None = None
    cooldown_minutes: int | None = Field(default=None, ge=1, le=24 * 60)


class AlertRule(BaseModel):
    id: str
    name: str
    metric: AlertMetric
    operator: AlertOperator
    threshold: float
    enabled: bool
    cooldown_minutes: int
    last_triggered_at: str | None = None
    created_at: str | None = None


class AlertEvent(BaseModel):
    id: str
    rule_id: str | None = None
    rule_name: str
    metric: AlertMetric
    operator: AlertOperator
    threshold: float
    observed: float
    message: str
    ai_phrased: bool = False
    acknowledged: bool = False
    created_at: str | None = None


class AlertRulesResponse(BaseModel):
    rules: list[AlertRule]


class AlertsResponse(BaseModel):
    alerts: list[AlertEvent]


class RiskSnapshot(BaseModel):
    """Current portfolio risk metrics the rules are evaluated against.

    Metrics are None when they can't be computed right now (e.g. no option
    positions, or spot/IV unavailable for the live broker).
    """

    total_pnl: float | None = None
    delta_rupees_per_pct: float | None = None
    theta_rupees_per_day: float | None = None
    vega_rupees_per_point: float | None = None
    margin_utilization_pct: float | None = None
    stress_loss_rupees: float | None = None
    option_legs: int = 0
    underlyings: list[str] = Field(default_factory=list)
    skipped_underlyings: list[str] = Field(default_factory=list)


class AlertCheckResponse(BaseModel):
    snapshot: RiskSnapshot
    fired: list[AlertEvent]
    checked_rules: int


# ── Strategy analyzer (M9 — hypothetical/paper only, never advice) ─────────────
class StrategyAnalyzeRequest(BaseModel):
    """A hypothetical option structure to analyze. Pure what-if math, no orders."""

    legs: list[Leg]
    spot: float
    iv_pct: float = 14.0  # single ATM IV in percent (per-leg iv overrides this)
    dte: float = 7.0  # days to expiry
    spot_range_pct: float = 0.15
    steps: int = 200


class StrategyAnalyzeResponse(BaseModel):
    net_premium: float  # entry cash flow: credit (+) / debit (-), in ₹
    max_profit: float | None
    max_loss: float | None
    breakevens: list[float]
    greeks: PortfolioGreeks
    probability_of_profit: float | None
    defined_risk: bool
    margin_estimate: float  # rough, education-only — NOT broker SPAN+Exposure
    margin_note: str


# ── Trade journal (M9) ────────────────────────────────────────────────────────
class JournalTradeCreate(BaseModel):
    """A trade the user logs. Legs are validated on the way in; on read they are
    returned as-stored (tolerant) so a schema tweak can't brick the journal."""

    legs: list[Leg] = Field(default_factory=list)
    opened_at: str | None = None  # ISO datetime
    closed_at: str | None = None  # None => still open (excluded from stats)
    realized_pnl: float | None = None  # ₹; None => open


class JournalTrade(BaseModel):
    id: str
    opened_at: str | None = None
    closed_at: str | None = None
    legs: list[dict[str, Any]] = Field(default_factory=list)
    realized_pnl: float | None = None
    ai_review: str | None = None
    underlying: str | None = None  # derived from legs, for grouping


class JournalStats(BaseModel):
    closed_trades: int = 0
    open_trades: int = 0
    total_realized_pnl: float = 0.0
    win_rate: float | None = None  # 0..1 over closed trades
    avg_win: float | None = None
    avg_loss: float | None = None  # negative
    profit_factor: float | None = None  # gross win / gross loss
    best: float | None = None
    worst: float | None = None
    pnl_by_underlying: dict[str, float] = Field(default_factory=dict)
    equity_curve: list[float] = Field(default_factory=list)  # cumulative, by close time


class JournalResponse(BaseModel):
    trades: list[JournalTrade]
    stats: JournalStats
