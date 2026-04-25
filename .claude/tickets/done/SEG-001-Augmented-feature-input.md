# SEG-001 — Augmented feature input for segment encoder

**Status:** [x] Done
**Depends on:** HTS-502

---

## Goal

Replace the raw-signal-only encoder input with an augmented feature matrix `X_feat ∈ R^(T × d')`.
The paper specifies: raw signal + smoothed signal + first difference Δx + local z-score + missingness mask.
This is a pure data-layer change — the existing `encode_segment` API signature stays identical.

Current encoder resamples raw values only. After this ticket every downstream call to `encode_segment`
gets richer features without touching prototype classifier, boundary proposer, or route code.

---

## Acceptance Criteria

- [ ] `build_feature_matrix(values, config)` function in `segment_encoder.py` returns augmented array with channels:
  raw, smoothed (Gaussian or rolling mean), Δx (first diff, prepended with 0), local z-score (per-channel,
  window-based), missingness mask (1 where NaN/inf, else 0)
- [ ] `encode_segment` calls `build_feature_matrix` internally — signature unchanged
- [ ] `SegmentEncoderConfig` has new fields: `smoothing_window: int = 5`, `zscore_window: int = 10`,
  `include_missingness_mask: bool = True`; all default to backwards-compatible values
- [ ] Existing tests still pass without modification
- [ ] New tests cover: feature matrix shape, missingness flag, z-score zero mean on clean signal
- [ ] `requirements.txt` unchanged (NumPy only, no new deps)

## Definition of Done

- [ ] Run `test-writer` agent — all tests pass (`pytest backend/tests/ -x`)
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-001: augmented feature input for segment encoder"`
- [ ] Update Status to `[x] Done`

## Work Done

- `backend/app/services/suggestion/segment_encoder.py` — added `build_feature_matrix()` (raw + rolling-mean smooth +
  Δx + local z-score + missingness mask channels), added `_rolling_mean()` and `_local_zscore()` helpers with source
  citations, added `smoothing_window`/`zscore_window`/`include_missingness_mask` fields to `SegmentEncoderConfig`,
  updated `encode_segment` to call `build_feature_matrix` and use the raw channel(s) from it (full feature matrix
  reserved for the TCN encoder in SEG-002)
- `backend/tests/test_segment_encoder_feature_matrix.py` — 19 new tests covering feature matrix shape (1-D and
  multi-channel, with/without mask), missingness flag correctness (NaN, ±inf, clean signal), local z-score near-zero
  mean and finite values, new config field defaults, and encode_segment NaN handling via feature matrix
