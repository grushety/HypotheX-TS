# VAL-001 — Conformal-PID prediction-band check (per-edit, fast path)

**Status:** [x] Done
**Depends on:** OP-050 (CF coordinator), forecaster API

---

## Goal

Compute the conformal prediction interval `[ŷ_h − q̂_α^h, ŷ_h + q̂_α^h]` for the model's forecast at horizon h, before and after each Tier-1/2/3 edit, and decide whether the **prediction shift exceeds the model's natural noise floor**. Use the Conformal PID Control algorithm (Angelopoulos–Candès–Tibshirani NeurIPS 2023) for adaptive intervals under non-stationarity.

**Why:** Without a calibrated noise floor, every prediction shift looks meaningful. CP-PID gives finite-sample marginal coverage without exchangeability assumptions — essential under the non-stationarity that BFAST/LandTrendr edits routinely produce. This is the single most important per-edit metric for telling the user whether their edit *actually* moved the prediction.

**How it fits:** Foundational fast-path metric. Runs on every edit committed via OP-050. Produces `band_check ∈ {within, exceeds_α=0.1, exceeds_α=0.05}` consumed by UI plausibility badge and tip engine (VAL-020).

---

## Paper references (for `algorithm-auditor`)

- Stankevičiūtė, Alaa, van der Schaar, **"Conformal Time-series Forecasting,"** NeurIPS 2021. OpenReview Rx9dBZaV_IP.
- Xu & Xie, **"Conformal Prediction for Time-Series,"** IEEE TPAMI 2023, arXiv 2010.09107 (orig. ICML 2021).
- Angelopoulos, Candès, Tibshirani, **"Conformal PID Control for Time Series Prediction,"** NeurIPS 2023, arXiv 2307.16895.
- Zaffran, Féron, Goude, Josse, Dieuleveut, **"Adaptive Conformal Predictions for Time Series,"** ICML 2022, PMLR 162:25834.

---

## Pseudocode

```python
class ConformalPIDValidator:
    def __init__(self, forecaster, calibration_set, alpha=0.1, K_p=0.5, K_i=0.1):
        self.forecaster = forecaster
        self.alpha      = alpha
        self.K_p, self.K_i = K_p, K_i           # PID gains
        self.q_history  = []                    # rolling quantile estimate
        self._calibrate(calibration_set)

    def _calibrate(self, cal):
        residuals = [abs(y - self.forecaster.predict(x)) for x, y in cal]
        self.q_history.append(np.quantile(residuals, 1 - self.alpha))

    def update(self, y_true, y_pred):
        # PID-style adaptive quantile update (Angelopoulos 2023 Eq. 4)
        err = abs(y_true - y_pred) - self.q_history[-1]
        q_next = self.q_history[-1] + self.K_p * err + self.K_i * sum(self.q_history[-10:]) / 10
        self.q_history.append(max(q_next, 0))

    def band_check(self, y_pre, y_post) -> BandCheckResult:
        q = self.q_history[-1]
        delta = abs(y_post - y_pre)
        return BandCheckResult(
            delta=delta, band_width=q,
            verdict='within' if delta < q
                   else 'exceeds_alpha=0.1' if delta < 2*q
                   else 'exceeds_alpha=0.05',
            band=(y_post - q, y_post + q),
        )
```

---

## Acceptance Criteria

- [x] `backend/app/services/validation/conformal_pid.py` with:
  - `BandCheckResult` frozen dataclass: `delta`, `band_width`, `verdict ∈ {'within', 'exceeds_alpha=0.1', 'exceeds_alpha=0.05'}`, `band: (lo, hi)`
  - `ConformalPIDValidator` class with `_calibrate`, `update`, `band_check`
  - `K_p` and `K_i` PID gains exposed in `ConformalConfig` (defaults from Angelopoulos 2023 Table 1)
- [x] Calibration runs offline once per dataset; results cached to `backend/app/services/validation/cache/conformal_calibration_<dataset>.json`
- [x] `band_check(y_pre, y_post)` runs in O(1) — verified by perf test ≤ 5 ms on reference hardware
- [x] Under non-stationarity (synthetic series with mean shift mid-stream), CP-PID interval widens; static split-CP would lose coverage — asserted by simulation test
- [x] `verdict='within'` when `|Δŷ| < q̂_α` — UI tip engine reads this and shows "edit within natural noise floor"
- [x] OP-050 calls `band_check` after each edit; result attached to `CFResult.validation.conformal`
- [x] Marginal coverage on held-out tail: `1 − α ± 0.02` over rolling window of 100 (asserted by integration test)
- [x] Tests: calibration determinism; PID update correctness vs Angelopoulos 2023 Eq. 4; band-check verdict thresholds; non-stationary widening; coverage on held-out

## Result Report

**Implementation summary.** Added `backend/app/services/validation/` package with `ConformalPIDValidator`, three frozen DTOs (`BandCheckResult`, `ValidationResult`, `ConformalConfig`), a `Forecaster` Protocol, and a JSON calibration cache at `validation/cache/conformal_calibration_<dataset>.json`. Wired the validator into `synthesize_counterfactual` via two optional kwargs (`validator`, `pre_segment`); when both are supplied, the coordinator computes `y_pre = forecaster(pre_segment)` and `y_post = forecaster(X_edit)` and attaches the resulting `BandCheckResult` to a new `CFResult.validation.conformal` field (default `None` → existing OP-050 callers untouched).

**Pseudocode-vs-paper deviation.** The ticket pseudocode shows a residual-gap update (`err = |y − ŷ| − q`); that controller converges to a function of `E[|residual|]` and does not target 1 − α coverage. The Acceptance Criteria require both "Angelopoulos 2023 Eq. 4 correctness" and 1 − α ± 0.02 marginal coverage on a held-out tail. Only the paper's miscoverage-indicator form (`err = 1{|y − ŷ| > q} − α`) satisfies both, so the implementation follows the paper. The deviation is documented in `update()`'s docstring. Default gains: `K_p=0.5, K_i=0.1, integral_window=10` (Angelopoulos 2023 Table 1).

**Tests.** 26 new tests across calibration determinism, PID update correctness (1-step proportional + integral, anti-windup window, zero-clipping), verdict ladder (`within / exceeds_alpha=0.1 / exceeds_alpha=0.05` with band centred on `y_post`), non-stationary widening (mean-shift synthetic series), static-split-CP coverage loss, held-out marginal coverage (rolling-100 hit-rate within 0.02 of 1 − α), O(1) perf budget (≤ 5 ms over 1000 calls), JSON cache round-trip + α/K_p/K_i/integral_window mismatch guard, OP-050 wiring (validation present / absent / pre_segment-required-when-validator).

**Test results.** `test_conformal_pid.py`: 26/26. `test_cf_coordinator.py`: 37/37 (no regressions from the new `validation` field). Frontend: 645/645. Three pre-existing failures in unrelated modules (`test_segmentation_eval.py` import name, `test_operation_result_contract.py` missing fixture file, `test_segment_encoder_feature_matrix.py` embedding-size drift) were already broken on `main` and are out of scope for VAL-001.

**Code review.** APPROVE, 0 blocking. Two correctness NITs addressed inline: cache validator now compares all four config fields (was alpha-only); removed dead `max(q0, 0.0)` after `np.quantile` over `abs(...)` residuals. Other NITs (forecaster try/except wrapper, `validator.score_edit` helper, length-check between pre/post arrays) deferred — none are contract violations and adding them would be scope creep on a fast-path validator.

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "VAL-001: conformal-PID prediction-band check (per-edit fast path)"` ← hook auto-moves this file to `done/` on commit
