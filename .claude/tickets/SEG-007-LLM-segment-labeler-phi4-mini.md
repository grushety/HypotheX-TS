# SEG-007 — LLM segment labeler with Phi-4-mini (cold-start fix)

**Status:** [x] Done
**Depends on:** SEG-001

---

## Goal

> **Researcher action required after this ticket:** run the one-time model download before using LLM mode:
> ```bash
> cd backend
> python -c "
> from huggingface_hub import hf_hub_download
> hf_hub_download(repo_id='microsoft/Phi-3-mini-4k-instruct-gguf', filename='Phi-3-mini-4k-instruct-q4.gguf', local_dir='../benchmarks/models/llm_labeler')
> "
> ```
> No training required. The app works without it (falls back to prototype labeler).

Replace synthetic prototype templates as the cold-start labeler with a local LLM
(Phi-4-mini GGUF, int4, ~2.2GB) that assigns segment labels from natural language
descriptions of each segment's statistical properties.

**Why:** The current `build_default_support_segments()` uses idealized synthetic patterns
(perfect linear ramp, flat 0.25, pure sine) as prototypes. Real noisy signals land far
from these in embedding space, producing poor cold-start labels. An LLM can describe
what it observes in a segment and pick the correct label reliably without any training data.

**How it fits:** The LLM labeler is a cold-start drop-in only. Once the user makes
corrections and `adapt_model` updates prototypes (SEG-005), the prototype classifier
takes over as before. The LLM is never called after adaptation has begun.

**Model:** `microsoft/Phi-4-mini-instruct` GGUF int4
(`microsoft/Phi-3-mini-4k-instruct-gguf` as fallback if Phi-4-mini GGUF unavailable).
Model weight file downloaded once to `benchmarks/models/llm_labeler/` via
`huggingface_hub.hf_hub_download`. Not committed to git.

**New dependency:** `llama-cpp-python` added to `backend/requirements.txt`.
`torch` already present from SEG-002. No other new deps.

---

## Architecture

```
segment values
    → build_feature_matrix() [SEG-001]
    → _describe_segment(stats) → natural language string
    → Phi-4-mini GGUF prompt
    → constrained output: one label from active_chunk_types
    → LlmSegmentLabel(label, confidence, raw_response)
```

The LLM is called only when:
- No user corrections exist yet for this session (prototype memory is empty / default only)
- The caller passes `use_llm_cold_start=True` to `BoundarySuggestionService.propose()`

After any accepted correction triggers `adapt_model`, the flag is ignored and
prototype classification runs as before.

---

## Acceptance Criteria

- [ ] `backend/app/services/suggestion/llm_labeler.py` with:
  - `LlmLabelerConfig` frozen dataclass: `model_repo: str`, `model_filename: str`, `model_dir: str`, `n_ctx: int = 256`, `max_tokens: int = 8`, `temperature: float = 0.0`
  - `LlmSegmentLabel` frozen dataclass: `label: str`, `confidence: float`, `raw_response: str`
  - `LlmSegmentLabeler` class: lazy-loads model on first call, thread-safe singleton
  - `LlmSegmentLabeler.label_segment(values, active_labels) -> LlmSegmentLabel`
  - Falls back to `"other"` with `confidence=0.0` if model file not found — never raises
- [ ] `_describe_segment(values) -> str` function producing a 2-3 sentence description using: mean, std, slope (linear regression), max absolute deviation, whether periodic (autocorrelation at lag T/4), length. Example: `"Short segment of 12 points. Mean 0.3, std 0.02, slope near zero. Low variance, no clear trend."`
- [ ] Prompt format uses Phi-4-mini chat template:
  ```
  <|system|>You are a time series analyst. Reply with exactly one word.<|end|>
  <|user|>Classify this segment. Options: trend, plateau, spike, event, transition, periodic.
  {description}
  Reply with one word only.<|end|>
  <|assistant|>
  ```
- [ ] Output parsed by stripping and lowercasing; if not in `active_labels` → `"other"`
- [ ] `BoundarySuggestionService.propose()` accepts `use_llm_cold_start: bool = False`; when True and prototype memory is empty/default, calls `LlmSegmentLabeler` instead of prototype classifier
- [ ] Model downloaded via `huggingface_hub.hf_hub_download` on first call; path logged at INFO level
- [ ] `benchmarks/models/llm_labeler/` added to `.gitignore`
- [ ] `llama-cpp-python` and `huggingface_hub` added to `backend/requirements.txt`
- [ ] Tests cover: correct label on clear synthetic cases (pure trend, pure spike, pure plateau), fallback to "other" when model file missing, description output is a non-empty string
- [ ] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent — prompt design and label parsing verified
- [ ] Run `code-reviewer` agent — no blocking issues, no logic in route handlers
- [ ] `git commit -m "SEG-007: LLM segment labeler with Phi-4-mini for cold-start labeling"`
- [ ] Update Status to `[x] Done`

## Work Done

- `backend/app/services/suggestion/llm_labeler.py` — new module: `LlmLabelerConfig` frozen dataclass, `LlmSegmentLabel` frozen dataclass, `_describe_segment()` (length/mean/std/slope/MAD/autocorrelation-periodicity → 2-3 sentence description), `_flatten_to_1d()` helper, `LlmSegmentLabeler` class with thread-safe double-checked locking singleton (`get_instance()`), lazy `_load_model()` (huggingface_hub download + llama_cpp.Llama init, both behind a `_load_attempted` guard), `label_segment()` (Phi-4-mini chat template prompt, constrained to active_labels, graceful fallback to "other" on any failure)
- `backend/app/services/suggestions.py` — added `use_llm_cold_start: bool = False` to `propose()`; passed through to `_classify_segments()`; added `_label_segments_with_llm()` method that calls `LlmSegmentLabeler.get_instance().label_segment()` per segment when no support segments exist and cold-start is requested
- `backend/requirements.txt` — added `llama-cpp-python>=0.2.90` and `huggingface_hub>=0.24.0`
- `.gitignore` — added `benchmarks/models/llm_labeler/` to exclude downloaded GGUF weight
- `backend/tests/test_llm_labeler.py` — 31 unit tests: `_describe_segment` (9 cases: non-empty string, length included, mean, rising/falling/flat trend, single-point, empty, falling), `LlmLabelerConfig` defaults (5), fallback behaviour (7: "other" label, zero confidence, no raise, multivariate input, download error → _load_attempted=True, import error → graceful, no-retry after attempt), mock model (10: correct labels for trend/plateau/spike, confidence=1.0 on match, "other" on unrecognised, confidence=0.0 on unrecognised, raw_response lowercased and stripped, LlmSegmentLabel instance, raw_response stored, multivariate input)
