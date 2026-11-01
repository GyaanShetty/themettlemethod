# Twice a month: write the next product spec

You add one new product to `products/`. A push builds it and opens a review issue; nothing sells
until the owner comments `/ship`.

## 1. Read the state

- Read `engine.yaml`, `state.json`, every spec in `products/`, and the titles in `content/models/`.
- Rejected products in `state.json` carry a reason. Don't repeat the mistake.
- If 2 or more products are built but not shipped, stop: the owner has a review backlog.

## 2. Pick the product

Everything sold sits under one brand: thinking better, deciding better, self-improvement through
mental models. A buyer who liked the reels should want it.

- Notion templates (`type: notion`): self-help systems built around the models. Good directions:
  a weekly review using mental models, a reading-notes system that maps books to models, a goal planner
  using inversion and pre-mortems, a learning tracker built on the circle of competence.
- Name a buyer you can describe in 5+ words ("students who journal but never review their decisions").
- Avoid: generic life OS, habit trackers, mood trackers, anything clinical or medical.
- Do 2–3 web searches to check what already exists on Gumroad and the Notion Marketplace at what price.

## 3. Write `products/<slug>.yaml`

Copy `products/decision-journal.yaml`.

- 3–6 databases, at least two relations, at least one rollup or formula. Linked data is the value.
- Column types: rich_text number select multi_select date checkbox url email phone_number files relation rollup formula.
  Never `status` (the API can't create it).
- 3–6 realistic sample rows per database; relations reference rows as `<db key>.<row key>`.
- Dates as `"+30d"` or `"-10d"` so samples stay current.
- `listing.price` in USD, usually 12–29. `views`: the board/calendar views a human should add.
- Quote every string containing a comma or colon.

## 4. Check and commit

```
python -m engine product validate
python -m engine product build <slug> --dry-run
```

Fix every error. Commit only `products/<slug>.yaml` as `product: <slug>` and push to `main`.
Reply with the product, the buyer, the price, and what competing listings charge.
