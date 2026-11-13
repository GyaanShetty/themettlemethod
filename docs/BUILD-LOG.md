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

## Phase 3: template layer and still renderers (13 Nov 2026, in progress)
- `brand/tokens.json` mirrors the Design System tokens; `engine/brand.py` turns them into CSS. Fonts are local woff2 files from the @fontsource packages.
- `engine/atoms.py`: the atom schema in pydantic. Existing YAML keeps its fields; `pillar`, `kicker`, `headline`, `image`, `status` and `channels` were added to the five atoms.
- `engine/social.py`: plate 1080×1350 (ink and paper), story 1080×1920, carousel 4 × 1080×1440, product covers 1280×720 and 600×600. Each render writes a manifest of hashes.
- Every render is measured in the browser: headline line count at 104/92/70, overflow, boxes outside the page, overlapping rows, failed images. Any finding fails the build.
- Tests: 35 passing. Schema rejections, every atom rendered, golden images, two deliberate overflow failures, and 4.5:1 contrast across both themes. `tests.yml` runs them on every push.
- Renders were checked by eye. Found and fixed: escaped line breaks in headlines, fonts not loading, the Greek key band not drawing, statues cropped at the head, Markdown marks in carousel text.

Deviations, to confirm:
- Story image window is 760px, not 900px. With 250px safe areas the 900px window leaves 240px for kicker, headline and sub, which overflows.
- The header numeral is ink in Marcellus, so oxblood appears once per plate, on the Greek key band. The kicker is muted for the same reason.
- The headlines on the five existing atoms were written during this build and need the owner's eye.

Not done yet in this phase: reel re-skin, story and carousel series numbering, the grid-puzzle splitter, email HTML, Series II and III comparison.

## Phase 3, finished (13 Nov 2026)
- Reels re-skinned from the brand tokens: title card over the photograph with a slow push-in and grain, captions in Hanken 600 at 64px on a 70% night band, end card on night with the white seal. Voice set to en-GB-RyanNeural, rate -18%, pitch -14Hz.
- The library site and product templates now use the brand fonts and colours. The old Fraunces and Inter files are gone.
- `engine/text.py`: thread (3 to 5 lines, under 500 characters) and the morning email (HTML and plain text, one-click stop).
- `engine/grid.py`: the grid puzzle. Post 1 is the bottom-right tile, post 9 the top-left; a test rebuilds the master from the tiles.
- `TTS_ENGINE=silent` renders reel layouts with no voice, for previews and tests. The real voice only runs on Actions.
- Not done: the reel video itself has not been rendered end to end in this build (edge-tts is unreachable here); only its stills were checked. Series II and III were not re-rendered from atoms or compared with the shipped PNGs, since they are not atoms in the repo yet.

## Phase 4: publishers (13 Nov 2026)
- `engine/publish.py`: Instagram plate, carousel, story and reel; YouTube Shorts; Threads; email through Resend or Buttondown; the site. One interface, one `run()` that decides live or dry run.
- Live needs all four: atom approved, `publish_live` true in the config table, the channel's secrets present, nothing already posted. Otherwise it is a dry run that prints what would be sent.
- `engine/net.py`: every external call has a timeout, retries with backoff and an `external_call` event.
- `engine/ledger.py`: outcomes go to `state.json` and are mirrored to `publications`. A second run posts nothing twice.
- Only today's and yesterday's atoms are picked up, so turning live on cannot release a backlog.
- `daily.yml` now runs at 06:15 IST, covers every channel and opens a GitHub issue assigned to the owner when a publish fails.
- Storage bucket `media` created (public read, service-role write).
- None of the live paths has been exercised against the real APIs. No secrets exist yet, so only the dry-run path is proven.
