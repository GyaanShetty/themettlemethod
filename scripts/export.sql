-- Plain exports for a spreadsheet. Run in the Supabase SQL editor and download each result as CSV.
-- Members: number, name, court, rank and days. No email addresses.
select p.member_no, p.display_name, p.tier, p.house, s.rank_earned, s.days_kept, s.last_sealed, p.created_at::date as joined
from public.profiles p join public.standings s on s.user_id = p.id order by p.member_no;

-- Money.
select created_at::date as day, provider, kind, stream, product, amount_cents, currency from public.payments order by created_at;

-- What went out, and where.
select c.id, c.title, c.publish_on, p.channel, p.status, p.url, p.posted_at from public.content c
left join public.publications p on p.content_id = c.id order by c.publish_on, c.id, p.channel;
