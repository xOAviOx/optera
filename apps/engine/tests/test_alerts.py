"""Monitoring + alerts (M8), fully offline.

Covers rule evaluation (operators, cooldown), the risk snapshot built from the
mock broker's synthetic book, alert phrasing (template fallback, advice-filter
compliance, provider failover), the Groq wire format, market-hours gating, and
endpoint auth gating. No network, DB, or API key is touched.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.ai import advice_filter, alert_writer
from app.ai.providers.base import LLMError, LLMProvider, LLMResponse, ToolSpec
from app.ai.providers.groq import GroqProvider
from app.main import app
from app.services import alert_service

client = TestClient(app)

_IST = timezone(timedelta(hours=5, minutes=30))


# ── rule evaluation (pure) ────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("observed", "operator", "threshold", "breached"),
    [
        (5_000.0, "gt", 4_000.0, True),
        (3_000.0, "gt", 4_000.0, False),
        (-2_500.0, "lt", -2_000.0, True),  # loss worse than limit
        (-1_500.0, "lt", -2_000.0, False),
        (-3_200.0, "abs_gt", 3_000.0, True),  # magnitude either direction
        (3_200.0, "abs_gt", 3_000.0, True),
        (2_800.0, "abs_gt", 3_000.0, False),
    ],
)
def test_rule_breached(observed, operator, threshold, breached):
    assert alert_service.rule_breached(observed, operator, threshold) is breached


def test_unknown_operator_raises():
    with pytest.raises(alert_service.AlertError):
        alert_service.rule_breached(1.0, "eq", 1.0)


def test_cooldown_window():
    now = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    recent = (now - timedelta(minutes=10)).isoformat()
    old = (now - timedelta(minutes=90)).isoformat()
    assert alert_service.in_cooldown(recent, 60, now)
    assert not alert_service.in_cooldown(old, 60, now)
    assert not alert_service.in_cooldown(None, 60, now)
    assert not alert_service.in_cooldown("not-a-date", 60, now)


def test_cooldown_handles_zulu_and_naive_timestamps():
    now = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    assert alert_service.in_cooldown("2026-07-02T11:55:00Z", 60, now)
    assert alert_service.in_cooldown("2026-07-02T11:55:00", 60, now)  # naive => UTC


# ── market-hours gate ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("when", "open_"),
    [
        (datetime(2026, 7, 1, 10, 30, tzinfo=_IST), True),  # Wed mid-session
        (datetime(2026, 7, 1, 9, 15, tzinfo=_IST), True),  # open bell
        (datetime(2026, 7, 1, 15, 30, tzinfo=_IST), True),  # close bell
        (datetime(2026, 7, 1, 9, 14, tzinfo=_IST), False),  # pre-open
        (datetime(2026, 7, 1, 15, 31, tzinfo=_IST), False),  # post-close
        (datetime(2026, 7, 4, 11, 0, tzinfo=_IST), False),  # Saturday
    ],
)
def test_is_market_hours(when, open_):
    assert alert_service.is_market_hours(when) is open_


# ── risk snapshot from the mock broker (no credentials, no network) ──────────
@pytest.fixture()
def mock_broker(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "broker", "mock")
    yield


async def test_snapshot_from_mock_book(mock_broker):
    snap = await alert_service.build_snapshot("user-1")
    # The demo book has 5 option legs across NIFTY + BANKNIFTY.
    assert snap.option_legs == 5
    assert snap.underlyings == ["BANKNIFTY", "NIFTY"]
    assert snap.skipped_underlyings == []
    assert snap.total_pnl is not None
    # Mock margin: 185k used / 315k available => 37% utilization.
    assert snap.margin_utilization_pct == pytest.approx(37.0)
    # Greeks priced off the mock chain (spot+IV available for both underlyings).
    assert snap.delta_rupees_per_pct is not None
    assert snap.theta_rupees_per_day is not None
    assert snap.vega_rupees_per_point is not None
    # A short-premium book stressed ±3/±5% must show a positive worst-case loss.
    assert snap.stress_loss_rupees is not None
    assert snap.stress_loss_rupees > 0


# ── alert phrasing: template fallback + compliance boundary ───────────────────
class _FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, text: str | None = None, error: bool = False) -> None:
        self._text = text
        self._error = error
        self.calls = 0

    async def complete(self, *, system, messages, tools) -> LLMResponse:
        self.calls += 1
        if self._error:
            raise LLMError("boom")
        return LLMResponse(text=self._text, tool_calls=[])


async def test_phrase_falls_back_to_template_when_no_provider():
    out = await alert_writer.phrase_alert(
        "Theta guard", "theta_rupees_per_day", "lt", -1_850.0, -1_500.0, providers=[]
    )
    assert not out.ai_phrased
    assert "Theta guard" in out.message
    assert "advice nahi" in out.message
    assert not advice_filter.is_advice(out.message)


async def test_phrase_uses_provider_when_clean():
    provider = _FakeProvider(text="Aapka theta ab ₹1,850 per day hai, limit ₹1,500 se zyada.")
    out = await alert_writer.phrase_alert(
        "Theta guard", "theta_rupees_per_day", "lt", -1_850.0, -1_500.0, providers=[provider]
    )
    assert out.ai_phrased
    assert "1,850" in out.message


async def test_phrase_advice_is_blocked_and_replaced_by_template():
    provider = _FakeProvider(text="Risk high hai — you should exit this position now!")
    out = await alert_writer.phrase_alert(
        "Delta cap", "delta_rupees_per_pct", "abs_gt", 4_200.0, 3_000.0, providers=[provider]
    )
    assert not out.ai_phrased  # compliance boundary replaced the model output
    assert "you should" not in out.message.lower()
    assert not advice_filter.is_advice(out.message)


async def test_phrase_fails_over_to_second_provider():
    broken = _FakeProvider(error=True)
    working = _FakeProvider(text="Margin utilization ab 82.0% hai, aapki limit 80% thi.")
    out = await alert_writer.phrase_alert(
        "Margin watch", "margin_utilization_pct", "gt", 82.0, 80.0, providers=[broken, working]
    )
    assert out.ai_phrased
    assert broken.calls == 1 and working.calls == 1


# ── Indian formatting helper ──────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (950.0, "₹950"),
        (12_34_567.0, "₹12.35 lakh"),
        (4_50_00_000.0, "₹4.50 crore"),
        (-1_850.0, "-₹1,850"),
        (12_345.0, "₹12,345"),
    ],
)
def test_fmt_inr(value, expected):
    assert alert_writer.fmt_inr(value) == expected


# ── Groq wire format (request build + response parse, no network) ─────────────
def test_groq_request_body():
    p = GroqProvider(api_key="k", model="llama-3.1-8b-instant")
    body = p.build_request_body(
        "sys", [{"role": "user", "content": "hi"}], [ToolSpec("t", "d", {"type": "object"})]
    )
    assert body["model"] == "llama-3.1-8b-instant"
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["messages"][1] == {"role": "user", "content": "hi"}
    assert body["tools"][0]["function"]["name"] == "t"


def test_groq_parse_text_and_tool_calls():
    data = {
        "choices": [
            {
                "message": {
                    "content": "ok",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {"name": "get_greeks", "arguments": '{"x": 1}'},
                        }
                    ],
                }
            }
        ]
    }
    resp = GroqProvider.parse_response(data)
    assert resp.text == "ok"
    assert resp.tool_calls[0].name == "get_greeks"
    assert resp.tool_calls[0].args == {"x": 1}
    assert GroqProvider.parse_response({}).text is None


# ── endpoint auth gating ──────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/alert-rules"),
        ("POST", "/alert-rules"),
        ("PATCH", "/alert-rules/x"),
        ("DELETE", "/alert-rules/x"),
        ("GET", "/alerts"),
        ("POST", "/alerts/x/ack"),
        ("POST", "/alerts/check"),
    ],
)
def test_alert_endpoints_require_auth(method, path):
    resp = client.request(method, path, json={})
    assert resp.status_code in (401, 403)
