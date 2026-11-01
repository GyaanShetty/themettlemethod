# Weekly: write next week's website lessons

The website publishes something new every day across three tracks: mental models (also reels; written by
`plan_models.md`), concepts and skills. You write the concepts and skills, 7 days ahead.

## 1. Read the state
Read `engine.yaml` and every file in `content/concepts/` and `content/skills/`. Find the latest `publish_on`
per track. Never repeat a topic or a close variant.

## 2. Pick
- **Concepts** (4 a week): big ideas from economics, science, computing, psychology, history.
  Good: compound interest, entropy, network effects, Bayes' rule, opportunity cost in time. Each needs one
  concrete worked example with numbers.
- **Skills** (3 a week): practical skills a person can learn alone in days to weeks. Good: touch typing,
  speed reading critically, writing a cold email, basic SQL, public speaking basics, negotiating a salary.
  No medical, legal or investment advice; teach the skill, not what to buy.
- Alternate days so something new goes live every day.

## 3. Write
Copy `content/concepts/compound-interest.yaml` or `content/skills/touch-typing.yaml` exactly.
- `article`: 250–450 words of markdown, short paragraphs, `##` subheadings, ends with a "Try it" or similar
  section. Plain words; define jargon on first use.
- Skills also need `level` (Beginner / Intermediate / Advanced), `time_to_learn`, 4–6 `steps` with `title` and
  `detail`, and `resources` (real URLs you opened; mark free ones `free: true`).
- `sources`: real pages you opened for any fact, figure or quote.
- Quote any YAML string containing a colon.

## 4. Check and commit
`python -m engine validate`, fix every error, commit only the new YAML files as `learn: <slugs>`, push to `main`.
The site rebuilds every morning and publishes whatever is due.
