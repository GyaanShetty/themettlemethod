# The Mettle Method

One content atom, four outputs.

```
content/models/<slug>.yaml ─┬─▶ reel (1080×1920, neural voice, word captions) ─▶ YouTube Shorts + Instagram Reels
                            ├─▶ website page (video + written breakdown)       ─▶ GitHub Pages
                            └─▶ card in the Mental Models deck                  ─▶ Gumroad
content/concepts/*.yaml ───────▶ website: Concepts track (daily)
content/skills/*.yaml ─────────▶ website: Skills track, with a learning plan
products/<slug>.yaml ──────────▶ Notion self-help template ─▶ review issue ─▶ /ship ─▶ Gumroad ─▶ website
```

Three scheduled Claude tasks write the content: `prompts/plan_models.md` (weekly, 7 reels queued),
`prompts/plan_learning.md` (weekly, 4 concepts + 3 skills) and `prompts/plan_product.md` (twice a month).
Add a track (e.g. `books`) by adding it under `tracks:` in `engine.yaml` and making `content/books/`. GitHub Actions does everything else.

## What runs when

| Workflow | When | Does |
|---|---|---|
| `preview.yml` | a model YAML lands | renders the reel with the real voice → download from the run's artifacts |
| `daily.yml` | 18:30 IST daily | posts whatever's due to YouTube + Instagram, commits `state.json`, refreshes the site |
| `site.yml` | every push, and 06:15 IST daily | rebuilds the site; that day's scheduled lessons go live |
| `products.yml` | a product YAML lands; Mondays | builds it (Notion or PDF), opens a review issue |
| `ship.yml` | you comment `/ship` on that issue | Gumroad listing live, site updated |
| `tokens.yml` | 1st of each month | refreshes the Instagram token |

**Your review window:** models are written a week ahead and previewed when they land. To stop one,
edit or delete its YAML before its `publish_on` date.

## Setup (about an hour, once)

### 1. Repo
1. Create a **private** GitHub repo called `themettlemethod`, push this folder to `main`.
2. Settings → Actions → General → Workflow permissions → **Read and write**.
3. Settings → Pages → Source: **GitHub Actions**. Pages on a private repo needs GitHub Pro, which is free with the
   [GitHub Student Developer Pack](https://education.github.com/pack). Or make the repo public; no secrets live in files.
4. Edit `engine.yaml`: brand name, handle, `site_url` (`https://<you>.github.io/themettlemethod`), Gumroad URL.

### 2. YouTube (secrets `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`)
1. console.cloud.google.com → new project → enable **YouTube Data API v3**.
2. OAuth consent screen: External, add yourself as a test user, then **Publish app** (test-mode refresh tokens die after 7 days).
3. Credentials → OAuth client ID → **Desktop app** → copy the ID and secret.
4. Get a refresh token with scope `https://www.googleapis.com/auth/youtube.upload`, for example through the
   [OAuth Playground](https://developers.google.com/oauthplayground) (gear icon → use your own credentials).
5. Uploads from a new API project are **locked to private** until YouTube audits it. Submit the
   [API audit form](https://support.google.com/youtube/contact/yt_api_form) on day one. Until it's approved,
   flip each Short to public in YouTube Studio (the daily run warns you).

### 3. Instagram (secret `IG_ACCESS_TOKEN`)
1. Switch your Instagram account to **Professional** (Creator is fine). No Facebook Page needed.
2. developers.facebook.com → create an app → add **Instagram** → "API setup with Instagram login".
3. Add your account under Roles as an Instagram tester and accept the invite in the Instagram app.
4. Generate a token with `instagram_business_basic` and `instagram_business_content_publish`.
   The dashboard gives a long-lived (60-day) token; `tokens.yml` keeps it fresh.
5. Create a fine-grained GitHub token for this repo with **Secrets: read and write** → secret `GH_ADMIN_TOKEN`.

### 4. Video hosting for Instagram (secrets `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`)
Instagram fetches the video from a public URL. The engine uploads it to Supabase, waits for Instagram to
take it, then deletes it.
1. supabase.com → new project (free tier).
2. Storage → New bucket → name `reels`, **Public**.
3. Settings → API: copy the project URL and the `service_role` key.

### 5. Products (secrets `NOTION_TOKEN`, `NOTION_PARENT_PAGE_ID`, `GUMROAD_ACCESS_TOKEN`)
1. notion.so/profile/integrations → new internal integration → copy the secret.
2. Make a page called "Engine products" → `•••` → Connections → add the integration → copy the 32-character ID from its URL.
3. Gumroad → Settings → Advanced → Applications → create app → **Generate access token**. Payouts go to PayPal.

### 6. Go
Actions → **Preview reels** → Run. Download the artifact and watch the three starter reels.
If they look right, the daily job posts them from their `publish_on` dates.

## Run it locally

```
pip install -r requirements.txt && python -m playwright install chromium   # plus ffmpeg
python -m engine validate
python -m engine preview inversion        # 7 stills in a few seconds
python -m engine reel inversion           # full mp4 in build/reels/
python -m engine post inversion --dry-run # what would be sent
python -m engine site                     # build/site/
python -m engine product build decision-journal --dry-run
python -m engine status
```

`TTS_ENGINE=espeak` uses an offline robot voice for quick local checks; CI always uses the neural voice.

## Adding a format

- New reel layout: add a `case` in `engine/templates/reel.html` and its name to `LAYOUTS` in `engine/content.py`.
- New product type: a branch in `engine/products.py` (`validate`, `build`, `ship`) and its templates in `engine/templates/product/`.

Fonts: Fraunces and Inter, SIL Open Font License, bundled in `assets/fonts/`.
