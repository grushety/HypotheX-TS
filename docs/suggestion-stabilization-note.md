# Suggestion Stabilization Note

`HTS-504` keeps the first suggestion model explicit and easy to ablate.

Current stabilization heuristics:

- Prototype updates are confidence-gated.
- Prototype memory is bounded per label.
- Prototype drift can freeze a candidate update before it is stored.
- Duration smoothing merges too-short provisional segments into the more compatible neighbor.

Current defaults:

- `min_update_confidence = 0.75`
- `max_buffer_per_label = 8`
- `max_prototype_drift = 0.45`

Duration smoothing rules:

- Base minimum segment length comes from `durationLimits.minimumSegmentLength`.
- `event`, `transition`, and `periodic` use their class-specific minimum lengths when present.
- When a segment is too short, the smoother merges it into the neighboring segment with the stronger compatibility score.
- Compatibility is derived from the short segment's label probabilities, same-label bonus, neighbor confidence, and a small length tie-breaker.

This intentionally stops short of HSMM decoding or online encoder fine-tuning. The MVP goal is to reduce obvious jitter and prototype drift without hiding the behavior behind a harder-to-debug model layer.
