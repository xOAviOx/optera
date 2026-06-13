# Optera — build rules for Claude Code

> Optera is an AI **options risk-analytics & education** co-pilot for Indian retail F&O
> traders. It connects (read-only) to a broker, reads live positions, computes risk
> (Greeks/payoff/scenarios), and explains/monitors that risk in plain Hinglish.
> **It never gives buy/sell advice.**

## Hard product constraints (these shape everything)

1. **Education & analytics ONLY. No advice.** Never recommend buy/sell/hold, entry/exit,
   price targets, or direction predictions. Enforced in the AI system prompt, a server-side
   advice filter, and UI copy. Treat it as a security boundary.
2. **Read-only broker access in v1. No order placement.** Strategy builder is hypothetical/
   paper only.
3. **India-first, ₹0/month to run.** Default broker = Upstox (free). Currency ₹.
   Market hours 09:15–15:30 IST. Disclaimers on every output surface.

## Architecture

- Monorepo: **Turborepo + pnpm**.
  - `apps/web` — Next 15 (App Router, TS, Tailwind, shadcn/ui). Dark theme default.
  - `apps/engine` — Python 3.12, FastAPI, managed with **uv**. Quant + realtime + AI orchestration.
  - `packages/types` — shared TS types (mirror engine Pydantic models).
  - `packages/ui` — shared shadcn components.
  - `packages/config` — shared tsconfig / lint config.
- `apps/engine` is a Python project, **not** a pnpm workspace member. Run it via `uv`.

## Engineering rules

- **Quant code MUST have unit tests with textbook reference values before use.**
  Tests live in `apps/engine/tests/`. `pytest` must be green before quant code is relied on.
- **Never log or expose broker access tokens.** Tokens live only in the engine, encrypted
  (libsodium/Fernet) with a server-side key. Never sent to the client.
- **Compliance:** NO order placement, NO buy/sell advice anywhere. Education only.
- **AI:** route ALL model calls through ONE LLM gateway (LiteLLM or thin router).
  - Chat / tool-calling = **Gemini 3 Flash** (free tier).
  - Alert phrasing = **Groq `llama-3.1-8b-instant`** (free tier).
  - Provider + model are **env config, never hardcoded**. Build failover. Tool-call loop is
    generic so providers are swappable.
- **Supabase:** all tables RLS-scoped to `user_id`. Migrations in `supabase/migrations/`.
- **Frontend:** dark theme default, mobile-responsive, small + typed components.
- **Indian formatting:** ₹, lakh/crore, IST, NSE conventions.
- **Secrets:** never hardcode. Use env vars. Keep `.env.example` current.

## Broker (Upstox) specifics

- Two tokens: the **daily OAuth access token** reads the user's positions/holdings (read-only);
  the **one-time analytics token** (no daily re-auth) powers market-data + websocket streaming.
  Use the analytics token for the live feed so data never breaks at 6 AM.
- Market-data websocket is **protobuf-encoded binary** — decode with Upstox's `.proto`.
- Option Chain API already returns IV + Greeks + OI; still compute our own portfolio-aggregate
  Greeks and scenario repricing in the quant core.
- Keep brokers behind an **adapter** (`apps/engine/app/brokers/`) so Kite/Dhan/Angel plug in later.

## Build plan (one module per session)

M1 Scaffold · M2 Auth+broker · M3 Quant core (+tests) · M4 Live positions+WS ·
M5 Risk visuals · M6 Chain+IV · M7 AI co-pilot · M8 Monitoring+alerts ·
M9 Journal+strategy · M10 Compliance+billing.
