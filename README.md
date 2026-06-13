# Optera — AI Options Risk & Analytics Co-Pilot

> See your F&O risk clearly. Optera connects (read-only) to an Indian retail trader's broker,
> reads live positions, computes real-time risk (Greeks, payoff, scenarios), and gives an AI
> co-pilot that **explains and monitors** that risk in plain Hinglish.
>
> **Education & analytics only — never buy/sell advice. Read-only broker access in v1.**

## Monorepo layout

```
optera/
├─ apps/
│  ├─ web/      Next.js 15 (App Router, TS, Tailwind, shadcn). Dark theme default.
│  └─ engine/   Python 3.12 FastAPI — quant + realtime + AI orchestration (uv).
├─ packages/
│  ├─ types/    Shared TS types (mirror engine Pydantic models).
│  ├─ ui/       Shared components (incl. the compliance Disclaimer).
│  └─ config/   Shared tsconfig base.
├─ supabase/migrations/   Postgres schema (RLS-scoped to user_id).
└─ CLAUDE.md    Build rules.
```

## Prerequisites

- Node ≥ 20 (repo pins 22 via `.nvmrc`), **pnpm**
- **uv** (Python 3.12) for the engine
- Accounts (all free tier): Supabase, Upstash Redis, Upstox API, Gemini, Groq

## Setup

```bash
# 1. JS workspaces (web + shared packages)
pnpm install

# 2. Env
cp .env.example apps/web/.env.local     # fill NEXT_PUBLIC_* + Supabase
cp .env.example apps/engine/.env        # fill engine secrets

# 3. Python engine
cd apps/engine && uv sync && cd ../..
```

## Run (two processes)

```bash
pnpm engine:dev    # FastAPI on :8000  (uv run uvicorn app.main:app --reload)
pnpm dev           # Next.js  on :3000  (turbo)
```

- Web: http://localhost:3000
- Engine health: http://localhost:8000/health · API docs: http://localhost:8000/docs

## Test

```bash
pnpm engine:test   # pytest (quant gets textbook reference cases in M3)
```

## Build status

M1 **Scaffold** ✅ — monorepo, web shell (dark, nav, dashboard), FastAPI skeleton with the §6
API contract stubbed, Supabase schema + RLS, env wiring.

Next: **M2** Auth + Upstox broker connect. See `CLAUDE.md` §10 for the full plan.
