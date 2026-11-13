-- A sale that arrived before its buyer signed in: set the tier before the profile row is written,
-- and link the subscription after, once the row exists for the foreign key.
create or replace function public.claim_subscription() returns trigger
  language plpgsql security definer set search_path = ''
as $$
declare v_email text;
begin
  select lower(email) into v_email from auth.users where id = new.id;
  if tg_when = 'BEFORE' then
    if exists (select 1 from public.subscriptions
               where user_id is null and lower(email) = v_email and status in ('active', 'cancelled') and ended_at is null) then
      new.tier := 'inner';
    end if;
    return new;
  end if;
  update public.subscriptions set user_id = new.id where user_id is null and lower(email) = v_email;
  update public.payments p set user_id = new.id
  from public.subscriptions s
  where s.user_id = new.id and p.user_id is null and p.provider = s.provider and p.provider_ref = s.provider_ref;
  return null;
end $$;
revoke all on function public.claim_subscription() from public, anon, authenticated;

create trigger link_subscription after insert on public.profiles
  for each row execute function public.claim_subscription();
