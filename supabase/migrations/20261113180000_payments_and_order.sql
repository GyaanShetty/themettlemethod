-- Payments, circles and the nightly job. Everything here runs server-side only.

alter table public.profiles
  add column if not exists timezone text,
  add column if not exists email_opt_in boolean not null default false;

-- Members may set their own timezone and email choice; tier, circle and number stay guarded by guard_profile.

-- ---------------------------------------------------------------- rate limits (not exposed through the API)
create table private.rate_limits (
  key          text not null,
  window_start timestamptz not null,
  hits         integer not null default 1,
  primary key (key, window_start)
);

create function private.hit(p_key text, p_max integer, p_window_seconds integer) returns boolean
  language plpgsql security definer set search_path = ''
as $$
declare
  w timestamptz := to_timestamp(floor(extract(epoch from now()) / p_window_seconds) * p_window_seconds);
  n integer;
begin
  insert into private.rate_limits (key, window_start) values (p_key, w)
  on conflict (key, window_start) do update set hits = private.rate_limits.hits + 1
  returning hits into n;
  delete from private.rate_limits where window_start < now() - interval '1 day';
  return n <= p_max;
end $$;
revoke all on function private.hit(text, integer, integer) from public, anon, authenticated;

-- Edge Functions call this through the API, so it lives in public but only the service role may run it.
create function public.rate_limit_hit(p_key text, p_max integer, p_window_seconds integer) returns boolean
  language sql security definer set search_path = ''
as $$ select private.hit(p_key, p_max, p_window_seconds) $$;
revoke all on function public.rate_limit_hit(text, integer, integer) from public, anon, authenticated;
grant execute on function public.rate_limit_hit(text, integer, integer) to service_role;

-- ---------------------------------------------------------------- one payment event, applied once
-- The webhook verifies the sender, turns the provider's payload into this shape, and calls this.
--   provider, event_id, kind: sale | refund | cancelled | ended
--   email, user_id (optional), provider_ref (subscription or sale id), sale_ref
--   amount_cents, currency, product, stream, billing_interval, period_end
create function public.apply_payment_event(e jsonb) returns text
  language plpgsql security definer set search_path = ''
as $$
declare
  v_provider text := e ->> 'provider';
  v_kind     text := e ->> 'kind';
  v_user     uuid;
  v_is_inner boolean := (e ->> 'stream') = 'inner_order';
begin
  if v_provider is null or e ->> 'event_id' is null or v_kind not in ('sale', 'refund', 'cancelled', 'ended') then
    raise exception 'bad payment event';
  end if;

  insert into public.webhook_events (provider, event_id) values (v_provider, e ->> 'event_id')
  on conflict do nothing;
  if not found then
    return 'duplicate';
  end if;

  -- Who is this? A user id passed through checkout wins; otherwise the email on the sale.
  select p.id into v_user from public.profiles p where p.id::text = e ->> 'user_id';
  if v_user is null and e ->> 'email' is not null then
    select p.id into v_user from public.profiles p join auth.users u on u.id = p.id
    where lower(u.email) = lower(e ->> 'email') limit 1;
  end if;

  if v_kind in ('sale', 'refund') and (e ->> 'amount_cents') is not null then
    insert into public.payments (user_id, provider, provider_ref, kind, stream, product, amount_cents, currency)
    values (v_user, v_provider, coalesce(e ->> 'sale_ref', e ->> 'provider_ref'),
            case v_kind when 'refund' then 'refund' else 'charge' end,
            coalesce(e ->> 'stream', 'products'), e ->> 'product', (e ->> 'amount_cents')::integer, coalesce(e ->> 'currency', 'USD'))
    on conflict (provider, provider_ref, kind) do nothing;

    if v_kind = 'sale' and not v_is_inner then
      update public.products set sales = sales + 1, revenue_cents = revenue_cents + (e ->> 'amount_cents')::integer, updated_at = now()
      where slug = e ->> 'product';
    end if;
  end if;

  if v_is_inner then
    if v_kind = 'sale' then
      insert into public.subscriptions (user_id, provider, provider_ref, email, status, amount_cents, currency, billing_interval, current_period_end)
      values (v_user, v_provider, e ->> 'provider_ref', e ->> 'email', 'active', (e ->> 'amount_cents')::integer,
              coalesce(e ->> 'currency', 'USD'), e ->> 'billing_interval', (e ->> 'period_end')::timestamptz)
      on conflict (provider, provider_ref) do update
        set status = 'active', ended_at = null, user_id = coalesce(excluded.user_id, public.subscriptions.user_id),
            current_period_end = coalesce(excluded.current_period_end, public.subscriptions.current_period_end), updated_at = now();
      if v_user is not null then
        update public.profiles set tier = 'inner' where id = v_user and tier <> 'inner';
        insert into public.events (user_id, name, props) values (v_user, 'upgrade_paid', jsonb_build_object('provider', v_provider));
      end if;
    elsif v_kind = 'cancelled' then
      -- Cancelling stops renewal. The member keeps what they paid for until the period ends.
      update public.subscriptions set status = 'cancelled', updated_at = now()
      where provider = v_provider and provider_ref = e ->> 'provider_ref'
      returning user_id into v_user;
      if v_user is not null then
        insert into public.events (user_id, name, props) values (v_user, 'cancel', jsonb_build_object('provider', v_provider));
      end if;
    else  -- ended, or a refund of the membership: back to the Outer Court. Days and rank earned are untouched.
      update public.subscriptions set status = 'ended', ended_at = now(), updated_at = now()
      where provider = v_provider and provider_ref = e ->> 'provider_ref'
      returning user_id into v_user;
      if v_user is not null and not exists (
        select 1 from public.subscriptions s where s.user_id = v_user and s.status in ('active', 'cancelled') and s.ended_at is null
      ) then
        update public.profiles set tier = 'outer', circle_id = null where id = v_user;
      end if;
    end if;
  end if;

  return case when v_user is null then 'applied, no member matched' else 'applied' end;
end $$;
revoke all on function public.apply_payment_event(jsonb) from public, anon, authenticated;
grant execute on function public.apply_payment_event(jsonb) to service_role;

-- A sale that arrived before its buyer signed in is claimed when they do.
create function public.claim_subscription() returns trigger
  language plpgsql security definer set search_path = ''
as $$
declare v_email text;
begin
  select lower(email) into v_email from auth.users where id = new.id;
  update public.subscriptions set user_id = new.id where user_id is null and lower(email) = v_email;
  if exists (select 1 from public.subscriptions where user_id = new.id and status in ('active', 'cancelled') and ended_at is null) then
    new.tier := 'inner';
  end if;
  return new;
end $$;
revoke all on function public.claim_subscription() from public, anon, authenticated;
create trigger claim_subscription before insert on public.profiles
  for each row execute function public.claim_subscription();

-- ---------------------------------------------------------------- circles of five
create function public.assign_circles() returns integer
  language plpgsql security definer set search_path = ''
as $$
declare
  m record;
  v_circle bigint;
  placed integer := 0;
begin
  for m in
    select id, house, timezone from public.profiles
    where tier = 'inner' and circle_id is null
    order by house nulls last, timezone nulls last, created_at
  loop
    -- An open circle of the same house first, nearest timezone preferred; any open circle after that.
    select c.id into v_circle
    from public.circles c join public.profiles p on p.circle_id = c.id
    group by c.id
    having count(*) < 5
    order by (count(*) filter (where p.house is not distinct from m.house)) desc,
             (count(*) filter (where p.timezone is not distinct from m.timezone)) desc,
             count(*) desc, c.id
    limit 1;
    if v_circle is null then
      insert into public.circles (name) values ('Circle ' || (select count(*) + 1 from public.circles)) returning id into v_circle;
    end if;
    update public.profiles set circle_id = v_circle where id = m.id;
    placed := placed + 1;
  end loop;
  return placed;
end $$;
revoke all on function public.assign_circles() from public, anon, authenticated;
grant execute on function public.assign_circles() to service_role;

-- ---------------------------------------------------------------- nightly
-- Ends memberships whose paid period has run out, fills circles, and returns who to nudge.
create function public.nightly() returns jsonb
  language plpgsql security definer set search_path = ''
as $$
declare
  v_ended integer;
  v_placed integer;
  v_nudge jsonb;
begin
  with done as (
    update public.subscriptions set status = 'ended', ended_at = now(), updated_at = now()
    where status = 'cancelled' and ended_at is null and current_period_end is not null and current_period_end < now()
    returning user_id
  ), back as (
    update public.profiles p set tier = 'outer', circle_id = null
    where p.id in (select user_id from done)
      and not exists (select 1 from public.subscriptions s where s.user_id = p.id and s.status = 'active')
    returning 1
  )
  select count(*) into v_ended from back;

  v_placed := public.assign_circles();

  -- The flame goes out after three unsealed days. Two days in, one quiet note, only to those who asked for email.
  select coalesce(jsonb_agg(jsonb_build_object('user_id', p.id, 'email', u.email, 'name', p.display_name, 'days_kept', st.days_kept)), '[]'::jsonb)
  into v_nudge
  from public.standings st
  join public.profiles p on p.id = st.user_id
  join auth.users u on u.id = p.id
  where p.email_opt_in and st.last_sealed = current_date - 2;

  return jsonb_build_object('memberships_ended', v_ended, 'placed_in_circles', v_placed, 'nudges', v_nudge);
end $$;
revoke all on function public.nightly() from public, anon, authenticated;
grant execute on function public.nightly() to service_role;

-- ---------------------------------------------------------------- what the member pages read
-- One call for the ledger, pillar bars and relics, for the signed-in member only.
create function public.my_ledger() returns jsonb
  language sql stable security invoker set search_path = ''
as $$
  select jsonb_build_object(
    'days', coalesce((select jsonb_agg(jsonb_build_object('day', d.day, 'sealed', d.sealed_at is not null, 'ticks', d.ticks) order by d.day)
                      from public.days d where d.user_id = (select auth.uid()) and d.day >= current_date - 120), '[]'::jsonb),
    'pillars', (select jsonb_object_agg(k, n) from (
                  select t.key as k, count(*) filter (where t.value = 'true'::jsonb) as n
                  from public.days d cross join lateral jsonb_each(d.ticks) t
                  where d.user_id = (select auth.uid()) and d.sealed_at is not null
                  group by t.key) x),
    'standing', (select to_jsonb(s) from public.standings s where s.user_id = (select auth.uid())),
    'vows_kept', (select count(*) from public.vows v where v.user_id = (select auth.uid()) and v.started_on + v.length_days <= current_date),
    'honours_given', (select count(*) from public.honours h where h.user_id = (select auth.uid())),
    'posts', (select count(*) from public.posts p where p.user_id = (select auth.uid()))
  )
$$;
revoke all on function public.my_ledger() from public, anon;
grant execute on function public.my_ledger() to authenticated;
