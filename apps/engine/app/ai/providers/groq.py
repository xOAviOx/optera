"""Groq provider (OpenAI-compatible chat completions).

Used for high-frequency, cheap alert phrasing (M8) and as chat failover.
Wire format pinned to Groq's OpenAI-compatible endpoint:
  POST {base}/chat/completions
  - system prompt is the first message with role "system"
  - model tool call: choices[0].message.tool_calls[].function {name, arguments(JSON str)}
  - tool result is sent back as {"role": "tool", "tool_call_id", "content"}
See https://console.groq.com/docs/api-reference#chat.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from app.ai.providers.base import LLMError, LLMProvider, LLMResponse, ToolCall, ToolSpec

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str, base_url: str = DEFAULT_BASE_URL) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    # ── neutral -> OpenAI-compatible ──────────────────────────────────────────
    @staticmethod
    def _to_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            role = m["role"]
            if role == "user":
                out.append({"role": "user", "content": m.get("content") or ""})
            elif role in ("assistant", "model"):
                entry: dict[str, Any] = {"role": "assistant", "content": m.get("content")}
                calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.args)},
                    }
                    for tc in m.get("tool_calls", [])
                ]
                if calls:
                    entry["tool_calls"] = calls
                out.append(entry)
            elif role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.get("tool_call_id", ""),
                        "content": m.get("content") or "",
                    }
                )
        return out

    @staticmethod
    def _to_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def build_request_body(
        self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": self._to_messages(system, messages),
        }
        if tools:
            body["tools"] = self._to_tools(tools)
        return body

    # ── OpenAI-compatible -> neutral ──────────────────────────────────────────
    @staticmethod
    def parse_response(data: dict[str, Any]) -> LLMResponse:
        choices = data.get("choices") or []
        if not choices:
            return LLMResponse(text=None, tool_calls=[])
        message = choices[0].get("message") or {}
        calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(
                ToolCall(
                    id=tc.get("id") or uuid.uuid4().hex,
                    name=fn.get("name", ""),
                    args=args if isinstance(args, dict) else {},
                )
            )
        return LLMResponse(text=message.get("content") or None, tool_calls=calls)

    async def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> LLMResponse:
        url = f"{self._base_url}/chat/completions"
        body = self.build_request_body(system, messages, tools)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}",  # never logged
                    },
                    json=body,
                )
                resp.raise_for_status()
                return self.parse_response(resp.json())
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"Groq API error {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Groq request failed: {exc}") from exc
