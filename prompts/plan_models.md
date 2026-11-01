# Weekly: write next week's mental models

You keep the reel queue 7 days ahead. Each file in `content/models/` becomes a ~40-second reel
(Instagram + YouTube Shorts), a page on the website and a card in the deck.

## 1. Read the state

- Read `engine.yaml`, `state.json` and every file in `content/models/`.
- Find the latest `publish_on` date and the highest `number`.
- Count queued models (publish_on after today). If 7 or more are queued, stop and say so.

## 2. Pick the models

Write enough to fill the queue to 7, one per day, continuing the dates and numbers.

- Never repeat a model already covered, or a close variant.
- Mix categories across the week: decision making, probability, systems, psychology, economics, self-knowledge, learning.
- Prefer models with a concrete, surprising example or a real quote from a named person.
- Look up every quote, date and attribution before using it (open the source page, not only a search snippet).
  If a story is disputed, say "the story goes" in the script, like `second-order-thinking.yaml` does.
- No health, medical or financial advice. Teach the thinking tool, not what to buy or take.

## 3. Write each `content/models/<slug>.yaml`

Copy the structure of `content/models/inversion.yaml` exactly.

- Scenes: `hook` first, `title` second, `cta` last. In between, 3–5 scenes using `statement`, `list`,
  `versus`, `quote`. Use at least two different middle layouts.
- `hook.text`: under 8 words, a claim that makes a scroller stop. Not a question starting with "Did you know".
- The whole script (all `say` lines) is 75–140 words. Write for the ear: short sentences, no parentheses,
  no abbreviations, numbers as words when spoken naturally.
- On-screen `text` and `title` are 90 characters max; shorter is better.
- `cta.say` stays "Follow for one mental model every day."
- `caption`: 2–4 lines, first line restates the model plainly, last line gives one thing to try today.
- `tags`: 5–8, lowercase, no #.
- `article`: 200–400 words of markdown for the website, including a `## How to use it` section with a
  numbered list of 3–5 steps (the card deck reads this section), and one concrete example.
- `sources`: real URLs you opened.
- Quote any YAML string that contains a colon or starts with a quote mark.

## 4. Check and commit

```
pip install -r requirements.txt
python -m engine validate
TTS_ENGINE=espeak python -m engine preview <slug>     # optional: look at the stills
```

Fix every error. Commit only the new files in `content/models/` with the message `models: <slugs>` and push to `main`.
The preview workflow renders them with the real voice so the owner can watch before they post.

Reply with the list of models, their dates, and one line on why each one.
