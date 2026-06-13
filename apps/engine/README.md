# Optera Engine

FastAPI service: broker adapters, quant core, realtime risk stream, AI orchestration.
**Education/analytics only — no order placement, no advice.**

## Run

```bash
cd apps/engine
cp ../../.env.example .env        # fill in secrets
uv sync                            # install deps (creates .venv)
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the OpenAPI UI, http://localhost:8000/health for health.

## Test

```bash
uv run pytest -q
```

## Layout

```
app/
  main.py        FastAPI app + /health
  api.py         §6 endpoint contract (stubs return 501 until their module lands)
  config.py      env-driven settings (pydantic-settings)
  models.py      Pydantic schemas (mirror packages/types)
  quant/         BS / IV / Greeks / payoff / scenario / POP  (M3)
  brokers/       adapter ABC + Upstox (default, free)         (M2+)
tests/           pytest; quant needs textbook reference cases
```
