# VAL-033 — PPCEF normalising-flow plausibility for TS decompositions

**Status:** [ ] Done — **PUBLISHABLE CONTRIBUTION**
**Depends on:** SEG-019 (decomposition blob), training data corpus with fitted blobs, OP-050 (CF coordinator)

---

## Goal

**Port PPCEF (Wielopolski et al. ECAI 2024) from raw-feature space to time-series decomposition-coefficient space.** Train a small normalising flow (RealNVP or Neural Spline Flow) on the **coefficient vectors** of decomposition blobs fitted to the training corpus. Surface the log-density `log p_NF(θ_edit)` as a per-edit plausibility score — *"how plausible is this configuration of decomposition parameters under the natural distribution of fitted models in the training set?"*

A single forward pass through the flow is ≤ 50 ms, so this can run on the **fast path** for inference, but requires offline training (hence "slow-path" tier).

**Why publishable:** Per the [[HypotheX-TS - Statistical Validation SOTA]] review §A.7, PPCEF has not been ported to time-series CFs; doing so over **fitted parametric decompositions rather than raw values** is novel and gives a plausibility signal that is interpretable in physical units (e.g. "your edited STL trend slope falls in the 0.2 % tail of fitted slopes for this domain"). **This is contribution #3 from §"Open research gaps"** of the SOTA review.

**How it fits:** Offline training of one flow per `(domain_pack, decomposition_method)` combination. Inference per edit: encode edited blob's coefficients to a fixed-length vector, query flow, compare `log p_NF` to the training-set distribution's 5th percentile. Result feeds into the plausibility badge (UI-012) and triggers VAL-020 tips when ` log p_NF` is in the lower tail.

---

## Paper references (for `algorithm-auditor`)

- Wielopolski, Furman, Stefanowski, Zięba, **"PPCEF: Probabilistically Plausible Counterfactual Explanations with Normalizing Flows,"** *ECAI 2024*, FAIA 392:954–961, DOI 10.3233/FAIA240584, arXiv 2405.17640 (canonical PPCEF formulation; algorithm-auditor reads §3 for the log-density-based plausibility score and §4 for training protocol).
- Dinh, Sohl-Dickstein, Bengio, **"Density estimation using Real NVP,"** *ICLR 2017*, arXiv 1605.08803 (RealNVP architecture).
- Durkan, Bekasov, Murray, Papamakarios, **"Neural Spline Flows,"** *NeurIPS 2019* (NSF — preferred for low-dimensional structured coefficient vectors), arXiv 1906.04032.
- Pawelczyk, Broelemann, Kasneci, **"Learning Model-Agnostic Counterfactual Explanations for Tabular Data" (C-CHVAE),** *WWW 2020*, DOI 10.1145/3366423.3380087 (related VAE-based plausibility — comparator).
- Furman, Wielopolski, Zięba et al., **"Unifying Perspectives: Plausible CF Explanations on Global, Group-wise, and Local Levels,"** arXiv 2405.17642 (2024) (extension; flag for follow-up work).
- Library: `nflows` (Durkan et al.) or `normflows` (Stimper et al. JOSS 2023 DOI 10.21105/joss.05361).

---

## Pseudocode

```python
# backend/app/services/validation/ppcef.py
import torch
import nflows
from dataclasses import dataclass

@dataclass(frozen=True)
class PPCEFResult:
    log_p: float                    # log p_NF(θ_edit)
    train_5th_percentile: float     # threshold for "anomalous"
    train_50th_percentile: float    # median
    quantile: float                 # quantile of log_p in training distribution
    is_plausible: bool
    flow_method: str

class CoefficientFlow:
    def __init__(self, dim: int, n_layers: int = 8, hidden_dim: int = 64,
                 method: Literal['realnvp', 'nsf'] = 'nsf'):
        from nflows.flows.base import Flow
        from nflows.transforms.compose import CompositeTransform
        self.flow = self._build(dim, n_layers, hidden_dim, method)
        self.method = method
        self.train_log_p_5th = None      # populated after training

    def fit(self, theta_train: np.ndarray, n_epochs: int = 200, lr: float = 1e-3,
            batch_size: int = 64, val_frac: float = 0.1, seed: int = 0):
        """Train on (N, dim) coefficient matrix from training-corpus fitted blobs."""
        torch.manual_seed(seed)
        N = theta_train.shape[0]
        n_val = int(val_frac * N)
        idx = np.random.default_rng(seed).permutation(N)
        train_idx, val_idx = idx[n_val:], idx[:n_val]
        # Standardise to zero-mean unit-var per dim (store μ, σ)
        self.mu, self.sigma = theta_train[train_idx].mean(0), theta_train[train_idx].std(0)
        train_z = (theta_train[train_idx] - self.mu) / (self.sigma + 1e-9)
        val_z   = (theta_train[val_idx]   - self.mu) / (self.sigma + 1e-9)
        opt = torch.optim.Adam(self.flow.parameters(), lr=lr)
        for epoch in range(n_epochs):
            self.flow.train()
            for batch in batched(train_z, batch_size):
                loss = -self.flow.log_prob(torch.tensor(batch).float()).mean()
                opt.zero_grad(); loss.backward(); opt.step()
            # Early stopping on val
            self.flow.eval()
            val_loss = -self.flow.log_prob(torch.tensor(val_z).float()).mean().item()
            if early_stop(val_loss): break
        # Compute training-set log_p distribution for percentile thresholds
        with torch.no_grad():
            train_log_p = self.flow.log_prob(torch.tensor(train_z).float()).cpu().numpy()
        self.train_log_p_5th  = float(np.percentile(train_log_p,  5))
        self.train_log_p_50th = float(np.percentile(train_log_p, 50))

    def score(self, theta_edit: np.ndarray) -> PPCEFResult:
        z = (theta_edit - self.mu) / (self.sigma + 1e-9)
        with torch.no_grad():
            log_p = float(self.flow.log_prob(torch.tensor(z).float()).item())
        # Quantile via empirical CDF of training log_p (computed once, cached)
        quantile = float(np.mean(self._train_log_p_full <= log_p))
        return PPCEFResult(
            log_p=log_p,
            train_5th_percentile=self.train_log_p_5th,
            train_50th_percentile=self.train_log_p_50th,
            quantile=quantile,
            is_plausible=log_p > self.train_log_p_5th,
            flow_method=self.method,
        )

def encode_blob_to_vector(blob) -> np.ndarray:
    """Flatten DecompositionBlob.coefficients to a fixed-length vector.
    Vector layout is method-specific and registered per method; missing
    coefficients are zero-padded with a mask channel."""
    return _COEFF_ENCODERS[blob.method](blob)
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/ppcef.py` with `CoefficientFlow`, `PPCEFResult`, `encode_blob_to_vector`
- [ ] **One flow per `(domain_pack, decomposition_method)` combination** trained offline; trained models cached as `.pt` files in `models/ppcef/{pack}_{method}.pt`
- [ ] Default flow architecture = **Neural Spline Flow** (Durkan et al. NeurIPS 2019), 8 coupling layers, 64 hidden units; RealNVP available as fallback for very-low-dim coefficient spaces (< 4 dims)
- [ ] **Coefficient encoder per decomposition method:** registered in `_COEFF_ENCODERS` dict; each encoder produces a deterministic fixed-length vector with documented layout. Variable-length coefficient sets (e.g. GrAtSiD's varying number of features) are handled by aggregating to summary statistics (count, amplitudes-mean, amplitudes-std, τ-mean, τ-std) — **documented as a known limitation**
- [ ] Per-dim standardisation (μ, σ) stored on the trained model; same standardisation applied at inference
- [ ] Training script `scripts/train_ppcef.py` with deterministic seed, early stopping on validation log-likelihood, output to `models/ppcef/`
- [ ] Inference latency < 50 ms on reference hardware for a single edit (asserted by CI benchmark)
- [ ] **Plausibility threshold:** `is_plausible := log_p > 5th-percentile of training log_p`. Quantile (empirical CDF) returned for the UI-012 plausibility badge to render a finer green/yellow/red signal
- [ ] **Methodological honesty:** docstring documents that PPCEF over coefficient space measures plausibility *of the fitted-parameter configuration*, NOT of the raw waveform — and that the two can diverge (e.g. a coefficient set with very different ETM step amplitudes might still produce a plausible-looking time series). Cross-references VAL-030 (IAAFT) as the complementary signal-space test
- [ ] Result surfaced via UI-012 plausibility badge; VAL-020 tip fires if `quantile < 0.05`
- [ ] **Optional comparator panel:** for the publishable paper, output also `LOF_score` from a pre-fit `LocalOutlierFactor` on the same coefficient vectors as a baseline against which to compare PPCEF
- [ ] `nflows` (or `normflows`) and `torch` (>= 2.0) added to `backend/requirements.txt`
- [ ] Tests cover: deterministic training under seed (loss curve hash matches); inference reproducibility; round-trip encode-decode invariant; latency < 50 ms; quantile computation correct on hand-checked toy distribution; raises informative error on coefficient-vector dim mismatch
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "VAL-033: PPCEF normalising-flow plausibility over decomposition coefficients (publishable port)"` ← hook auto-moves this file to `done/` on commit
