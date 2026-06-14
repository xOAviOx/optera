"""Neutral LLM interface the co-pilot programs against.

Messages use a small provider-agnostic schema (list of dicts):
  {"role": "user",   "content": str}
  {"role": "model",  "content": str | None, "tool_calls": [ToolCall]}
  {"role": "tool",   "tool_call_id": str, "name": str, "content": str}
Each provider translates this to/from its own wire format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMError(RuntimeError):
    """Upstream model call failed (network / API error)."""


class LLMNotConfigured(LLMError):
    """No API key / provider configured for the requested model role."""


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
    ) -> LLMResponse:
        """One model turn: returns either text, tool calls, or both."""
