"""Conformal-PID prediction-band check (VAL-001).

Implements the adaptive prediction-interval algorithm of:

  Angelopoulos, Candès, Tibshirani, "Conformal PID Control for Time Series
  Prediction," NeurIPS 2023, arXiv:2307.16895 — Eq. 4 (proportional + integral
  quantile update under non-stationarity).

Companion references (split-CP / ACI variants the calibration step builds on):
  - Stankevičiūtė, Alaa, van der Schaar, "Conformal Time-series Forecasting,"
    NeurIPS 2021 (OpenReview Rx9dBZaV_IP).
  - Xu & Xie, "Conformal Prediction for Time-Series," IEEE TPAMI 2023,
    arXiv:2010.09107.
  - Zaffran et al., "Adaptive Conformal Predictions for Time Series,"
    ICML 2022, PMLR 162:25834.

Per-edit usage (fast path, OP-050):

    validator = ConformalPIDValidator(forecaster, calibration_set=cal,
                                      dataset_name="ECG200")
    band = validator.band_check(y_pre, y_post)   # O(1)

The verdict thresholds match the ticket's Acceptance Criteria:

    |Δŷ| < q̂_α                 → 'within'
    q̂_α ≤ |Δŷ| < 2·q̂_α          → 'exceeds_alpha=0.1'
    |Δŷ| ≥ 2·q̂_α                → 'exceeds_alpha=0.05'

(`q̂_α` is the rolling PID quantile estimate; doubling tracks the standard
inflation factor used to map the α=0.1 marginal interval onto an α=0.05
coverage bound under symmetric residuals.)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ConformalCalibrationError(RuntimeError):
    """Raised when calibration cannot be performed or loaded."""


# ---------------------------------------------------------------------------
# Forecaster protocol
# ---------------------------------------------------------------------------


class Forecaster(Protocol):
    """Minimal contract a model must satisfy to be wrapped by the validator.

    A forecaster maps a context array ``x`` to a single scalar prediction
    ``ŷ_h`` at horizon ``h``. The horizon is fixed by the forecaster — the
    validator is horizon-agnostic.
    """

    def predict(self, x: np.ndarray) -> float:  # pragma: no cover - protocol
        ...


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


VERDICT_WITHIN = "within"
VERDICT_EXCEEDS_10 = "exceeds_alpha=0.1"
VERDICT_EXCEEDS_05 = "exceeds_alpha=0.05"
_ALLOWED_VERDICTS = frozenset({VERDICT_WITHIN, VERDICT_EXCEEDS_10, VERDICT_EXCEEDS_05})


@dataclass(frozen=True)
class BandCheckResult:
    """Outcome of a single per-edit prediction-band check.

    Attributes:
        delta:       |y_post − y_pre| — the prediction shift induced by the edit.
        band_width:  Current PID quantile estimate q̂_α (always ≥ 0).
        verdict:     One of 'within' | 'exceeds_alpha=0.1' | 'exceeds_alpha=0.05'.
        band:        (lo, hi) prediction interval centred on y_post.
    """

    delta: float
    band_width: float
    verdict: str
    band: Tuple[float, float]

    def __post_init__(self) -> None:
        if self.verdict not in _ALLOWED_VERDICTS:
            raise ValueError(
                f"verdict must be one of {sorted(_ALLOWED_VERDICTS)}; got {self.verdict!r}"
            )


@dataclass(frozen=True)
class ValidationResult:
    """Aggregate validation outcome attached to ``CFResult.validation``.

    Each field is ``None`` when the corresponding validator was not run on
    this edit. Fields land here as their VAL tickets ship — currently
    VAL-001 (``conformal``), VAL-002 (``probe_ir``), VAL-003 (``ynn``),
    VAL-004 (``native_guide``).

    All non-VAL-001 fields are forward string references so this module
    does not side-import sibling validators; the runtime types come from
    ``app.services.validation.{probe_ir, ynn_plausibility, native_guide}``.
    """

    conformal: BandCheckResult | None = None
    probe_ir: "ProbeIRResult | None" = None  # noqa: F821 — forward ref
    ynn: "YnnResult | None" = None  # noqa: F821 — forward ref
    native_guide: "NativeGuideResult | None" = None  # noqa: F821 — forward ref


@dataclass(frozen=True)
class ConformalConfig:
    """PID gains and target coverage for the adaptive quantile.

    Defaults follow Angelopoulos et al. 2023 Table 1 (η = 0.5 proportional
    gain, modest integral term to damp drift). ``integral_window`` = 10
    matches the ticket pseudocode and is small enough that a single shock
    is fully absorbed within a few updates.
    """

    alpha: float = 0.1
    K_p: float = 0.5
    K_i: float = 0.1
    integral_window: int = 10

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1); got {self.alpha}")
        if self.integral_window < 1:
            raise ValueError(f"integral_window must be ≥ 1; got {self.integral_window}")


# ---------------------------------------------------------------------------
# Calibration cache helpers
# ---------------------------------------------------------------------------


def _default_cache_dir() -> Path:
    return Path(__file__).resolve().parent / "cache"


def _calibration_path(cache_dir: Path, dataset_name: str) -> Path:
    safe = "".join(ch for ch in dataset_name if ch.isalnum() or ch in ("-", "_"))
    if not safe:
        raise ConformalCalibrationError(
            f"dataset_name {dataset_name!r} produces an empty cache filename"
        )
    return cache_dir / f"conformal_calibration_{safe}.json"


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


CalibrationSet = Iterable[Tuple[np.ndarray, float]]


class ConformalPIDValidator:
    """Adaptive prediction-interval estimator for the per-edit fast path.

    The validator maintains a rolling estimate of the (1−α) residual
    quantile ``q̂_α`` via the PID update of Angelopoulos 2023 Eq. 4.
    ``band_check`` runs in O(1): it reads the latest ``q̂_α`` and compares it
    to the prediction shift caused by the edit.

    Calibration is performed once per dataset; the resulting initial
    quantile is cached as JSON so production runs do not pay the calibration
    cost. Subsequent ``update`` calls evolve the quantile online.
    """

    def __init__(
        self,
        forecaster: Forecaster,
        *,
        calibration_set: CalibrationSet | None = None,
        config: ConformalConfig | None = None,
        dataset_name: str | None = None,
        cache_dir: Path | str | None = None,
        load_cached: bool = True,
    ) -> None:
        self.forecaster = forecaster
        self.config = config or ConformalConfig()
        self._cache_dir = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
        self._dataset_name = dataset_name
        self.q_history: list[float] = []
        self._error_buffer: list[float] = []

        cache_path = (
            _calibration_path(self._cache_dir, dataset_name) if dataset_name else None
        )
        cache_hit = bool(load_cached and cache_path is not None and cache_path.exists())

        if cache_hit:
            self._load_cache(cache_path)  # type: ignore[arg-type]
        elif calibration_set is not None:
            self._calibrate(calibration_set)
            if cache_path is not None:
                self._save_cache(cache_path)
        else:
            raise ConformalCalibrationError(
                "ConformalPIDValidator requires either a calibration_set or a "
                "cached dataset_name; both were missing."
            )

    # -------- calibration ---------------------------------------------------

    def _calibrate(self, calibration_set: CalibrationSet) -> None:
        residuals = [
            float(abs(y_true - float(self.forecaster.predict(x))))
            for x, y_true in calibration_set
        ]
        if not residuals:
            raise ConformalCalibrationError("calibration_set is empty")
        q0 = float(np.quantile(residuals, 1.0 - self.config.alpha))
        self.q_history.append(q0)

    # -------- PID update ----------------------------------------------------

    def update(self, y_true: float, y_pred: float) -> None:
        """Apply Angelopoulos 2023 Eq. 4 PID update to ``q̂_α``.

        Eq. 4 drives the *miscoverage rate* to the target α. With

            err_t   = 1{|y_t − ŷ_t| > q_t} − α

        the update is

            q_{t+1} = q_t + K_p · err_t + K_i · Σ_{i=t−W+1}^{t} err_i

        where ``W = config.integral_window`` bounds the integral term
        (standard anti-windup). At stationarity ``E[err_t] = 0``, so the
        empirical miscoverage rate converges to α — giving 1−α marginal
        coverage. The result is clipped at zero; a negative quantile would
        imply a degenerate (empty) interval.

        Note: the VAL-001 ticket's pseudocode shows a residual-gap form
        ``err = |y − ŷ| − q``, which is a different controller and does not
        target 1−α coverage. The Acceptance Criteria bind correctness to
        Angelopoulos 2023 Eq. 4 and to a 1−α ± 0.02 held-out coverage test;
        this implementation follows the paper.
        """
        if not self.q_history:
            raise ConformalCalibrationError(
                "update() called before calibration; q_history is empty."
            )
        q_now = self.q_history[-1]
        miscovered = float(abs(float(y_true) - float(y_pred)) > q_now)
        err = miscovered - self.config.alpha
        self._error_buffer.append(err)
        if len(self._error_buffer) > self.config.integral_window:
            del self._error_buffer[: len(self._error_buffer) - self.config.integral_window]
        integral = sum(self._error_buffer)
        q_next = q_now + self.config.K_p * err + self.config.K_i * integral
        self.q_history.append(max(q_next, 0.0))

    # -------- per-edit band check (O(1)) -----------------------------------

    def band_check(self, y_pre: float, y_post: float) -> BandCheckResult:
        """Compare the prediction shift |y_post − y_pre| to the current band.

        This is the hot path: pure arithmetic on the latest ``q̂_α``. The
        verdict ladder uses the standard 2× inflation to map an α=0.1
        marginal interval onto an α=0.05 coverage bound under symmetric
        residuals.
        """
        if not self.q_history:
            raise ConformalCalibrationError(
                "band_check() called before calibration; q_history is empty."
            )
        q = self.q_history[-1]
        delta = float(abs(y_post - y_pre))
        if delta < q:
            verdict = VERDICT_WITHIN
        elif delta < 2.0 * q:
            verdict = VERDICT_EXCEEDS_10
        else:
            verdict = VERDICT_EXCEEDS_05
        return BandCheckResult(
            delta=delta,
            band_width=q,
            verdict=verdict,
            band=(float(y_post) - q, float(y_post) + q),
        )

    # -------- cache I/O -----------------------------------------------------

    @property
    def calibration_cache_path(self) -> Path | None:
        if self._dataset_name is None:
            return None
        return _calibration_path(self._cache_dir, self._dataset_name)

    def _save_cache(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "alpha": self.config.alpha,
            "K_p": self.config.K_p,
            "K_i": self.config.K_i,
            "integral_window": self.config.integral_window,
            "q_history": list(self.q_history),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_cache(self, path: Path) -> None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConformalCalibrationError(
                f"failed to read calibration cache at {path}: {exc}"
            ) from exc
        for field_name in ("alpha", "K_p", "K_i", "integral_window"):
            cached = raw.get(field_name)
            current = getattr(self.config, field_name)
            if cached != current:
                raise ConformalCalibrationError(
                    f"cached {field_name}={cached} does not match configured {field_name}={current}"
                )
        history = raw.get("q_history")
        if not isinstance(history, list) or not history:
            raise ConformalCalibrationError(
                f"calibration cache at {path} has no q_history entries"
            )
        self.q_history = [float(v) for v in history]
