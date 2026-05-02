# Instructions — HypotheX-TS with tip engine (`hypothex_tips`)

Locked at OSF registration. Render to PDF for participants:
`pandoc instructions_hypothex_tips.md -o instructions_hypothex_tips.pdf`.

---

## What you'll do

You'll see 8 short time-series plots (4 easy, 4 hard). For each one:

1. The system shows you the original signal and the model's prediction.
2. You'll **construct a counterfactual** — an edited version of the
   signal that, if it had occurred instead, would have made the model
   predict a different class.
3. You rate your confidence in your edit on a 0–100 slider.
4. You judge whether your edited signal is plausible (yes/no).

We're interested in *how* you arrive at the counterfactual, not whether
you get it right on the first try.

## The HypotheX-TS interface

You'll have access to:

- **Decomposition editor** — break the signal into named pieces
  (e.g. trend, cycle, noise) and edit each one independently. The
  pieces follow a 7-shape vocabulary: `plateau, trend, step, spike,
  cycle, transient, noise`.
- **Operation palette** — three tiers of edits, from raw replacement
  (Tier 1) through coefficient edits (Tier 2) to global structural
  edits (Tier 3).
- **Guardrails sidebar** — shows session-level metrics (shape coverage,
  diversity, validity rate, cherry-picking risk).
- **Tip engine** — short, dismissible guidance messages that appear
  below the operation palette when an edit triggers a known caveat
  (e.g. "this CF is fragile under small jitter").

The tip engine emits at most 3 tips per edit. You can dismiss any tip
without consequence.

## Practice and attention checks

- 2 practice trials with feedback; you can ask the experimenter
  questions during practice.
- 3 attention checks scattered through the practice + main trials.
  ≥ 2 of 3 must pass.

## Time

≈ 1 hour total. You may take a break between trials but not within a
trial.

## Compensation

£15/hour, paid via Prolific on completion.
