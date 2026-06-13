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

- M1 **Scaffold** ✅ — monorepo, web shell (dark, nav, dashboard + placeholder routes),
  FastAPI skeleton with the §6 API contract, Supabase schema + RLS, env wiring.
- M3 **Quant core** ✅ — Black-Scholes (generalized, b-carry), Brent/Newton IV solver,
  Greeks, payoff, scenario, POP (lognormal + Monte Carlo). 40 textbook-referenced tests.
  Live endpoints: `POST /payoff`, `/scenario`, `/pop`.
- M2 **Auth + broker connect** ✅ — Supabase auth (Google + email, session middleware),
  Fernet-encrypted broker tokens, Supabase JWT verification, Upstox OAuth
  (`/broker/upstox/login-url`, `/auth/broker/connect`, `/broker/analytics-token`,
  `/broker/status`), onboarding wizard with risk-disclosure gating. Degrades gracefully
  until Supabase/Upstox keys are set. 53 engine tests.

### Configuring auth + broker (to exercise M2 end-to-end)

1. Create a **Supabase** project → copy URL + anon key → `apps/web/.env.local`; copy the
   service-role key + JWT secret → `apps/engine/.env`. Run `supabase/migrations/*.sql`.
2. Enable **Google** provider in Supabase Auth (optional) and set the redirect to
   `<web>/auth/callback`.
3. Create an **Upstox** API app → API key/secret + redirect URI
   `<web>/auth/broker/callback` → `apps/engine/.env`.
4. Generate `TOKEN_ENCRYPTION_KEY`:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

Next: **M4** Live positions + WS stream (ticker ingestion, normalized positions, live risk push).
