# SEG-002 — 1D-TCN encoder module (PyTorch)

**Status:** [x] Done
**Depends on:** SEG-001

---

## Goal

Replace the current heuristic segment encoder (resample + diff + summary stats) with a small
learned 1D Temporal Convolutional Network. The existing `encode_segment(values, config)` API
is preserved exactly — only the implementation behind it changes.

The encoder must be frozen at inference time (weights do not update online).
A checkpoint file is saved to `benchmarks/models/tcn_encoder/` and loaded at startup.
If no checkpoint exists, fall back silently to the heuristic encoder so the app still runs.

Add `torch` to `backend/requirements.txt`. Do not add any other new ML dependencies.

---

## Architecture

Small 1D-TCN (fits on CPU, no GPU required):
- Input: `X_feat` from SEG-001, resampled to fixed length (default 32)
- 3 causal conv layers: channels 32 → 64 → 64, kernel 3, dilation 1/2/4, ReLU
- Global average pool → linear projection → L2-normalized embedding of dim 64
- Parameter count target: < 50k total

Keep it small — this is a research tool, not a production model.

---

## Acceptance Criteria

- [ ] `TcnSegmentEncoder` class in `backend/app/services/suggestion/tcn_encoder.py` with `encode(X_feat) -> np.ndarray` method
- [ ] `torch` added to `backend/requirements.txt` (pin to `torch==2.3.*` CPU-only)
- [ ] `encode_segment` in `segment_encoder.py` uses `TcnSegmentEncoder` when a checkpoint exists, falls back to heuristic when it does not
- [ ] Checkpoint path: `benchmarks/models/tcn_encoder/encoder.pt`; loaded once at module import via `functools.lru_cache`
- [ ] `TcnEncoderConfig` dataclass: `embedding_dim: int = 64`, `resample_length: int = 32`, `channels: tuple = (32, 64, 64)`, `kernel_size: int = 3`
- [ ] Output embeddings are L2-normalized (same contract as current encoder)
- [ ] Fallback to heuristic encoder is silent (no exception, no warning spam) — log at DEBUG level only
- [ ] Tests cover: output shape `(embedding_dim,)`, L2 norm ≈ 1.0, fallback when no checkpoint, no gradient computation during inference (`torch.no_grad()`)
- [ ] `npm test` and `npm run build` still pass (frontend unaffected)

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass (`pytest backend/tests/ -x`)
- [ ] Run `algorithm-auditor` agent — architecture matches paper spec (TCN, frozen online, L2 norm)
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-002: 1D-TCN encoder module with PyTorch fallback"`
- [ ] Update Status to `[x] Done`

## Work Done

- `backend/app/services/suggestion/tcn_encoder.py` — new module: `TcnEncoderConfig` dataclass, `_build_tcn_model()` building a 3-layer causal TCN with dilations 1/2/4, `TcnSegmentEncoder` (frozen weights, `encode()` under `torch.no_grad()`), `load_tcn_encoder()` with `@lru_cache(maxsize=1)` returning None on any failure, `save_tcn_encoder_checkpoint()` helper
- `backend/app/services/suggestion/segment_encoder.py` — updated `encode_segment` to call `load_tcn_encoder()` and route through the TCN when a checkpoint is available; falls back silently to heuristic on any failure (DEBUG log only)
- `backend/requirements.txt` — added `torch==2.11.0` (CPU-only wheel; pinned to installed version on Python 3.14)
- `backend/tests/test_tcn_encoder.py` — 13 new tests covering: output shape `(embedding_dim,)`, dtype float64, L2 norm ≈ 1.0 across input lengths, wrong channel count raises ValueError, params require no grad, model in eval mode, no gradient accumulation, graceful fallback for missing/corrupt checkpoint, checkpoint round-trip produces identical embeddings, config serialisation defaults and round-trip
