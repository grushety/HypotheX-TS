# Instructions — Native Guide CF baseline (`native_guide`)

Locked at OSF registration. Render to PDF for participants:
`pandoc instructions_native_guide.md -o instructions_native_guide.pdf`.

> **Baseline condition.** Participants have access to the Native Guide
> tool only — Delaney, Greene, Keane (ICCBR 2021). No decomposition
> editor, no Guardrails sidebar, no tip engine.

---

## What you'll do

You'll see 8 short time-series plots (4 easy, 4 hard). For each one:

1. The system shows you the original signal and the model's prediction.
2. The Native Guide tool proposes a counterfactual — an example from
   the training set, of the *opposite* class, that is closest to your
   signal under DTW distance.
3. You can accept the proposal as your counterfactual, or generate
   the next-closest proposal.
4. You rate your confidence in the chosen counterfactual on a 0–100
   slider.
5. You judge whether the chosen counterfactual is plausible (yes/no).

We're interested in *how* you arrive at the counterfactual, not whether
you get it right on the first try.

## The Native Guide interface

- **Proposal panel** — top-K nearest unlike-neighbour examples ranked
  by DTW distance.
- **Accept / next-proposal buttons** — your only edit affordance.

You cannot modify the proposed counterfactual; you can only choose
which proposal to accept.

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
