"""Co-pilot orchestration: system prompt + generic tool-call loop + advice filter.

The loop is provider-agnostic — it speaks only the neutral message schema from
`providers.base`, so swapping Gemini for another vendor needs no changes here.
Every final answer passes through the advice filter (compliance boundary).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.ai import advice_filter, tools
from app.ai.gateway import chat_providers
from app.ai.providers.base import LLMError, LLMProvider
from app.ai.tools import StrategyContext

MAX_STEPS = 5  # tool-call rounds before we force a textual answer

SYSTEM_PROMPT = (
    "You are Optera, an options risk-analytics and education co-pilot for Indian retail "
    "F&O traders. You explain risk in clear, friendly Hinglish (Hindi-English mix).\n\n"
    "HARD RULES — these are non-negotiable:\n"
    "1. You give EDUCATION and ANALYTICS only. NEVER recommend buy/sell/hold, entry/exit, "
    "price targets, stop-losses, or predict market direction. If asked, politely refuse and "
    "redirect to analyzing the user's existing structure.\n"
    "2. NEVER invent numbers. For any Greeks, payoff, P&L, breakevens or probabilities, CALL "
    "the provided tools and use their results. The tools run on the user's current structure.\n"
    "3. Use ₹ and Indian conventions (lakh/crore). Keep answers concise and plain.\n"
    "4. You are not a SEBI-registered advisor; you analyze, you don't advise.\n\n"
    "Explain what the numbers MEAN for the user's risk (e.g. 'theta aapko roz ₹X kha raha hai'), "
    "never what they should DO about it."
)


@dataclass
class ChatReply:
    reply: str
    flagged: bool  # True if the advice filter had to replace the model's output


def _to_neutral(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map inbound {role, content} chat history to the neutral provider schema."""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        out.append({"role": role, "content": m.get("content", "")})
    return out


async def run_chat(
    messages: list[dict[str, Any]],
    ctx: StrategyContext | None,
    *,
    providers: list[LLMProvider] | None = None,
) -> ChatReply:
    """Drive one assistant response: tool loop until text, then filter it."""
    provider = _select_provider(providers if providers is not None else chat_providers())
    convo = _to_neutral(messages)

    for _ in range(MAX_STEPS):
        resp = await provider.complete(
            system=SYSTEM_PROMPT, messages=convo, tools=tools.TOOL_SPECS
        )
        if resp.tool_calls:
            convo.append({"role": "model", "content": resp.text, "tool_calls": resp.tool_calls})
            for call in resp.tool_calls:
                result = tools.dispatch(ctx, call.name, call.args)
                convo.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": json.dumps(result),
                    }
                )
            continue

        text, flagged = advice_filter.screen(resp.text or "")
        return ChatReply(reply=text, flagged=flagged)

    # Tool loop didn't converge to a textual answer.
    return ChatReply(
        reply="Sorry, main is sawaal ka jawaab abhi process nahi kar paaya. Thoda rephrase karein?",
        flagged=False,
    )


def _select_provider(providers: list[LLMProvider]) -> LLMProvider:
    if not providers:
        raise LLMError("No chat provider configured.")
    return providers[0]
