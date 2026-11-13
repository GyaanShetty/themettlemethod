-- Engine core: admins, config, content mirror, publications, products, payments,
-- events, referrals, channel metrics, and the dashboard views.
-- Every table has row-level security. Writes that matter go through the service role only.

create schema if not exists private;
grant usage on schema private to anon, authenticated, service_role;

-- ---------------------------------------------------------------- admins
create table public.admins (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  created_at timestamptz not null default now()
);
alter table public.admins enable row level security;

create function private.is_admin() returns boolean
  language sql stable security definer set search_path = ''
as $$ select exists (select 1 from public.admins where user_id = (select auth.uid())) $$;
revoke all on function private.is_admin() from public;
grant execute on function private.is_admin() to anon, authenticated, service_role;

create policy "admins read admins" on public.admins
  for select to authenticated using ((select private.is_admin()));

-- ---------------------------------------------------------------- config
create table public.config (
  key        text primary key,
  value      jsonb,
  is_public  boolean not null default false,
  note       text,
  updated_at timestamptz not null default now(),
  updated_by uuid references auth.users (id) on delete set null
);
alter table public.config enable row level security;
create index config_updated_by_idx on public.config (updated_by);

create policy "read public config, admins read all" on public.config
  for select to anon, authenticated using (is_public or (select private.is_admin()));
create policy "admins insert config" on public.config
  for insert to authenticated with check ((select private.is_admin()));
create policy "admins update config" on public.config
  for update to authenticated using ((select private.is_admin())) with check ((select private.is_admin()));

insert into public.config (key, value, is_public, note) values
  ('publish_live',          'false', false, 'Nothing posts publicly until this is true.'),
  ('price_inner_monthly',   'null',  true,  'Inner Order, per month. Null shows [PRICE].'),
  ('price_inner_yearly',    'null',  true,  'Inner Order, per year. Null shows [PRICE].'),
  ('price_currency',        '"USD"', true,  null),
  ('inner_checkout_url',    'null',  true,  'Gumroad membership link.'),
  ('posting_time_ist',      '"06:15"', false, 'Daily run time.'),
  ('email_provider',        'null',  false, 'resend or buttondown.'),
  ('domain',                'null',  false, 'Set when themettlemethod.com is bought.'),
  ('voice',                 '{"name":"en-GB-RyanNeural","rate":"-18%","pitch":"-14Hz"}', false, 'Reel narration.');

-- ---------------------------------------------------------------- content mirror
create table public.content (
  id         text primary key,
  type       text not null check (type in ('model','concept','skill','quote','law')),
  pillar     text check (pillar in ('mind','body','faith','relationships')),
  number     integer,
  title      text not null,
  kicker     text,
  headline   text,
  sub        text,
  body       text,
  source     text,
  image      text,
  publish_on date,
  status     text not null default 'draft' check (status in ('draft','approved','scheduled','published','held')),
  channels   text[] not null default '{}',
  git_sha    text,
  updated_at timestamptz not null default now()
);
alter table public.content enable row level security;
create index content_publish_on_idx on public.content (publish_on);
create policy "admins read content" on public.content
  for select to authenticated using ((select private.is_admin()));

create table public.publications (
  id          bigint generated always as identity primary key,
  content_id  text not null references public.content (id) on delete cascade,
  channel     text not null check (channel in ('instagram_plate','instagram_carousel','instagram_story','instagram_reel','youtube_short','threads','email','site')),
  status      text not null default 'pending' check (status in ('pending','dry_run','posted','failed','held')),
  external_id text,
  url         text,
  posted_at   timestamptz,
  attempts    integer not null default 0,
  error       text,
  metrics     jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (content_id, channel)
);
alter table public.publications enable row level security;
create policy "admins read publications" on public.publications
  for select to authenticated using ((select private.is_admin()));

-- ---------------------------------------------------------------- products
create table public.products (
  slug          text primary key,
  name          text not null,
  format        text,
  price_cents   integer,
  currency      text not null default 'USD',
  status        text not null default 'spec' check (status in ('spec','built','draft','live','unshipped','rejected')),
  gumroad_id    text,
  url           text,
  sales         integer not null default 0,
  revenue_cents bigint not null default 0,
  updated_at    timestamptz not null default now()
);
alter table public.products enable row level security;
create policy "read live products, admins read all" on public.products
  for select to anon, authenticated using (status = 'live' or (select private.is_admin()));

insert into public.products (slug, name, format, price_cents) values
  ('decision-journal',   'Decision Journal',   'Notion template', 1900),
  ('mental-models-deck', 'Mental Models Deck', 'PDF / Notion',     900);

-- ---------------------------------------------------------------- money
create table public.subscriptions (
  id                 bigint generated always as identity primary key,
  user_id            uuid references public.profiles (id) on delete set null,
  provider           text not null check (provider in ('gumroad','razorpay','stripe')),
  provider_ref       text not null,
  email              text,
  status             text not null check (status in ('active','cancelled','past_due','ended')),
  amount_cents       integer,
  currency           text,
  billing_interval   text check (billing_interval in ('month','year')),
  started_at         timestamptz not null default now(),
  current_period_end timestamptz,
  ended_at           timestamptz,
  updated_at         timestamptz not null default now(),
  unique (provider, provider_ref)
);
alter table public.subscriptions enable row level security;
create index subscriptions_user_id_idx on public.subscriptions (user_id);
create policy "own subscriptions, admins read all" on public.subscriptions
  for select to authenticated using (user_id = (select auth.uid()) or (select private.is_admin()));

create table public.payments (
  id           bigint generated always as identity primary key,
  user_id      uuid references public.profiles (id) on delete set null,
  provider     text not null check (provider in ('gumroad','razorpay','stripe')),
  provider_ref text not null,
  kind         text not null default 'charge' check (kind in ('charge','refund')),
  stream       text not null default 'products' check (stream in ('inner_order','products','cohorts','relics','other')),
  product      text,
  amount_cents integer not null,
  currency     text not null,
  created_at   timestamptz not null default now(),
  unique (provider, provider_ref, kind)
);
alter table public.payments enable row level security;
create index payments_user_id_idx on public.payments (user_id);
create policy "own payments, admins read all" on public.payments
  for select to authenticated using (user_id = (select auth.uid()) or (select private.is_admin()));

-- Webhook deliveries already handled, so a replay changes nothing.
create table public.webhook_events (
  provider    text not null,
  event_id    text not null,
  received_at timestamptz not null default now(),
  primary key (provider, event_id)
);
alter table public.webhook_events enable row level security;
create policy "admins read webhook events" on public.webhook_events
  for select to authenticated using ((select private.is_admin()));

-- ---------------------------------------------------------------- events
create table public.events (
  id      bigint generated always as identity primary key,
  user_id uuid references auth.users (id) on delete set null,
  name    text not null check (name in ('visit','signup','oath','seal','vow','post','upgrade_view','upgrade_paid','cancel','invite_sent','invite_joined','external_call','publish_failed')),
  props   jsonb not null default '{}'::jsonb,
  ts      timestamptz not null default now()
);
alter table public.events enable row level security;
create index events_name_ts_idx on public.events (name, ts);
create index events_user_id_idx on public.events (user_id);

-- The site may log its own events. Paid, cancel and joined are written by the server only.
create policy "site logs events" on public.events
  for insert to anon, authenticated
  with check (
    name in ('visit','signup','oath','seal','vow','post','upgrade_view','invite_sent')
    and (user_id is null or user_id = (select auth.uid()))
    and pg_column_size(props) <= 2048
  );
create policy "admins read events" on public.events
  for select to authenticated using ((select private.is_admin()));

-- ---------------------------------------------------------------- referrals
create table public.referrals (
  id         bigint generated always as identity primary key,
  inviter_id uuid not null references public.profiles (id) on delete cascade,
  code       text not null unique default encode(extensions.gen_random_bytes(6), 'hex'),
  invitee_id uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  joined_at  timestamptz
);
alter table public.referrals enable row level security;
create index referrals_inviter_id_idx on public.referrals (inviter_id);
create index referrals_invitee_id_idx on public.referrals (invitee_id);
create policy "own referrals, admins read all" on public.referrals
  for select to authenticated
  using (inviter_id = (select auth.uid()) or invitee_id = (select auth.uid()) or (select private.is_admin()));
create policy "members create invites" on public.referrals
  for insert to authenticated
  with check (inviter_id = (select auth.uid()) and invitee_id is null and joined_at is null);

-- ---------------------------------------------------------------- channel metrics
create table public.channel_metrics (
  channel   text not null check (channel in ('instagram','youtube','threads','email','gumroad','site')),
  day       date not null,
  followers integer,
  reach     integer,
  saves     integer,
  shares    integer,
  clicks    integer,
  raw       jsonb not null default '{}'::jsonb,
  primary key (channel, day)
);
alter table public.channel_metrics enable row level security;
create policy "admins read channel metrics" on public.channel_metrics
  for select to authenticated using ((select private.is_admin()));

-- ---------------------------------------------------------------- existing tables
create index if not exists posts_user_id_idx on public.posts (user_id);

-- Admins need every member's days for cohorts; members still see only their own.
drop policy "own days read" on public.days;
create policy "own days read, admins read all" on public.days
  for select to authenticated using (user_id = (select auth.uid()) or (select private.is_admin()));

-- ---------------------------------------------------------------- views
-- All views run as the caller, so row-level security decides what each person sees.

create view public.funnel_daily with (security_invoker = true) as
with bounds as (
  select least((select min(created_at)::date from public.profiles),
               (select min(ts)::date from public.events)) as first_day
), d as (
  select generate_series(first_day, current_date, interval '1 day')::date as day from bounds
), v as (
  select ts::date as day, count(*) as n from public.events where name = 'visit' group by 1
), s as (
  select p.created_at::date as day,
         count(*) as signups,
         count(*) filter (where st.days_kept >= 7)  as day7,
         count(*) filter (where st.days_kept >= 21) as day21,
         count(*) filter (where p.tier = 'inner')   as paid
  from public.profiles p left join public.standings st on st.user_id = p.id
  group by 1
)
select d.day,
       coalesce(v.n, 0)       as visits,
       coalesce(s.signups, 0) as signups,
       coalesce(s.day7, 0)    as day7,
       coalesce(s.day21, 0)   as day21,
       coalesce(s.paid, 0)    as paid
from d left join v using (day) left join s using (day);

create view public.retention_cohorts with (security_invoker = true) as
select date_trunc('week', p.created_at)::date as cohort_week,
       count(*) as size,
       count(*) filter (where k.last_offset >= 1)   as d1,
       count(*) filter (where k.last_offset >= 7)   as d7,
       count(*) filter (where k.last_offset >= 21)  as d21,
       count(*) filter (where k.last_offset >= 40)  as d40,
       count(*) filter (where k.last_offset >= 100) as d100
from public.profiles p
left join lateral (
  select max(dd.day - p.initiated_on) as last_offset
  from public.days dd where dd.user_id = p.id and dd.sealed_at is not null
) k on true
group by 1;

create view public.mrr_daily with (security_invoker = true) as
select d.day::date as day,
       s.currency,
       sum(case s.billing_interval when 'year' then s.amount_cents / 12.0 else s.amount_cents end)::bigint as mrr_cents,
       count(*) as active_members
from (select min(started_at)::date as first_day from public.subscriptions) b
cross join lateral generate_series(b.first_day, current_date, interval '1 day') as d(day)
join public.subscriptions s
  on s.started_at::date <= d.day and (s.ended_at is null or s.ended_at::date > d.day)
group by 1, 2;

create view public.revenue_by_stream with (security_invoker = true) as
select date_trunc('month', created_at)::date as month,
       stream,
       currency,
       sum(amount_cents) filter (where kind = 'charge') as gross_cents,
       coalesce(sum(amount_cents) filter (where kind = 'refund'), 0) as refund_cents,
       count(*) filter (where kind = 'charge') as charges,
       count(*) filter (where kind = 'refund') as refunds
from public.payments
group by 1, 2, 3;

create view public.content_performance with (security_invoker = true) as
select c.id as content_id, c.type, c.pillar, c.title, c.publish_on, c.status as content_status,
       p.channel, p.status, p.url, p.posted_at,
       (p.metrics ->> 'reach')::bigint  as reach,
       (p.metrics ->> 'likes')::bigint  as likes,
       (p.metrics ->> 'saves')::bigint  as saves,
       (p.metrics ->> 'shares')::bigint as shares,
       (p.metrics ->> 'clicks')::bigint as clicks
from public.content c left join public.publications p on p.content_id = c.id;

create view public.rank_distribution with (security_invoker = true) as
select r.rank, count(st.user_id) as members
from generate_series(0, 9) as r(rank)
left join public.standings st on st.rank_earned = r.rank
group by r.rank;

create view public.flames_lit with (security_invoker = true) as
select count(*) filter (where flame_lit) as lit, count(*) as members from public.standings;

create view public.circle_health with (security_invoker = true) as
select c.id as circle_id, c.name, count(p.id) as members, count(p.id) >= 5 as is_full
from public.circles c left join public.profiles p on p.circle_id = c.id
group by c.id, c.name;
