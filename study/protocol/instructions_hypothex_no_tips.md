# Instructions — HypotheX-TS without tip engine (`hypothex_no_tips`)

Locked at OSF registration. Render to PDF for participants:
`pandoc instructions_hypothex_no_tips.md -o instructions_hypothex_no_tips.pdf`.

> **Same content as the `hypothex_tips` instructions** except the
> tip-engine paragraph is removed. We deliberately keep all other
> wording verbatim so the only between-condition difference at the
> instruction level is the tip-engine availability — not the framing.

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
