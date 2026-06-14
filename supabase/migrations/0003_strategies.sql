-- ════════════════════════════════════════════════════════════════════════════
-- Optera — saved paper strategies (M9)
-- Hypothetical option structures a user saves from the Risk workbench. Pure
-- user-owned data: written directly from the web client under RLS (the engine
-- is not involved). No orders, no advice — analytics/education only.
-- ════════════════════════════════════════════════════════════════════════════

create table if not exists public.strategies (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  name       text not null,
  spot       numeric not null,
  iv_pct     numeric not null default 14,
  dte        numeric not null default 7,
  legs_jsonb jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_strategies_user_time
  on public.strategies (user_id, created_at desc);

-- ── Row Level Security (owner-only, same pattern as the rest of the schema) ────
alter table public.strategies enable row level security;

create policy strategies_select on public.strategies
  for select using (user_id = auth.uid());
create policy strategies_insert on public.strategies
  for insert with check (user_id = auth.uid());
create policy strategies_update on public.strategies
  for update using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy strategies_delete on public.strategies
  for delete using (user_id = auth.uid());
