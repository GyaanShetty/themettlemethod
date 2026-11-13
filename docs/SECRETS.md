# Secrets

Every secret lives in one of two places and nowhere else. Never paste one into a chat, an issue or a file.

- **GitHub**: repo Settings > Secrets and variables > Actions. "Secret" unless marked "variable".
- **Supabase**: project `themettlemethod` > Edge Functions > Secrets.

A channel with a missing secret shows "not connected" and runs as a dry run. Nothing else breaks.

## Needed first

| Name | Where | What it is for | Where to get it |
|---|---|---|---|
| `SUPABASE_URL` | GitHub | Lets the daily and nightly jobs reach the database | Supabase > Project Settings > API > Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | GitHub | Server-side writes: content mirror, publish records, media uploads. Never in the browser | Supabase > Project Settings > API > service_role key |
| `CRON_SECRET` | GitHub and Supabase, same value | Proves the nightly call comes from your workflow | Make one: `openssl rand -hex 32` |
| `SUPABASE_ACCESS_TOKEN` | GitHub | Lets `functions.yml` redeploy Edge Functions from main | supabase.com/dashboard/account/tokens |
| `SITE_URL` | Supabase | Link used in the flame note | Your Pages URL, later the domain |

`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set inside Edge Functions by Supabase itself.

## Payments (Gumroad)

| Name | Where | What it is for | Where to get it |
|---|---|---|---|
| `GUMROAD_WEBHOOK_SECRET` | Supabase | The token on the webhook URL | Make one: `openssl rand -hex 32` |
| `GUMROAD_SELLER_ID` | Supabase | Rejects pings that are not about your account | Gumroad > Settings > Advanced, or the `seller_id` on any ping |
| `GUMROAD_INNER_PERMALINK` | Supabase | Tells the Inner Order membership apart from products | The membership's product URL |
| `GUMROAD_ACCESS_TOKEN` | GitHub and Supabase | Shipping products; daily sales count | Gumroad > Settings > Advanced > Applications |

Then in Gumroad > Settings > Advanced, set the Ping URL to
`https://zcdszmvktizxydwgehsr.supabase.co/functions/v1/payments-webhook?provider=gumroad&token=<GUMROAD_WEBHOOK_SECRET>`
and subscribe the same URL to `cancellation`, `subscription_ended` and `refund`.

`STRIPE_WEBHOOK_SECRET` and `RAZORPAY_WEBHOOK_SECRET` (Supabase) are only needed if you add those providers.

## Channels

| Name | Where | What it is for | Where to get it |
|---|---|---|---|
| `IG_ACCESS_TOKEN` | GitHub and Supabase | Posting to Instagram; daily insights | developers.facebook.com > your app > Instagram > API setup. Needs `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_insights` |
| `GH_ADMIN_TOKEN` | GitHub | Lets `tokens.yml` refresh the Instagram token monthly | A fine-grained GitHub token for this repo with Secrets: read and write |
| `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | GitHub and Supabase | Uploading Shorts; subscriber count | Google Cloud > YouTube Data API v3 > OAuth client. See the README |
| `THREADS_ACCESS_TOKEN` | GitHub and Supabase | Posting threads; daily insights | developers.facebook.com > your app > Threads. Needs `threads_basic`, `threads_content_publish`, `threads_manage_insights` |
| `EMAIL_PROVIDER` | GitHub variable | `resend` or `buttondown` | Your choice |
| `EMAIL_FROM` | GitHub variable and Supabase | The sender address | A verified sender at your provider |
| `RESEND_API_KEY`, `RESEND_AUDIENCE_ID` | GitHub; the key also in Supabase | Morning lesson and the flame note | resend.com |
| `BUTTONDOWN_API_KEY` | GitHub | Morning lesson, if you pick Buttondown. It cannot send the flame note | buttondown.com > Settings > API |
| `NOTION_TOKEN`, `NOTION_PARENT_PAGE_ID` | GitHub | Building Notion templates | notion.so/my-integrations |

Meta and YouTube both need their app reviewed before posts are public. Until then, leave the channel unconnected or expect private uploads.

## Not secrets

The Supabase publishable key in `web/assets/js/mettle.js` is meant to be public. Row-level security is what protects the data.
