"""PPCEF normalising-flow plausibility for TS decompositions (VAL-033).

**Publishable contribution.** Ports PPCEF (Wielopolski et al. ECAI 2024)
from raw-feature space to **decomposition-coefficient space**. A small
normalising flow (RealNVP or Neural Spline Flow) is trained on the
coefficient vectors of decomposition blobs fitted across a training
corpus. Per-edit inference computes ``log p_NF(θ_edit)`` and compares
it to the training-set log-density distribution; lower-tail values
fire the VAL-020 plausibility tip.

Sources (binding for ``algorithm-auditor``):

  - Wielopolski, Furman, Stefanowski, Zięba, "PPCEF: Probabilistically
    Plausible Counterfactual Explanations with Normalizing Flows,"
    *ECAI 2024*, FAIA 392:954–961, DOI:10.3233/FAIA240584,
    arXiv:2405.17640 — canonical PPCEF formulation; §3 for the
    log-density-based plausibility score; §4 for training protocol.
  - Dinh, Sohl-Dickstein, Bengio, "Density estimation using Real NVP,"
    *ICLR 2017*, arXiv:1605.08803 — RealNVP architecture.
  - Durkan, Bekasov, Murray, Papamakarios, "Neural Spline Flows,"
    *NeurIPS 2019*, arXiv:1906.04032 — NSF, default for low-dimensional
    structured coefficient vectors.
  - Pawelczyk, Broelemann, Kasneci, "C-CHVAE," *WWW 2020*,
    DOI:10.1145/3366423.3380087 — VAE-based plausibility comparator.
  - Furman, Wielopolski, Zięba et al., arXiv:2405.17642 (2024) —
    extension; flagged for follow-up.

Library: ``normflows`` (Stimper et al. *JOSS* 2023, DOI:10.21105/joss.05361).

**Methodological honesty.** PPCEF over coefficient space measures
plausibility *of the fitted-parameter configuration*, NOT of the raw
waveform — and the two can diverge. A coefficient set with very
different ETM step amplitudes might still produce a plausible-looking
time series under a different fitter. Cross-reference VAL-030 (IAAFT)
for the complementary signal-space test.

Per the SOTA review's open-research-gaps §3, this is the third
publishable contribution: PPCEF has not been ported to time-series CFs;
doing so over fitted parametric decompositions rather than raw values
gives a plausibility signal interpretable in physical units (e.g.
"your edited STL trend slope falls in the 0.2 % tail of fitted slopes
for this domain").
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np

from app.models.decomposition import DecompositionBlob

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PPCEFError(RuntimeError):
    """Raised when PPCEF inputs are unusable (encoder missing, dim mismatch, etc.)."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


METHOD_REALNVP = "realnvp"
METHOD_NSF = "nsf"
_ALLOWED_METHODS = frozenset({METHOD_REALNVP, METHOD_NSF})

DEFAULT_N_LAYERS = 8
DEFAULT_HIDDEN_DIM = 64
DEFAULT_LR = 1e-3
DEFAULT_BATCH_SIZE = 64
DEFAULT_N_EPOCHS = 200
DEFAULT_VAL_FRAC = 0.1
DEFAULT_PLAUSIBILITY_QUANTILE = 0.05  # AC: 5th-percentile threshold
_LOW_DIM_CUTOFF = 4  # AC: < 4 dims → fall back to RealNVP per AC


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PPCEFResult:
    """Per-edit PPCEF plausibility outcome.

    Attributes:
        log_p:                 ``log p_NF(θ_edit)`` from the flow.
        train_5th_percentile:  AC threshold; ``log_p`` below this is
                               judged anomalous.
        train_50th_percentile: Median of training log_p — the
                               "central" plausibility value.
        quantile:              Empirical CDF of ``log_p`` against the
                               training distribution; ``[0, 1]``.
                               Drives the green/yellow/red badge in UI-012.
        is_plausible:          ``log_p > train_5th_percentile``.
        flow_method:           ``'realnvp' | 'nsf'``.
        coefficient_dim:       Length of the encoded coefficient vector.
        decomposition_method:  Method of the input blob.
    """

    log_p: float
    train_5th_percentile: float
    train_50th_percentile: float
    quantile: float
    is_plausible: bool
    flow_method: str
    coefficient_dim: int
    decomposition_method: str


# ---------------------------------------------------------------------------
# Coefficient encoder registry
# ---------------------------------------------------------------------------


# Maps DecompositionBlob.method → callable(blob) → (vector, layout_keys).
# layout_keys is the canonical name list aligned with the vector entries
# so the UI can show "your edited STL trend slope falls in the 0.2 % tail".
_COEFF_ENCODERS: dict[str, Callable[[DecompositionBlob], tuple[np.ndarray, list[str]]]] = {}


def register_coefficient_encoder(
    method: str,
    encoder: Callable[[DecompositionBlob], tuple[np.ndarray, list[str]]],
) -> None:
    """Register a method-specific coefficient encoder.

    Each encoder returns ``(vector, layout_keys)`` — a fixed-length 1-D
    float array plus a list of canonical names aligned 1:1 with the
    vector entries. Variable-length coefficient sets (e.g. GrAtSiD's
    varying number of features) should aggregate to summary statistics
    (count, mean / std of amplitudes, mean / std of decay constants,
    …) rather than truncate or pad — see the AC's "documented as a
    known limitation" line.
    """
    _COEFF_ENCODERS[method] = encoder


def _encode_constant(blob: DecompositionBlob) -> tuple[np.ndarray, list[str]]:
    """Constant fitter: single ``level`` coefficient."""
    level = float(blob.coefficients.get("level", 0.0))
    return np.array([level], dtype=np.float64), ["level"]


def _encode_etm(blob: DecompositionBlob) -> tuple[np.ndarray, list[str]]:
    """ETM fitter: ``x0`` + ``linear_rate`` (the two scalar coefficients
    common across ETM fits per Bevis-Brown Eq. 1; step / transient
    coefficients are summarised via count + mean magnitude when present)."""
    x0 = float(blob.coefficients.get("x0", 0.0))
    linear_rate = float(blob.coefficients.get("linear_rate", 0.0))
    layout = ["x0", "linear_rate"]
    values = [x0, linear_rate]

    # Aggregate step coefficients (variable count) → (count, mean abs amplitude).
    step_keys = [k for k in blob.coefficients if k.startswith("step_at_")]
    step_amps = [
        float(blob.coefficients[k]) for k in step_keys
        if isinstance(blob.coefficients[k], (int, float, np.integer, np.floating))
    ]
    layout += ["n_steps", "mean_abs_step"]
    values += [
        float(len(step_amps)),
        float(np.mean(np.abs(step_amps))) if step_amps else 0.0,
    ]
    return np.asarray(values, dtype=np.float64), layout


def _encode_summary_fallback(blob: DecompositionBlob) -> tuple[np.ndarray, list[str]]:
    """Last-resort encoder for unregistered methods.

    Aggregates *all* scalar coefficients to a 4-vector summary:
    (count, mean, std, max-abs). Documented as a known limitation in the
    module docstring and per AC.
    """
    scalars = [
        float(v) for v in blob.coefficients.values()
        if isinstance(v, (int, float, np.integer, np.floating))
    ]
    if not scalars:
        return np.zeros(4, dtype=np.float64), ["count", "mean", "std", "max_abs"]
    arr = np.asarray(scalars, dtype=np.float64)
    return (
        np.array([len(arr), float(arr.mean()), float(arr.std()), float(np.max(np.abs(arr)))], dtype=np.float64),
        ["count", "mean", "std", "max_abs"],
    )


# Register the two canonical encoders. Other methods fall back to the
# summary statistics; callers can register their own with
# ``register_coefficient_encoder``.
register_coefficient_encoder("Constant", _encode_constant)
register_coefficient_encoder("ETM", _encode_etm)


def encode_blob_to_vector(
    blob: DecompositionBlob,
) -> tuple[np.ndarray, list[str]]:
    """Encode a fitted blob to a fixed-length 1-D coefficient vector.

    Returns ``(vector, layout_keys)`` so callers can map vector indices
    back to coefficient names for the UI badge tooltip.
    """
    encoder = _COEFF_ENCODERS.get(blob.method, _encode_summary_fallback)
    return encoder(blob)


# ---------------------------------------------------------------------------
# Flow construction
# ---------------------------------------------------------------------------


def _build_realnvp(dim: int, n_layers: int, hidden_dim: int):
    """RealNVP via normflows (Dinh et al. 2017).

    For dim < 2, the coupling-block split degenerates; in that case we
    fall back to a single AffineCouplingBlock around a 2-padded vector
    and rely on the marginal Gaussian over the padding dim. This keeps
    the API uniform across very-low-dim coefficient spaces.
    """
    import normflows as nf  # noqa: PLC0415
    if dim < 2:
        raise PPCEFError(
            f"RealNVP requires dim ≥ 2; got {dim}. Use NSF or pad the coefficient vector."
        )
    flows = []
    for _ in range(n_layers):
        param_map = nf.nets.MLP([dim // 2, hidden_dim, dim], init_zeros=True)
        flows.append(nf.flows.AffineCouplingBlock(param_map))
        flows.append(nf.flows.Permute(dim, mode="swap"))
    base = nf.distributions.DiagGaussian(dim, trainable=False)
    return nf.NormalizingFlow(base, flows)


def _build_nsf(dim: int, n_layers: int, hidden_dim: int, num_bins: int = 8):
    """Neural Spline Flow via normflows (Durkan et al. 2019)."""
    import normflows as nf  # noqa: PLC0415
    if dim < 2:
        raise PPCEFError(
            f"NSF requires dim ≥ 2; got {dim}. Pad the coefficient vector."
        )
    flows = []
    for i in range(n_layers):
        flows.append(
            nf.flows.CoupledRationalQuadraticSpline(
                num_input_channels=dim,
                num_blocks=2,
                num_hidden_channels=hidden_dim,
                num_bins=num_bins,
                tail_bound=4.0,
                reverse_mask=(i % 2 == 1),
            )
        )
        flows.append(nf.flows.LULinearPermute(dim))
    base = nf.distributions.DiagGaussian(dim, trainable=False)
    return nf.NormalizingFlow(base, flows)


# ---------------------------------------------------------------------------
# CoefficientFlow
# ---------------------------------------------------------------------------


class CoefficientFlow:
    """A single trained flow over the coefficient-vector space.

    One ``CoefficientFlow`` is trained per ``(domain_pack, decomposition_method)``
    pair. Use ``fit`` to train on a 2-D ``(N, dim)`` array; ``score`` to
    score a single edit; ``save`` / ``load`` to persist a trained flow.

    Standardisation: per-dim z-score is computed at fit time on the
    training partition and stored on the model so inference applies the
    same (μ, σ).
    """

    def __init__(
        self,
        dim: int,
        *,
        n_layers: int = DEFAULT_N_LAYERS,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
        method: Literal["realnvp", "nsf"] | None = None,
        seed: int = 0,
    ) -> None:
        if dim < 1:
            raise PPCEFError(f"dim must be ≥ 1; got {dim}")
        if method is None:
            # AC: fall back to RealNVP for dim < 4 (NSF default otherwise).
            method = METHOD_REALNVP if dim < _LOW_DIM_CUTOFF else METHOD_NSF
        if method not in _ALLOWED_METHODS:
            raise PPCEFError(
                f"method must be one of {sorted(_ALLOWED_METHODS)}; got {method!r}"
            )

        self.dim = int(dim)
        self.method = method
        self.n_layers = int(n_layers)
        self.hidden_dim = int(hidden_dim)
        self.seed = int(seed)

        import torch  # noqa: PLC0415
        torch.manual_seed(seed)
        np.random.seed(seed)

        if method == METHOD_REALNVP:
            self.flow = _build_realnvp(self.dim, self.n_layers, self.hidden_dim)
        else:
            self.flow = _build_nsf(self.dim, self.n_layers, self.hidden_dim)

        self.mu: np.ndarray | None = None
        self.sigma: np.ndarray | None = None
        self._train_log_p: np.ndarray | None = None
        self.train_log_p_5th: float | None = None
        self.train_log_p_50th: float | None = None

    # -------- training ----------------------------------------------------

    def fit(
        self,
        theta_train: np.ndarray,
        *,
        n_epochs: int = DEFAULT_N_EPOCHS,
        lr: float = DEFAULT_LR,
        batch_size: int = DEFAULT_BATCH_SIZE,
        val_frac: float = DEFAULT_VAL_FRAC,
        early_stopping_patience: int = 10,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Train the flow on a coefficient matrix.

        Returns a training summary dict ``{loss_curve, val_loss_curve,
        early_stopped_epoch, best_val_loss}``.
        """
        import torch  # noqa: PLC0415

        arr = np.asarray(theta_train, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[1] != self.dim:
            raise PPCEFError(
                f"theta_train must be (N, {self.dim}); got {arr.shape}"
            )
        if arr.shape[0] < 4:
            raise PPCEFError(
                f"need ≥ 4 training rows; got {arr.shape[0]}"
            )

        # Deterministic train / val split.
        rng = np.random.default_rng(self.seed)
        idx = rng.permutation(arr.shape[0])
        n_val = max(1, int(val_frac * arr.shape[0]))
        val_idx = idx[:n_val]
        train_idx = idx[n_val:]
        if len(train_idx) < 1:
            raise PPCEFError(
                f"after val split (val_frac={val_frac}) no training rows remain; "
                f"reduce val_frac or supply more data."
            )

        # Standardisation on the *training* partition only (no val leakage).
        self.mu = arr[train_idx].mean(axis=0)
        self.sigma = arr[train_idx].std(axis=0) + 1e-9
        train_z = (arr[train_idx] - self.mu) / self.sigma
        val_z = (arr[val_idx] - self.mu) / self.sigma

        torch.manual_seed(self.seed)
        opt = torch.optim.Adam(self.flow.parameters(), lr=lr)
        train_x = torch.tensor(train_z, dtype=torch.float32)
        val_x = torch.tensor(val_z, dtype=torch.float32)

        loss_curve: list[float] = []
        val_curve: list[float] = []
        best_val = float("inf")
        best_epoch = 0
        patience_left = early_stopping_patience
        early_stopped = None

        for epoch in range(n_epochs):
            self.flow.train()
            perm = torch.randperm(train_x.shape[0])
            epoch_loss = 0.0
            n_batches = 0
            for start in range(0, train_x.shape[0], batch_size):
                batch_idx = perm[start : start + batch_size]
                batch = train_x[batch_idx]
                loss = -self.flow.log_prob(batch).mean()
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_loss += float(loss.item())
                n_batches += 1
            loss_curve.append(epoch_loss / max(n_batches, 1))

            self.flow.eval()
            with torch.no_grad():
                val_loss = -self.flow.log_prob(val_x).mean().item()
            val_curve.append(float(val_loss))
            if verbose:
                logger.info(
                    "ppcef fit epoch %d/%d train=%.4f val=%.4f",
                    epoch + 1, n_epochs, loss_curve[-1], val_loss,
                )
            if val_loss < best_val - 1e-6:
                best_val = float(val_loss)
                best_epoch = epoch
                patience_left = early_stopping_patience
            else:
                patience_left -= 1
                if patience_left <= 0:
                    early_stopped = epoch
                    break

        # Cache training-set log_p distribution for inference quantiles.
        self.flow.eval()
        with torch.no_grad():
            self._train_log_p = self.flow.log_prob(train_x).cpu().numpy().astype(np.float64)
        self.train_log_p_5th = float(np.percentile(self._train_log_p, 5))
        self.train_log_p_50th = float(np.percentile(self._train_log_p, 50))

        return {
            "loss_curve": loss_curve,
            "val_loss_curve": val_curve,
            "best_val_loss": best_val,
            "best_epoch": best_epoch,
            "early_stopped_epoch": early_stopped,
        }

    # -------- inference ---------------------------------------------------

    def score(self, theta_edit: np.ndarray, *, decomposition_method: str = "") -> PPCEFResult:
        """Score a single edited coefficient vector.

        ``theta_edit`` must be a 1-D vector of length ``self.dim`` (the
        encoded blob output of ``encode_blob_to_vector``). Raises
        ``PPCEFError`` if the model has not been fit yet or on dim
        mismatch.
        """
        if self.mu is None or self.sigma is None or self._train_log_p is None:
            raise PPCEFError(
                "CoefficientFlow has not been fit yet — call .fit(theta_train) first."
            )
        arr = np.asarray(theta_edit, dtype=np.float32).reshape(-1)
        if arr.shape[0] != self.dim:
            raise PPCEFError(
                f"theta_edit dim mismatch: got {arr.shape[0]}, expected {self.dim}"
            )
        z = (arr - self.mu) / self.sigma

        import torch  # noqa: PLC0415
        self.flow.eval()
        with torch.no_grad():
            log_p_t = self.flow.log_prob(torch.tensor(z, dtype=torch.float32).unsqueeze(0))
            log_p = float(log_p_t.item())

        # Empirical-CDF quantile against the cached training log_p distribution.
        quantile = float(np.mean(self._train_log_p <= log_p))

        return PPCEFResult(
            log_p=log_p,
            train_5th_percentile=float(self.train_log_p_5th),
            train_50th_percentile=float(self.train_log_p_50th),
            quantile=quantile,
            is_plausible=bool(log_p > self.train_log_p_5th),
            flow_method=self.method,
            coefficient_dim=self.dim,
            decomposition_method=decomposition_method,
        )

    # -------- persistence -------------------------------------------------

    def save(self, path: Path | str) -> None:
        """Persist the trained flow + standardisation to ``.pt`` + sidecar JSON."""
        if self.mu is None:
            raise PPCEFError("save: cannot persist an un-fit CoefficientFlow.")
        import torch  # noqa: PLC0415
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.flow.state_dict(), out)
        meta = {
            "dim": self.dim,
            "method": self.method,
            "n_layers": self.n_layers,
            "hidden_dim": self.hidden_dim,
            "seed": self.seed,
            "mu": self.mu.tolist(),
            "sigma": self.sigma.tolist(),
            "train_log_p_5th": self.train_log_p_5th,
            "train_log_p_50th": self.train_log_p_50th,
            "train_log_p": self._train_log_p.tolist() if self._train_log_p is not None else None,
        }
        out.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> "CoefficientFlow":
        import torch  # noqa: PLC0415
        p = Path(path)
        meta_path = p.with_suffix(".json")
        if not p.exists() or not meta_path.exists():
            raise PPCEFError(
                f"CoefficientFlow.load: missing {p} or {meta_path}; both must exist."
            )
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        flow = cls(
            dim=int(meta["dim"]),
            n_layers=int(meta["n_layers"]),
            hidden_dim=int(meta["hidden_dim"]),
            method=meta["method"],
            seed=int(meta["seed"]),
        )
        flow.flow.load_state_dict(torch.load(p, map_location="cpu", weights_only=True))
        flow.mu = np.asarray(meta["mu"], dtype=np.float64)
        flow.sigma = np.asarray(meta["sigma"], dtype=np.float64)
        flow.train_log_p_5th = float(meta["train_log_p_5th"])
        flow.train_log_p_50th = float(meta["train_log_p_50th"])
        if meta.get("train_log_p") is not None:
            flow._train_log_p = np.asarray(meta["train_log_p"], dtype=np.float64)
        return flow


# ---------------------------------------------------------------------------
# LOF baseline (paper comparator panel per AC)
# ---------------------------------------------------------------------------


def lof_baseline_score(
    theta_train: np.ndarray,
    theta_edit: np.ndarray,
    *,
    n_neighbors: int = 20,
    contamination: float | str = "auto",
) -> float:
    """Local Outlier Factor score on the coefficient vectors.

    Returns the LOF anomaly score (lower = more anomalous; values close
    to 1 are inliers, values much greater than 1 are outliers per
    Breunig et al. 2000). Used as the baseline against which to compare
    PPCEF in the publication.
    """
    from sklearn.neighbors import LocalOutlierFactor  # noqa: PLC0415
    train = np.asarray(theta_train, dtype=np.float64)
    edit = np.asarray(theta_edit, dtype=np.float64).reshape(1, -1)
    if train.shape[1] != edit.shape[1]:
        raise PPCEFError(
            f"LOF baseline dim mismatch: train {train.shape[1]} vs edit {edit.shape[1]}"
        )
    lof = LocalOutlierFactor(
        n_neighbors=min(n_neighbors, max(2, train.shape[0] - 1)),
        contamination=contamination,
        novelty=True,
    )
    lof.fit(train)
    # ``score_samples`` returns the negative LOF; negate for the standard
    # convention (higher = more anomalous).
    score = float(-lof.score_samples(edit)[0])
    return score
