"""LLM gateway: build providers from env config (never hardcoded).

All model calls route through here so providers/models are swappable and we get
failover: chat prefers the chat provider (default Gemini) and falls back to the
alert provider; alert phrasing (M8) prefers the alert provider (default Groq)
and falls back to the chat provider. A role returns every configured provider,
in preference order — callers try them in sequence.
"""

from __future__ import annotations

from app.ai.providers.base import LLMNotConfigured, LLMProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.groq import GroqProvider
from app.config import get_settings


def build_provider(kind: str, model: str) -> LLMProvider:
    s = get_settings()
    if kind == "gemini":
        if not s.gemini_api_key:
            raise LLMNotConfigured("GEMINI_API_KEY is not set — Gemini is unavailable.")
        return GeminiProvider(api_key=s.gemini_api_key, model=model)
    if kind == "groq":
        if not s.groq_api_key:
            raise LLMNotConfigured("GROQ_API_KEY is not set — Groq is unavailable.")
        return GroqProvider(api_key=s.groq_api_key, model=model)
    raise LLMNotConfigured(f"Unsupported LLM provider {kind!r}")


def _providers_in_order(pairs: list[tuple[str, str]]) -> list[LLMProvider]:
    """Build every configured provider from (kind, model) pairs, skipping dupes
    and unconfigured ones. Order = preference order (failover)."""
    out: list[LLMProvider] = []
    seen: set[str] = set()
    for kind, model in pairs:
        if kind in seen:
            continue
        try:
            out.append(build_provider(kind, model))
            seen.add(kind)
        except LLMNotConfigured:
            continue
    return out


def chat_providers() -> list[LLMProvider]:
    """Ordered providers for chat/tool-calling. First that works wins (failover)."""
    s = get_settings()
    providers = _providers_in_order(
        [(s.ai_chat_provider, s.ai_chat_model), (s.ai_alert_provider, s.ai_alert_model)]
    )
    if not providers:
        raise LLMNotConfigured(
            "No chat provider configured (set GEMINI_API_KEY or GROQ_API_KEY)."
        )
    return providers


def alert_providers() -> list[LLMProvider]:
    """Ordered providers for alert phrasing (M8). May be empty — alert delivery
    never depends on an LLM; callers fall back to a deterministic template."""
    s = get_settings()
    return _providers_in_order(
        [(s.ai_alert_provider, s.ai_alert_model), (s.ai_chat_provider, s.ai_chat_model)]
    )
