"""Tests for the AI co-pilot (M7), fully offline.

Covers the compliance advice filter (the security boundary), the tool dispatch
math, the provider-agnostic tool loop (with a fake provider), the Gemini wire
format, and endpoint auth gating. No network or API key is touched.
"""

import pytest
from fastapi.testclient import TestClient

from app.ai import advice_filter, copilot, tools
from app.ai.providers.base import LLMResponse, ToolCall, ToolSpec
from app.ai.providers.gemini import GeminiProvider
from app.ai.tools import StrategyContext
from app.main import app
from app.models import Leg, OptionType, Side

client = TestClient(app)


def _leg(option_type: OptionType, strike: int) -> Leg:
    return Leg(
        symbol="L", option_type=option_type, strike=strike, side=Side.BUY, lots=1, lot_size=75
    )


def _straddle() -> StrategyContext:
    legs = [_leg(OptionType.CALL, 23500), _leg(OptionType.PUT, 23500)]
    return StrategyContext(legs=legs, spot=23500, iv_pct=14, dte=7)


# ── advice filter (compliance boundary) ───────────────────────────────────────
@pytest.mark.parametrize(
    "text",
    [
        "You should buy the 23500 call now.",
        "I recommend selling this put.",
        "My recommendation is to hold.",
        "NIFTY will reach 24000 next week.",
        "Set a stop-loss at 23200.",
        "The index is likely to rally tomorrow.",
        "Book your profit here.",
    ],
)
def test_advice_is_flagged(text):
    assert advice_filter.is_advice(text)
    safe, flagged = advice_filter.screen(text)
    assert flagged
    assert safe == advice_filter.SAFE_REPLACEMENT


@pytest.mark.parametrize(
    "text",
    [
        "Your net delta is bullish: about ₹1,200 per 1% move in NIFTY.",
        "If NIFTY rises, your long call gains delta while the put loses value.",
        "Theta is costing this book about ₹1,000 per day.",
        "A long straddle profits if the underlying moves far in either direction.",
        "Your breakevens are 23,136 and 23,864.",
    ],
)
def test_education_is_not_flagged(text):
    assert not advice_filter.is_advice(text)
    safe, flagged = advice_filter.screen(text)
    assert not flagged
    assert safe == text


# ── tool dispatch (real quant math) ───────────────────────────────────────────
def test_payoff_summary_tool():
    out = tools.dispatch(_straddle(), "get_payoff_summary", {})
    assert out["max_loss"] < 0  # long straddle pays a debit
    assert len(out["breakevens"]) == 2
    assert 0.0 <= out["probability_of_profit"] <= 1.0


def test_what_if_tool_returns_pnl_and_greeks():
    out = tools.dispatch(_straddle(), "run_what_if", {"spot_move_pct": 3, "iv_change_pts": 0})
    assert "pnl_delta" in out
    assert out["new_greeks"]["delta_direction"] in ("bullish", "bearish", "neutral")


def test_dispatch_without_context_is_safe():
    out = tools.dispatch(None, "get_greeks", {})
    assert "error" in out


# ── tool loop with a fake provider ────────────────────────────────────────────
class FakeProvider:
    """Returns a queued list of LLMResponses, one per `complete` call."""

    name = "fake"

    def __init__(self, responses):
        self._responses = list(responses)
        self.tool_specs_seen: list[ToolSpec] = []

    async def complete(self, *, system, messages, tools):  # noqa: A002 - mirrors interface
        self.tool_specs_seen = tools
        return self._responses.pop(0)


async def test_run_chat_executes_tool_then_answers():
    call = ToolCall(id="c1", name="get_payoff_summary", args={})
    provider = FakeProvider(
        [
            LLMResponse(text=None, tool_calls=[call]),
            LLMResponse(text="Max loss ~26k, breakevens 23136/23864.", tool_calls=[]),
        ]
    )
    reply = await copilot.run_chat(
        [{"role": "user", "content": "explain my risk"}], _straddle(), providers=[provider]
    )
    assert not reply.flagged
    assert "max loss" in reply.reply.lower()
    assert any(t.name == "get_payoff_summary" for t in provider.tool_specs_seen)


async def test_run_chat_filters_advice_output():
    provider = FakeProvider([LLMResponse(text="You should buy more calls now.", tool_calls=[])])
    reply = await copilot.run_chat(
        [{"role": "user", "content": "what do I do?"}], _straddle(), providers=[provider]
    )
    assert reply.flagged
    assert reply.reply == advice_filter.SAFE_REPLACEMENT


# ── Gemini wire format ────────────────────────────────────────────────────────
def test_gemini_request_body_shape():
    g = GeminiProvider(api_key="x", model="gemini-2.5-flash")
    tc = ToolCall(id="c1", name="t", args={"a": 1})
    body = g.build_request_body(
        system="be helpful",
        messages=[
            {"role": "user", "content": "hi"},
            {"role": "model", "content": None, "tool_calls": [tc]},
            {"role": "tool", "tool_call_id": "c1", "name": "t", "content": '{"ok": true}'},
        ],
        tools=[ToolSpec(name="t", description="d", parameters={"type": "object"})],
    )
    assert body["system_instruction"]["parts"][0]["text"] == "be helpful"
    assert body["tools"][0]["functionDeclarations"][0]["name"] == "t"
    roles = [c["role"] for c in body["contents"]]
    assert roles == ["user", "model", "user"]  # tool result rides back as a user turn
    assert body["contents"][1]["parts"][0]["functionCall"]["name"] == "t"
    assert body["contents"][2]["parts"][0]["functionResponse"]["id"] == "c1"


def test_gemini_parse_function_call_and_text():
    part = {"functionCall": {"name": "t", "args": {"x": 1}}}
    fc_resp = GeminiProvider.parse_response({"candidates": [{"content": {"parts": [part]}}]})
    assert fc_resp.tool_calls[0].name == "t"
    assert fc_resp.tool_calls[0].id  # synthesized when absent

    text_resp = GeminiProvider.parse_response(
        {"candidates": [{"content": {"parts": [{"text": "namaste"}]}}]}
    )
    assert text_resp.text == "namaste"
    assert not text_resp.tool_calls


# ── endpoint auth gating ──────────────────────────────────────────────────────
def test_ai_chat_requires_auth():
    res = client.post("/ai/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert res.status_code == 401
