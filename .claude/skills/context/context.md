# Project Context

Running log of feature-level changes. One short paragraph per finished ticket, appended at ticket-completion time as a DoD step.

Format: `## <PREFIX>-NNN <short title>` heading, followed by 1–4 sentences explaining what changed and why a future Claude Code instance needs to know it (architectural decisions, non-obvious wiring, paper references, gotchas). Skip routine implementation details — those live in code comments.

---

## SEG-014 STL/MSTL decomposition fitter (Cleveland 1990 / Bandara 2021)

Replaced stubs in `backend/app/services/decomposition/fitters/stl.py` and `mstl.py` with full implementations via statsmodels (requires `statsmodels>=0.14` in requirements.txt). `detect_dominant_period(X)` in `stl.py` returns `int` (single period) or `list[int]` (multiple) via FFT + ACF. Two non-obvious gotchas: (1) statsmodels MSTL sorts periods internally, so `valid_periods` must be sorted before naming `seasonal_{T}` columns or you get mislabeled components; (2) MSTL crashes with `UnboundLocalError` when `2*period >= n` for all requested periods — handled by an underdetermined fallback in `_fit_mstl_1d`. Dispatches: `("cycle", None)` → STL, `("cycle", "multi-period")` → MSTL. Tests: `backend/tests/test_stl_mstl_fitter.py` (37 tests).

## SEG-013 ETM decomposition fitter (Bevis-Brown 2014)

Replaced the linear-trend stub in `backend/app/services/decomposition/fitters/etm.py` with the full Bevis-Brown (2014) Eq. 1 ETM model: x₀ + linear rate + Heaviside steps + log/exp transients + sinusoidal harmonics, fitted via `np.linalg.lstsq`. `build_etm_design_matrix(t, known_steps, known_transients, harmonic_periods)` returns `(A, labels)` where labels follow Bevis-Brown naming (`x0`, `linear_rate`, `step_at_{t_s}`, `log_{t_r}_tau{τ}`, `sin_{T}`, etc.). Graceful underdetermined fallback (n < p) returns a constant-mean blob with `fit_metadata["underdetermined"] = True`. Multivariate (n, d) input fits channels independently and stacks. Registered as `"ETM"` and dispatched for `trend`, `step`, and `transient` shapes. Tests: `backend/tests/test_etm_fitter.py` (29 tests).

## UI-015 Audit log panel extension (tiered ops)

Added `frontend/src/components/audit/AuditLogPanel.vue` and supporting lib files (`createAuditLogPanelState.js`, `labelChipBus.js`). The panel merges existing audit events with label chip events (from OP-041's `labelChipBus` pub/sub) to display columns: tier, op, segment, pre→post shape, rule_class, compensation_mode, plausibility_badge, constraint_residual. Tier is derived from `operationCatalog.js` when no chip is present. Filter date values from `datetime-local` inputs must be normalised to ISO-8601 via `new Date().toISOString()` before passing to `createAuditLogPanelState` — the lib uses `new Date()` comparison internally. The component is not yet wired into `BenchmarkViewerPage.vue`; mount it inside the `history-strip` details block when ready.
