# Architecture now

Audit of 13 Nov 2026, before anything new is designed. Sources read: the two project docs, the repo at `098d272`, Supabase project `zcdszmvktizxydwgehsr`, and the Design System artifact (README, tokens.json, file and asset lists).

## 1. What exists

### Repo (`GyaanShetty/themettlemethod`, public, 8 commits)

| Area | Files | State |
|---|---|---|
| `engine/` | 10 Python modules, about 1,450 lines: `content`, `reel`, `tts`, `publish`, `site`, `state`, `notion`, `products`, CLI | Runs. `python -m engine validate` passes; `python -m engine site` builds |
| `engine/templates/` | `reel.html`, 10 site templates, 4 product templates | All in the old look (see gaps) |
| `content/` | 3 models, 1 concept, 1 skill | Valid. Five atoms in total |
| `products/` | `decision-journal.yaml`, `mental-models-deck.yaml`, covers and thumbnails | Specs valid; covers in the old look |
| `web/` | 8 pages, `assets/js/mettle.js` (54 lines), art, art2, ranks, relics, houses, seal | In the brand. Fonts come from Google Fonts by link |
| `.github/workflows/` | daily, preview, site, products, ship, tokens, voice, plus an empty `main.yml` | See gaps |
| `prompts/` | three planner prompts for scheduled writing | Present |

Flow today: a model YAML becomes a reel (Playwright frames, ffmpeg, edge-tts, word-timed captions), which `publish.py` posts to YouTube Shorts and Instagram Reels. Posting state lives in `state.json`, committed back by CI. `site.py` builds a lesson library. Products go Notion, then Gumroad draft, then a review issue, then `/ship`.

### Supabase (`themettlemethod`, ap-south-1)

- Tables, all with RLS on and all empty: `profiles`, `days`, `vows`, `circles`, `posts`, `honours`.
- View `standings`: days kept, drops (one per 30 missed days in a row), rank earned, rank shown (capped at III for the Outer Court), flame lit (sealed within 3 days).
- Triggers: `on_auth_user_created` creates the profile; `guard_profile` refuses changes to `tier`, `circle_id` and `member_no` unless the caller is the service role.
- Policies: members write only their own rows; days can be logged for today or yesterday only.
- Migrations: `order_core`, `revoke_trigger_fn`. Edge Functions: none.
- Advisors: security clean. Performance: one unindexed foreign key (`posts.user_id`) and five unused-index notes, expected on empty tables.

### Design System artifact

README (the brand book), `tokens.json` (12 colour tokens across Paper and Ink, five type families, spacing, radius, stroke), 11 components with previews (Plate, ProductCover, ReelTitleCard, RankLadder, Quote, Tag, Button, Lockup, ModelCard, Ornaments, PillarIcons) and 91 assets. The SVG assets are readable through the tools; the PNG, JPEG and WebP assets (seal, lockups, ranks, statues, stills) are not, so those must come from the repo's `web/assets` or from the owner's Mac.

### Artifact types on this account

Data (the dashboard type), Design, Design System, Docs, Sheets, Slides, Whiteboard. The War Room can be built on the Data type.

## 2. Gaps and broken pieces

1. **The engine is not in the brand.** `engine.yaml` uses amber `#F2A33A` on `#14120F`; `reel.html` uses Fraunces and Inter (the only fonts in `assets/fonts/`); the voice is `en-US-AndrewMultilingualNeural` at +6%, not en-GB-RyanNeural slower and lower. The tagline is the older "Learn something useful every day". Reels, library pages and product covers all need the template layer.
2. **No tests.** There is no `tests/` folder and no CI test step. "Run the existing tests" has nothing to run.
3. **The atom schema differs from the target.** Models are scene scripts (`scenes`, `say`, `caption`, `tags`, `article`, `category`, `number`). There is no `pillar`, `kicker`, `headline`, `sub`, `source`, `image`, `status` or `channels`, and no `quote` or `law` type. The new fields can be added alongside the old ones without breaking the reel scripts.
4. **Nothing has been posted and no state is recorded.** `state.json` does not exist, though three models were due on 3 to 5 Nov. Idempotency rests on that one committed file.
5. **`main.yml` is an empty workflow file.** GitHub reports it as invalid on every push. It should be removed.
6. **`daily.yml` is named for 18:30 IST and reels only.** The money-engine doc expects 06:15 IST with plate, thread and email. Only reels to YouTube and Instagram exist. No plate, carousel, story, thread or email renderer; no Threads or email publisher; no dry-run default or `PUBLISH_LIVE` switch.
7. **Instagram hosting points at a `reels` bucket** through `SUPABASE_URL`, which the context doc says was the older project. The target is a `media` bucket in `themettlemethod`.
8. **Site wiring is partial.** `mettle.js` handles sign-in, name, day, rank, oath, seal, vows and the hall. The ledger calendar, pillar bars, ranks ladder, reliquary, circles and the upgrade page still show placeholder data. No analytics events are sent.
9. **art2 images.** Already referenced on about, order, reliquary, ranks and community; `build.html` has none, so the half-built temple is not placed.
10. **Order backend is missing its paid half.** No `subscriptions`, `payments`, `events`, `referrals`, `admins`, `config`, `content`, `publications`, `products` or `channel_metrics` tables; no views beyond `standings`; no Edge Functions.
11. **`guard_profile` does not guard rank directly**, which is correct, since rank is derived in `standings` and never stored. Worth stating so nobody adds a rank column later.
12. **Series II and III source.** The shipped Series III PNGs are on the Mac (`themettlemethod-series3-story/`, 36 files plus captions). The Series II zip is not in the connected folder, so the Series II comparison has nothing to compare against yet.
13. **Brand book and prompt disagree on numerals.** The README still says blackletter numerals; the context doc and the build prompt say Marcellus numerals, blackletter for drop letters only. The build follows Marcellus; the README should be corrected.
14. **The connected Mac folder is not the repo.** It holds art, the Series III export and older zips. The repo was read from GitHub.

## 3. Decisions only the owner can make

| Decision | Safe default until decided |
|---|---|
| Inner Order price, USD and INR, and a founding price | `[PRICE]`, read from config |
| Payment stack | Gumroad memberships first, behind a provider interface |
| Email provider | Interface with Resend and Buttondown adapters, neither live |
| Domain | Stay on the Pages URL; no CNAME |
| Voice | en-GB-RyanNeural, slower and lower |
| Going live | `PUBLISH_LIVE=false` |

