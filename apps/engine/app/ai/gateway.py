"""LLM gateway: build providers from env config (never hardcoded).

All model calls route through here so providers/models are swappable and we can
add failover by returning an ordered provider list. Chat/tool-calling uses the
configured chat provider (default Gemini); alert phrasing will use the alert
provider (Groq) in M8.
"""

from __future__ import annotations

from app.ai.providers.base import LLMNotConfigured, LLMProvider
from app.ai.providers.gemini import GeminiProvider
from app.config import get_settings


def build_provider(kind: str, model: str) -> LLMProvider:
    s = get_settings()
    if kind == "gemini":
        if not s.gemini_api_key:
            raise LLMNotConfigured("GEMINI_API_KEY is not set — AI co-pilot is unavailable.")
        return GeminiProvider(api_key=s.gemini_api_key, model=model)
    # Groq (and others) plug in here as they're needed.
    raise LLMNotConfigured(f"Unsupported chat provider {kind!r}")


def chat_providers() -> list[LLMProvider]:
    """Ordered providers for chat/tool-calling. First that works wins (failover)."""
    s = get_settings()
    return [build_provider(s.ai_chat_provider, s.ai_chat_model)]
