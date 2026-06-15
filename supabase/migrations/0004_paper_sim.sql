-- ════════════════════════════════════════════════════════════════════════════
-- Optera — paper-trading simulator (M-sim)
-- A hypothetical/paper account: synthetic cash, positions opened/closed against a
-- deterministic simulated market. NO real orders, NO advice — education only.
-- The engine writes these via the service role (server-authoritative fills); RLS
-- still scopes everything to the owner for defense-in-depth + any direct reads.
-- ════════════════════════════════════════════════════════════════════════════

-- One paper account per user.
create table if not exists public.paper_accounts (
  user_id      uuid primary key references auth.users (id) on delete cascade,
  capital      numeric not null default 500000,  -- starting paper capital (₹)
  cash         numeric not null default 500000,
  realized_pnl numeric not null default 0,
  clock_tick   bigint  not null default 0,        -- last sim tick seen
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table if not exists public.paper_positions (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users (id) on delete cascade,
  symbol       text not null,                      -- NIFTY / BANKNIFTY
  option_type  text not null,                      -- CE / PE
  strike       numeric not null,
  side         text not null,                      -- BUY / SELL
  lots         integer not null,
  lot_size     integer not null,
  entry_tick   bigint  not null,
  entry_spot   numeric not null,
  entry_price  numeric not null,                   -- fill premium per contract
  expiry_tick  bigint  not null,
  status       text not null default 'open',       -- open / closed
  exit_tick    bigint,
  exit_spot    numeric,
  exit_price   numeric,
  realized_pnl numeric,
  opened_at    timestamptz not null default now(),
  closed_at    timestamptz
);

create index if not exists idx_paper_positions_user_status
  on public.paper_positions (user_id, status, opened_at desc);

-- ── Row Level Security (owner-only, same pattern as the rest of the schema) ────
alter table public.paper_accounts enable row level security;
alter table public.paper_positions enable row level security;

create policy paper_accounts_select on public.paper_accounts
  for select using (user_id = auth.uid());
create policy paper_accounts_insert on public.paper_accounts
  for insert with check (user_id = auth.uid());
create policy paper_accounts_update on public.paper_accounts
  for update using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy paper_accounts_delete on public.paper_accounts
  for delete using (user_id = auth.uid());

create policy paper_positions_select on public.paper_positions
  for select using (user_id = auth.uid());
create policy paper_positions_insert on public.paper_positions
  for insert with check (user_id = auth.uid());
create policy paper_positions_update on public.paper_positions
  for update using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy paper_positions_delete on public.paper_positions
  for delete using (user_id = auth.uid());
