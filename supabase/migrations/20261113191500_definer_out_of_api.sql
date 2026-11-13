-- The functions that read across members keep their elevated rights, but live outside the API schema.
-- The API exposes thin wrappers that run as the caller.
alter function public.hall_tally() set schema private;
alter function public.hall_roll() set schema private;
alter function public.my_circle() set schema private;
alter function public.my_relics() set schema private;

create function public.hall_tally() returns jsonb language sql stable security invoker set search_path = ''
as $$ select private.hall_tally() $$;
create function public.hall_roll() returns table (display_name text, member_no bigint, rank integer, tier text, unbroken integer)
  language sql stable security invoker set search_path = ''
as $$ select * from private.hall_roll() $$;
create function public.my_circle() returns table (display_name text, member_no bigint, rank integer, days_kept bigint, kept_today boolean, is_me boolean)
  language sql stable security invoker set search_path = ''
as $$ select * from private.my_circle() $$;
create function public.my_relics() returns jsonb language sql stable security invoker set search_path = ''
as $$ select private.my_relics() $$;

revoke all on function public.hall_tally(), public.hall_roll(), public.my_circle(), public.my_relics() from public, anon;
grant execute on function public.hall_tally(), public.hall_roll(), public.my_circle(), public.my_relics() to authenticated;
