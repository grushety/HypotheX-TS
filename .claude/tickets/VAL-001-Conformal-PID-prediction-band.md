# VAL-001 — Conformal-PID prediction-band check (per-edit, fast path)

**Status:** [ ] Done
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

- [ ] `backend/app/services/validation/conformal_pid.py` with:
  - `BandCheckResult` frozen dataclass: `delta`, `band_width`, `verdict ∈ {'within', 'exceeds_alpha=0.1', 'exceeds_alpha=0.05'}`, `band: (lo, hi)`
  - `ConformalPIDValidator` class with `_calibrate`, `update`, `band_check`
  - `K_p` and `K_i` PID gains exposed in `ConformalConfig` (defaults from Angelopoulos 2023 Table 1)
- [ ] Calibration runs offline once per dataset; results cached to `backend/app/services/validation/cache/conformal_calibration_<dataset>.json`
- [ ] `band_check(y_pre, y_post)` runs in O(1) — verified by perf test ≤ 5 ms on reference hardware
- [ ] Under non-stationarity (synthetic series with mean shift mid-stream), CP-PID interval widens; static split-CP would lose coverage — asserted by simulation test
- [ ] `verdict='within'` when `|Δŷ| < q̂_α` — UI tip engine reads this and shows "edit within natural noise floor"
- [ ] OP-050 calls `band_check` after each edit; result attached to `CFResult.validation.conformal`
- [ ] Marginal coverage on held-out tail: `1 − α ± 0.02` over rolling window of 100 (asserted by integration test)
- [ ] Tests: calibration determinism; PID update correctness vs Angelopoulos 2023 Eq. 4; band-check verdict thresholds; non-stationary widening; coverage on held-out

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "VAL-001: conformal-PID prediction-band check (per-edit fast path)"` ← hook auto-moves this file to `done/` on commit
