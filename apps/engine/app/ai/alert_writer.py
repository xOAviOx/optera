"""Alert phrasing (M8): turn a breached rule into one plain-Hinglish sentence.

Delivery must NEVER depend on an LLM: if no alert provider is configured, the
call fails, or the output trips the advice filter (compliance boundary), we fall
back to a deterministic template. Either way the user gets an education-only
notification — never a recommendation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.ai import advice_filter
from app.ai.gateway import alert_providers
from app.ai.providers.base import LLMError, LLMProvider

SYSTEM_PROMPT = (
    "You write ONE short alert notification (max 2 sentences) in friendly Hinglish "
    "(Hindi-English mix) for Optera, an options risk-analytics education tool for Indian "
    "retail F&O traders. The user set their own threshold on a risk metric and it has now "
    "been crossed. State plainly: which metric, its current value, and the user's threshold. "
    "Use ₹ and Indian conventions (lakh/crore).\n\n"
    "HARD RULES — non-negotiable:\n"
    "1. EDUCATION ONLY. NEVER suggest any action: no buy/sell/exit/hedge/adjust/square-off, "
    "no predictions, no 'aapko ... chahiye'. Only describe what the number is and what it "
    "measures.\n"
    "2. Output ONLY the alert text — no preamble, no quotes, no markdown."
)

# Human labels for the template fallback (and for the model's context).
METRIC_LABELS: dict[str, str] = {
    "total_pnl": "Portfolio P&L",
    "delta_rupees_per_pct": "Delta (₹ per 1% move)",
    "theta_rupees_per_day": "Theta (₹ per day)",
    "vega_rupees_per_point": "Vega (₹ per vol point)",
    "margin_utilization_pct": "Margin utilization",
    "stress_loss_rupees": "Stress-scenario loss (±3–5% move)",
}

_PCT_METRICS = {"margin_utilization_pct"}


@dataclass(frozen=True)
class PhrasedAlert:
    message: str
    ai_phrased: bool  # False when the deterministic template was used


def fmt_inr(value: float) -> str:
    """₹ with lakh/crore units, else Indian-style digit grouping (12,34,567)."""
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1e7:
        return f"{sign}₹{v / 1e7:.2f} crore"
    if v >= 1e5:
        return f"{sign}₹{v / 1e5:.2f} lakh"
    whole = f"{v:,.0f}"  # western grouping first
    # Re-group indian style: last 3 digits, then pairs.
    digits = whole.replace(",", "")
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        pairs = []
        while len(head) > 2:
            pairs.insert(0, head[-2:])
            head = head[:-2]
        if head:
            pairs.insert(0, head)
        whole = ",".join([*pairs, tail])
    return f"{sign}₹{whole}"


def _fmt_value(metric: str, value: float) -> str:
    if metric in _PCT_METRICS:
        return f"{value:.1f}%"
    return fmt_inr(value)


def template_message(rule_name: str, metric: str, observed: float, threshold: float) -> str:
    label = METRIC_LABELS.get(metric, metric)
    return (
        f"{rule_name}: {label} abhi {_fmt_value(metric, observed)} hai — aapki set limit "
        f"{_fmt_value(metric, threshold)} cross ho gayi hai. "
        "(Education-only alert — yeh koi advice nahi hai.)"
    )


async def phrase_alert(
    rule_name: str,
    metric: str,
    operator: str,
    observed: float,
    threshold: float,
    *,
    providers: list[LLMProvider] | None = None,
) -> PhrasedAlert:
    """Phrase via the alert providers (failover), else the deterministic template."""
    fallback = template_message(rule_name, metric, observed, threshold)
    payload = json.dumps(
        {
            "rule_name": rule_name,
            "metric": metric,
            "metric_label": METRIC_LABELS.get(metric, metric),
            "operator": operator,
            "observed": round(observed, 2),
            "threshold": threshold,
            "observed_formatted": _fmt_value(metric, observed),
            "threshold_formatted": _fmt_value(metric, threshold),
        }
    )

    for provider in providers if providers is not None else alert_providers():
        try:
            resp = await provider.complete(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": payload}],
                tools=[],
            )
        except LLMError:
            continue  # failover to the next provider
        text = (resp.text or "").strip()
        if not text:
            continue
        safe, flagged = advice_filter.screen(text)
        if flagged:
            break  # model tried to advise — use the template, don't retry
        return PhrasedAlert(message=safe, ai_phrased=True)

    return PhrasedAlert(message=fallback, ai_phrased=False)
