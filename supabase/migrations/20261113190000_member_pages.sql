-- What the member pages read. Members cannot read each other's days, so the shared figures come
-- from these functions, which return counts, display names, member numbers and ranks and nothing else.

create function private.streaks() returns table (user_id uuid, longest integer, current integer)
  language sql stable security definer set search_path = ''
as $$
  with runs as (
    select d.user_id, d.day, d.day - (row_number() over (partition by d.user_id order by d.day))::integer as grp
    from public.days d where d.sealed_at is not null
  ), isl as (
    select r.user_id, count(*)::integer as len, max(r.day) as last_day from runs r group by r.user_id, r.grp
  )
  select i.user_id, max(i.len), coalesce(max(i.len) filter (where i.last_day >= current_date - 1), 0) from isl i group by i.user_id
$$;
revoke all on function private.streaks() from public, anon, authenticated;

create function public.hall_tally() returns jsonb
  language sql stable security definer set search_path = ''
as $$
  select jsonb_build_object(
    'members', (select count(*) from public.profiles),
    'kept_today', (select count(*) from public.days where day = current_date and sealed_at is not null),
    'longest_unbroken', (select coalesce(max(current), 0) from private.streaks()))
$$;
revoke all on function public.hall_tally() from public, anon;
grant execute on function public.hall_tally() to authenticated;

create function public.hall_roll() returns table (display_name text, member_no bigint, rank integer, tier text, unbroken integer)
  language sql stable security definer set search_path = ''
as $$
  select p.display_name, p.member_no, st.rank, p.tier, s.current
  from private.streaks() s
  join public.profiles p on p.id = s.user_id
  join public.standings st on st.user_id = p.id
  where s.current > 0
  order by s.current desc, p.member_no
  limit 10
$$;
revoke all on function public.hall_roll() from public, anon;
grant execute on function public.hall_roll() to authenticated;

create function public.my_circle() returns table (display_name text, member_no bigint, rank integer, days_kept bigint, kept_today boolean, is_me boolean)
  language sql stable security definer set search_path = ''
as $$
  select p.display_name, p.member_no, st.rank, st.days_kept,
         exists (select 1 from public.days d where d.user_id = p.id and d.day = current_date and d.sealed_at is not null),
         p.id = (select auth.uid())
  from public.profiles me
  join public.profiles p on p.circle_id = me.circle_id
  join public.standings st on st.user_id = p.id
  where me.id = (select auth.uid()) and me.circle_id is not null
  order by p.member_no
$$;
revoke all on function public.my_circle() from public, anon;
grant execute on function public.my_circle() to authenticated;

-- Relic progress for the signed-in member. The rules are written out in docs/RELICS.md.
create function public.my_relics() returns jsonb
  language sql stable security definer set search_path = ''
as $$
  with me as (select p.id, coalesce(p.timezone, 'UTC') as tz from public.profiles p where p.id = (select auth.uid())),
  d as (select dd.* from public.days dd join me on me.id = dd.user_id),
  s as (select longest, current from private.streaks() where user_id = (select auth.uid()))
  select jsonb_build_object(
    'body_days',   (select count(*) from d where sealed_at is not null and ticks ->> 'body' = 'true'),
    'mind_days',   (select count(*) from d where sealed_at is not null and ticks ->> 'mind' = 'true'),
    'reviews',     (select count(*) from d where sealed_at is not null and review is not null),
    'vow30_days',  (select coalesce(max(least(30, current_date - v.started_on)), 0) from public.vows v join me on me.id = v.user_id where v.length_days = 30),
    'early_oaths', (select count(*) from d, me where oath_at is not null and extract(hour from oath_at at time zone me.tz) < 6),
    'longest',     coalesce((select longest from s), 0),
    'current',     coalesce((select current from s), 0),
    'drops',       coalesce((select st.drops from public.standings st where st.user_id = (select auth.uid())), 0))
$$;
revoke all on function public.my_relics() from public, anon;
grant execute on function public.my_relics() to authenticated;
