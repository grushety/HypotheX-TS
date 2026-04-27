# Project Context

Running log of feature-level changes. One short paragraph per finished ticket, appended at ticket-completion time as a DoD step.

Format: `## <PREFIX>-NNN <short title>` heading, followed by 1–4 sentences explaining what changed and why a future Claude Code instance needs to know it (architectural decisions, non-obvious wiring, paper references, gotchas). Skip routine implementation details — those live in code comments.

---

## SEG-014 STL/MSTL decomposition fitter (Cleveland 1990 / Bandara 2021)

Replaced stubs in `backend/app/services/decomposition/fitters/stl.py` and `mstl.py` with full implementations via statsmodels (requires `statsmodels>=0.14` in requirements.txt). `detect_dominant_period(X)` in `stl.py` returns `int` (single period) or `list[int]` (multiple) via FFT + ACF. Two non-obvious gotchas: (1) statsmodels MSTL sorts periods internally, so `valid_periods` must be sorted before naming `seasonal_{T}` columns or you get mislabeled components; (2) MSTL crashes with `UnboundLocalError` when `2*period >= n` for all requested periods — handled by an underdetermined fallback in `_fit_mstl_1d`. Dispatches: `("cycle", None)` → STL, `("cycle", "multi-period")` → MSTL. Tests: `backend/tests/test_stl_mstl_fitter.py` (37 tests).

## SEG-013 ETM decomposition fitter (Bevis-Brown 2014)

Replaced the linear-trend stub in `backend/app/services/decomposition/fitters/etm.py` with the full Bevis-Brown (2014) Eq. 1 ETM model: x₀ + linear rate + Heaviside steps + log/exp transients + sinusoidal harmonics, fitted via `np.linalg.lstsq`. `build_etm_design_matrix(t, known_steps, known_transients, harmonic_periods)` returns `(A, labels)` where labels follow Bevis-Brown naming (`x0`, `linear_rate`, `step_at_{t_s}`, `log_{t_r}_tau{τ}`, `sin_{T}`, etc.). Graceful underdetermined fallback (n < p) returns a constant-mean blob with `fit_metadata["underdetermined"] = True`. Multivariate (n, d) input fits channels independently and stacks. Registered as `"ETM"` and dispatched for `trend`, `step`, and `transient` shapes. Tests: `backend/tests/test_etm_fitter.py` (29 tests).

## SEG-011 Prototype encoder + classifier (few-shot, real corrections only)

`PrototypeShapeClassifier` added to `backend/app/services/suggestion/prototype_classifier.py`, alongside the legacy `PrototypeChunkClassifier`. Uses the 7-shape vocabulary (`SHAPE_LABELS`), computing L2-normalized mean prototypes exclusively from `provenance='user'` support segments (synthetic/template are hard-rejected). `BoundarySuggestionService.propose()` activates it when ≥ 5 corrections per class exist across ≥ 4 of 7 shape classes; below threshold it falls back to SEG-008 rule-based. A two-way label bridge (`_DOMAIN_TO_SHAPE`, `_PRIMITIVE_TO_DOMAIN` in `suggestions.py`) handles the mismatch between the 7-shape vocab and the 6-label domain vocab (`event↔transient`, `transition↔step`, `periodic↔cycle`). The `PrototypeShapeClassifier` is DI-injected as `self._shape_classifier` in `BoundarySuggestionService.__init__`. Evaluation fixture in `test_prototype_classifier.py` uses spike signals of length 30 (> `spike_max_len=20` rule threshold) to guarantee the prototype classifier outperforms the rule classifier by ≥ 3 pts macro F1 — the rule classifier misclassifies all long spikes while the prototype classifier embeds them correctly.

## UI-015 Audit log panel extension (tiered ops)

Added `frontend/src/components/audit/AuditLogPanel.vue` and supporting lib files (`createAuditLogPanelState.js`, `labelChipBus.js`). The panel merges existing audit events with label chip events (from OP-041's `labelChipBus` pub/sub) to display columns: tier, op, segment, pre→post shape, rule_class, compensation_mode, plausibility_badge, constraint_residual. Tier is derived from `operationCatalog.js` when no chip is present. Filter date values from `datetime-local` inputs must be normalised to ISO-8601 via `new Date().toISOString()` before passing to `createAuditLogPanelState` — the lib uses `new Date()` comparison internally. The component is not yet wired into `BenchmarkViewerPage.vue`; mount it inside the `history-strip` details block when ready.
