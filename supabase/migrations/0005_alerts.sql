-- ════════════════════════════════════════════════════════════════════════════
-- Optera — monitoring + alerts (M8)
--
-- Replaces the never-used M1 placeholders (alert_rules with an alert_kind enum,
-- alerts_log) with the real M8 shape: user-defined threshold rules on risk
-- metrics, evaluated server-side by the engine against the live risk snapshot.
-- The placeholders were created in 0001 but no code ever wrote to them (the M8
-- endpoints were 501 stubs), so dropping them loses nothing.
--
-- Alert messages are phrased by AI (education-only, advice-filtered) with a
-- deterministic fallback. No orders, no advice — analytics/education only.
-- ════════════════════════════════════════════════════════════════════════════

drop table if exists public.alerts_log;
drop table if exists public.alert_rules;
drop type if exists alert_kind;

create table public.alert_rules (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references auth.users (id) on delete cascade,
  name              text not null,
  -- total_pnl | delta_rupees_per_pct | theta_rupees_per_day |
  -- vega_rupees_per_point | margin_utilization_pct | stress_loss_rupees
  metric            text not null,
  operator          text not null,             -- gt | lt | abs_gt
  threshold         numeric not null,
  enabled           boolean not null default true,
  cooldown_minutes  integer not null default 60,
  last_triggered_at timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create table public.alerts (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users (id) on delete cascade,
  rule_id      uuid references public.alert_rules (id) on delete set null,
  rule_name    text not null,
  metric       text not null,
  operator     text not null,
  threshold    numeric not null,
  observed     numeric not null,
  message      text not null,
  ai_phrased   boolean not null default false,
  acknowledged boolean not null default false,
  created_at   timestamptz not null default now()
);

create index idx_alert_rules_user_time on public.alert_rules (user_id, created_at desc);
create index idx_alert_rules_enabled on public.alert_rules (enabled) where enabled;
create index idx_alerts_user_time on public.alerts (user_id, created_at desc);

-- ── Row Level Security (owner-only, same pattern as the rest of the schema) ──
-- (Dropping the old tables above also dropped their old policies.)
alter table public.alert_rules enable row level security;
alter table public.alerts enable row level security;

create policy alert_rules_select on public.alert_rules
  for select using (user_id = auth.uid());
create policy alert_rules_insert on public.alert_rules
  for insert with check (user_id = auth.uid());
create policy alert_rules_update on public.alert_rules
  for update using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy alert_rules_delete on public.alert_rules
  for delete using (user_id = auth.uid());

create policy alerts_select on public.alerts
  for select using (user_id = auth.uid());
create policy alerts_insert on public.alerts
  for insert with check (user_id = auth.uid());
create policy alerts_update on public.alerts
  for update using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy alerts_delete on public.alerts
  for delete using (user_id = auth.uid());
