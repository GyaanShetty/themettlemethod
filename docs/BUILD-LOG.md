# Build log

## Phase 1: audit (13 Nov 2026)
- Read both project docs, the repo, the Supabase project and the Design System.
- Wrote `docs/ARCHITECTURE-NOW.md`.
- Removed the empty `main.yml` workflow.
- There were no tests to run. `python -m engine validate` and `python -m engine site` pass.

## Phase 2: schema (13 Nov 2026)
- Migration `engine_core` applied to `zcdszmvktizxydwgehsr` and saved in `supabase/migrations/`.
- New tables: admins, config, content, publications, products, subscriptions, payments, webhook_events, events, referrals, channel_metrics. Row-level security on all.
- New views, all running as the caller: funnel_daily, retention_cohorts, mrr_daily, revenue_by_stream, content_performance, rank_distribution, flames_lit, circle_health.
- Admin check is `private.is_admin()`, used by every admin policy.
- `days` read policy widened so admins can read all days for cohorts. Members still read only their own.
- Advisors after the migration: security clean. Performance shows only "unused index" notes, which is expected while the tables are empty; the indexes cover foreign keys.
- No one has signed in yet, so no admin is seeded. After the owner's first sign-in, run:
  `insert into public.admins (user_id) select id from auth.users where email = '<owner email>';`

## Decisions to confirm
- Inner Order price: unset, shown as [PRICE] from `config`.
- Payments: Gumroad memberships first.
- Email: provider unset; Resend and Buttondown behind one interface.
- Voice: en-GB-RyanNeural, rate -18%, pitch -14Hz.
- Numerals are set in Marcellus. The Design System README still says blackletter and needs correcting.
- `rank_distribution` counts by rank earned, not rank shown, so capped Outer Court members appear at their true rank.
