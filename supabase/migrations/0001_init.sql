-- ════════════════════════════════════════════════════════════════════════════
-- Optera — initial schema (M1)
-- All app tables are RLS-scoped to auth.uid(). Broker access tokens are stored
-- ENCRYPTED by the engine (Fernet) before they ever reach this table.
-- ════════════════════════════════════════════════════════════════════════════

create extension if not exists "pgcrypto";

-- ── Enums ────────────────────────────────────────────────────────────────────
do $$ begin
  create type broker_kind as enum ('upstox', 'kite', 'dhan', 'angel');
exception when duplicate_object then null; end $$;

do $$ begin
  create type connection_status as enum ('active', 'expired', 'revoked', 'error');
exception when duplicate_object then null; end $$;

do $$ begin
  create type language_pref as enum ('hinglish', 'english', 'hindi');
exception when duplicate_object then null; end $$;

do $$ begin
  create type alert_kind as enum (
    'delta_flip', 'theta_burn', 'margin_proximity', 'position_limit_proximity',
    'adverse_move', 'iv_spike', 'expiry_reminder'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type subscription_plan as enum ('free', 'pro', 'pro_plus');
exception when duplicate_object then null; end $$;

-- ── profiles (1:1 with auth.users) ───────────────────────────────────────────
create table if not exists public.profiles (
  id                          uuid primary key references auth.users (id) on delete cascade,
  display_name                text,
  language_pref               language_pref not null default 'hinglish',
  notification_channel        text,
  risk_disclosure_accepted_at timestamptz,
  created_at                  timestamptz not null default now(),
  updated_at                  timestamptz not null default now()
);

-- ── broker_connections ───────────────────────────────────────────────────────
create table if not exists public.broker_connections (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users (id) on delete cascade,
  broker              broker_kind not null default 'upstox',
  api_key             text,
  access_token_enc    text,          -- ENCRYPTED daily OAuth token (engine-only)
  analytics_token_enc text,          -- ENCRYPTED one-time analytics token (engine-only)
  public_token        text,
  status              connection_status not null default 'active',
  connected_at        timestamptz not null default now(),
  expires_at          timestamptz
);

-- ── positions_snapshots ──────────────────────────────────────────────────────
create table if not exists public.positions_snapshots (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references auth.users (id) on delete cascade,
  taken_at             timestamptz not null default now(),
  raw_jsonb            jsonb not null,
  computed_greeks_jsonb jsonb,
  net_pnl              numeric
);
create index if not exists idx_snapshots_user_time on public.positions_snapshots (user_id, taken_at desc);

-- ── instruments_cache (shared reference data, read-only to clients) ───────────
create table if not exists public.instruments_cache (
  instrument_token text primary key,
  tradingsymbol    text not null,
  name             text,
  expiry           date,
  strike           numeric,
  type             text,           -- CE / PE / FUT / EQ
  lot_size         integer,
  exch             text,
  updated_at       timestamptz not null default now()
);
create index if not exists idx_instruments_symbol on public.instruments_cache (tradingsymbol);

-- ── alert_rules ──────────────────────────────────────────────────────────────
create table if not exists public.alert_rules (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  type        alert_kind not null,
  params_jsonb jsonb not null default '{}'::jsonb,
  channels    text[] not null default '{}',
  enabled     boolean not null default true,
  created_at  timestamptz not null default now()
);

-- ── alerts_log ───────────────────────────────────────────────────────────────
create table if not exists public.alerts_log (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users (id) on delete cascade,
  rule_id      uuid references public.alert_rules (id) on delete set null,
  fired_at     timestamptz not null default now(),
  payload_jsonb jsonb,
  message      text,
  channel      text,
  delivered    boolean not null default false
);
create index if not exists idx_alerts_user_time on public.alerts_log (user_id, fired_at desc);

-- ── chat_sessions / chat_messages ────────────────────────────────────────────
create table if not exists public.chat_sessions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  title      text,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id              uuid primary key default gen_random_uuid(),
  session_id      uuid not null references public.chat_sessions (id) on delete cascade,
  user_id         uuid not null references auth.users (id) on delete cascade,
  role            text not null,            -- user / assistant / tool / system
  content         text,
  tool_calls_jsonb jsonb,
  created_at      timestamptz not null default now()
);
create index if not exists idx_messages_session on public.chat_messages (session_id, created_at);

-- ── journal_trades ───────────────────────────────────────────────────────────
create table if not exists public.journal_trades (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users (id) on delete cascade,
  opened_at    timestamptz,
  closed_at    timestamptz,
  legs_jsonb   jsonb not null,
  realized_pnl numeric,
  ai_review    text
);

-- ── watchlists ───────────────────────────────────────────────────────────────
create table if not exists public.watchlists (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  instruments text[] not null default '{}',
  created_at  timestamptz not null default now()
);

-- ── subscriptions ────────────────────────────────────────────────────────────
create table if not exists public.subscriptions (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users (id) on delete cascade,
  plan                subscription_plan not null default 'free',
  status              text not null default 'active',
  razorpay_sub_id     text,
  current_period_end  timestamptz
);

-- ── ai_usage (per-day metering for rate limiting / cost) ──────────────────────
create table if not exists public.ai_usage (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  day        date not null default current_date,
  tokens_in  bigint not null default 0,
  tokens_out bigint not null default 0,
  calls      integer not null default 0,
  unique (user_id, day)
);

-- ════════════════════════════════════════════════════════════════════════════
-- Row Level Security
-- ════════════════════════════════════════════════════════════════════════════
alter table public.profiles            enable row level security;
alter table public.broker_connections  enable row level security;
alter table public.positions_snapshots enable row level security;
alter table public.alert_rules         enable row level security;
alter table public.alerts_log          enable row level security;
alter table public.chat_sessions       enable row level security;
alter table public.chat_messages       enable row level security;
alter table public.journal_trades      enable row level security;
alter table public.watchlists          enable row level security;
alter table public.subscriptions       enable row level security;
alter table public.ai_usage            enable row level security;
alter table public.instruments_cache   enable row level security;

-- Owner-only policies (one helper pattern per table on user_id = auth.uid()).
do $$
declare t text;
begin
  foreach t in array array[
    'profiles','broker_connections','positions_snapshots','alert_rules','alerts_log',
    'chat_sessions','chat_messages','journal_trades','watchlists','subscriptions','ai_usage'
  ]
  loop
    -- profiles keys on id; everything else on user_id. Handle profiles separately below.
    if t <> 'profiles' then
      execute format($f$
        create policy %1$s_select on public.%1$s for select using (user_id = auth.uid());
        create policy %1$s_insert on public.%1$s for insert with check (user_id = auth.uid());
        create policy %1$s_update on public.%1$s for update using (user_id = auth.uid()) with check (user_id = auth.uid());
        create policy %1$s_delete on public.%1$s for delete using (user_id = auth.uid());
      $f$, t);
    end if;
  end loop;
end $$;

create policy profiles_select on public.profiles for select using (id = auth.uid());
create policy profiles_insert on public.profiles for insert with check (id = auth.uid());
create policy profiles_update on public.profiles for update using (id = auth.uid()) with check (id = auth.uid());

-- instruments_cache is shared reference data: readable by any authenticated user,
-- writable only by the service role (engine), which bypasses RLS.
create policy instruments_select on public.instruments_cache for select using (auth.role() = 'authenticated');

-- ── auto-create a profile row on signup ──────────────────────────────────────
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', new.email))
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
