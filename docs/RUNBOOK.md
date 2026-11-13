# Runbook

How to run the order in a few hours a week. The War Room shows the state; GitHub is where you act.

- War Room: https://claude.ai/artifact/TWKL9FofnU7wByq2GLnLZ3 (reads live through your Supabase connection)
- Repo: https://github.com/GyaanShetty/themettlemethod

## Daily (5 minutes)

1. Open the War Room. Look at Today: failed publishes should be 0.
2. If GitHub has opened an issue titled "Publish failed", read it, fix the cause, and re-run the `Daily` workflow. A re-run never posts twice.
3. Reply in the hall and in comments.

## Weekly (1 to 2 hours)

1. Run the planner prompts in `prompts/` to draft next week's atoms. They arrive as a pull request.
2. Read each atom. Fix the headline (three lines at most, sentence case, a full stop). Set `status: approved`. Merge. Only approved atoms can ever post.
3. Check the `Tests` run on the pull request is green, and look at the rendered plates in its `renders` artifact.
4. Review the funnel and money sections. Pick next week's product or campaign.

## Monthly

1. Run `scripts/backup.sh` from your own machine and keep the file somewhere private.
2. Check the `Refresh Instagram token` workflow ran.
3. Read the Supabase advisors (Database > Advisors). Security should be empty.

## How to

**Add an atom.** Copy a file in `content/models/`, change the fields, open a pull request. `python -m engine validate` and the tests tell you what is wrong. `python -m engine render <id>` draws its plate, story and carousel into `build/social/<id>/`.

**Send one atom now.** Actions > Daily > Run workflow, with the atom's id. It is a dry run unless publishing is live.

**Hold an atom.** Set `status: held` in its YAML and merge.

**Ship a product.** Add `products/<slug>.yaml`. The `Build products` workflow builds it and opens a review issue. Comment `/ship` to publish, `/ship-draft` for a Gumroad draft, `/reject <reason>` to drop it.

**Change a price.** In the Supabase SQL editor:
`update public.config set value = '9', updated_at = now() where key = 'price_inner_monthly';`
Do the same for `price_inner_yearly` and set `inner_checkout_url` to the Gumroad membership link in quotes, for example `'"https://..."'`. Until both a price and a link are set, the Inner Order page shows [PRICE] and "The gates are not open yet."

**Make yourself an admin.** After your first sign-in on the site:
`insert into public.admins (user_id) select id from auth.users where email = '<your email>';`

**Go live.** Add the secrets in `docs/SECRETS.md`, run `Daily` once and read its dry-run output, then:
`update public.config set value = 'true', updated_at = now() where key = 'publish_live';`
To stop everything at once, set it back to `'false'`.

## The five most likely failures

1. **A channel says "not connected".** A secret is missing or misnamed. The `Daily` run prints which, by name. Add it and re-run.
2. **Instagram rejects a post.** Usually an expired token (run `Refresh Instagram token`) or an app still in review. The atom's other channels are unaffected.
3. **YouTube uploads arrive private.** The API project has not passed YouTube's audit. Submit the audit form; flip each Short to public by hand until it passes.
4. **A render fails with "overflow" or "headline runs to 4 lines".** The text does not fit the plate. Shorten the headline or the sub. This is the build protecting the layout, not a bug.
5. **A member paid but is still in the Outer Court.** The ping did not match them. Check `subscriptions` for their email; if the row has no `user_id`, they paid with a different email from their sign-in. Set `user_id` on that row, then run `select public.nightly();` to settle tiers and circles.
