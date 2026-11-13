-- An invited person claims the code they arrived with, once, after signing in.
create function private.claim_invite(p_code text) returns boolean
  language plpgsql security definer set search_path = '' as $$
declare v_me uuid := (select auth.uid());
begin
  if v_me is null or p_code !~ '^[a-f0-9]{12}$' then return false; end if;
  update public.referrals set invitee_id = v_me, joined_at = now()
   where code = p_code and invitee_id is null and inviter_id <> v_me
     and not exists (select 1 from public.referrals r where r.invitee_id = v_me);
  if not found then return false; end if;
  insert into public.events (user_id, name, props) values (v_me, 'invite_joined', '{}'::jsonb);
  return true;
end $$;
revoke all on function private.claim_invite(text) from public, anon;
grant execute on function private.claim_invite(text) to authenticated;

create function public.claim_invite(p_code text) returns boolean language sql security invoker set search_path = ''
as $$ select private.claim_invite(p_code) $$;
revoke all on function public.claim_invite(text) from public, anon;
grant execute on function public.claim_invite(text) to authenticated;
