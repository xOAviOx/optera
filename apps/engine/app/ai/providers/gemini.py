"""Gemini provider (generativelanguage REST, function calling).

Wire format pinned to the official docs:
  - request: {contents, tools:[{functionDeclarations}], system_instruction}
  - model tool call: candidates[0].content.parts[].functionCall {name, id, args}
  - tool result is sent back as a `user` turn with a functionResponse part
  - valid content roles are only "user" and "model"
See https://ai.google.dev/gemini-api/docs/function-calling.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.ai.providers.base import LLMError, LLMProvider, LLMResponse, ToolCall, ToolSpec

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, base_url: str = DEFAULT_BASE_URL) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    # ── neutral -> Gemini ──────────────────────────────────────────────────────
    def _to_contents(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        contents: list[dict[str, Any]] = []
        for m in messages:
            role = m["role"]
            if role == "user":
                contents.append({"role": "user", "parts": [{"text": m.get("content") or ""}]})
            elif role in ("assistant", "model"):
                parts: list[dict[str, Any]] = []
                if m.get("content"):
                    parts.append({"text": m["content"]})
                for tc in m.get("tool_calls", []):
                    parts.append(
                        {"functionCall": {"name": tc.name, "id": tc.id, "args": tc.args}}
                    )
                contents.append({"role": "model", "parts": parts or [{"text": ""}]})
            elif role == "tool":
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": m.get("name", ""),
                                    "id": m.get("tool_call_id", ""),
                                    "response": {"result": m.get("content") or ""},
                                }
                            }
                        ],
                    }
                )
        return contents

    @staticmethod
    def _to_function_declarations(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in tools
        ]

    def build_request_body(
        self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"contents": self._to_contents(messages)}
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = [{"functionDeclarations": self._to_function_declarations(tools)}]
        return body

    # ── Gemini -> neutral ──────────────────────────────────────────────────────
    @staticmethod
    def parse_response(data: dict[str, Any]) -> LLMResponse:
        candidates = data.get("candidates") or []
        if not candidates:
            return LLMResponse(text=None, tool_calls=[])
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text_chunks: list[str] = []
        calls: list[ToolCall] = []
        for part in parts:
            if "functionCall" in part:
                fc = part["functionCall"]
                calls.append(
                    ToolCall(
                        id=fc.get("id") or uuid.uuid4().hex,
                        name=fc.get("name", ""),
                        args=fc.get("args") or {},
                    )
                )
            elif "text" in part:
                text_chunks.append(part["text"])
        return LLMResponse(text="".join(text_chunks) or None, tool_calls=calls)

    async def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> LLMResponse:
        url = f"{self._base_url}/models/{self._model}:generateContent"
        body = self.build_request_body(system, messages, tools)
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": self._api_key,  # key in header, never logged
                    },
                    json=body,
                )
                resp.raise_for_status()
                return self.parse_response(resp.json())
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"Gemini API error {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc
