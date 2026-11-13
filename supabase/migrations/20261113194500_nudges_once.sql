-- A flame note goes to a member at most once a day, however many times the nightly job runs.
create table public.nudges (
  user_id uuid not null references public.profiles (id) on delete cascade,
  day     date not null,
  kind    text not null default 'flame',
  primary key (user_id, day, kind)
);
alter table public.nudges enable row level security;
create policy "admins read nudges" on public.nudges for select to authenticated using ((select private.is_admin()));

create or replace function public.nightly() returns jsonb
  language plpgsql security definer set search_path = '' as $$
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

  with due as (
    insert into public.nudges (user_id, day, kind)
    select st.user_id, current_date, 'flame'
    from public.standings st join public.profiles p on p.id = st.user_id
    where p.email_opt_in and st.last_sealed = current_date - 2
    on conflict do nothing
    returning user_id
  )
  select coalesce(jsonb_agg(jsonb_build_object('user_id', p.id, 'email', u.email, 'name', p.display_name, 'days_kept', st.days_kept)), '[]'::jsonb)
  into v_nudge
  from due d
  join public.profiles p on p.id = d.user_id
  join public.standings st on st.user_id = p.id
  join auth.users u on u.id = p.id;

  return jsonb_build_object('memberships_ended', v_ended, 'placed_in_circles', v_placed, 'nudges', v_nudge);
end $$;
revoke all on function public.nightly() from public, anon, authenticated;
grant execute on function public.nightly() to service_role;
