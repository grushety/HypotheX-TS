# HypotheX-TS — Research Algorithms Skill

Load this skill before implementing, modifying, or reviewing any domain algorithm.
Load this skill when running the `algorithm-auditor` agent.

Each entry documents: purpose, authoritative source, key equations or pseudocode, correct behaviour, what to check during review, and SotA status.

**SotA status is time-sensitive.** The `algorithm-auditor` agent must perform a web search for each algorithm before declaring SotA status current.

---

## 1. Prototype-Based Nearest-Centroid Classifier

**Purpose:** Assigns segment labels by comparing window embeddings to per-class prototype vectors. Enables few-shot adaptation from user corrections.

**Source:**
- Snell et al., *Prototypical Networks for Few-shot Learning*, NeurIPS 2017 — core prototypical distance idea
- TAPNet: He et al., *Temporal Attentive Prototype Network*, arXiv 1909.11485 — few-shot time series adaptation
- Internal feasibility report: *Formalizing Interactive Few-Shot Semantic Segmentation for Geoscientific Time Series*, 2026

**Key equations:**
```
Embedding:      z_t = encoder(X_{t-w:t+w})         z_t ∈ ℝ^d
Prototype:      μ_y = mean({z_t : t ∈ support_y})
Label score:    p(y|t) ∝ exp(−‖z_t − μ_y‖² / τ)
Prediction:     ŷ_t = argmin_y ‖z_t − μ_y‖²
```

**Correct behaviour:**
- Prototypes are updated from user-labeled support segments after every N operations
- Encoder weights are **mostly frozen** during adaptation — only the classification head or prototype vectors update
- Softmax temperature `τ` controls confidence sharpness; default should be documented in domain config

**What to check:**
- Is the encoder frozen correctly? Any full fine-tuning is a bug unless explicitly ticketed
- Is the prototype mean computed over embeddings (not raw signal)?
- Is the temperature parameter exposed and documented?

**SotA status (last checked 2026-04):**
- Prototypical networks remain competitive for few-shot classification
- Check: ProtoNet variants (ICLR 2024), CASC, any 2025 few-shot TS segmentation work
- Key question for auditor: is there a few-shot TS segmentation method that achieves better label efficiency with fewer user corrections? Search ECML/ICML/NeurIPS 2024-2025.

---

## 2. HSMM Smoother

**Purpose:** Prevents rapid label switching in the prototype classifier output. Enforces minimum segment duration as a temporal prior.

**Source:**
- Murphy, *Hidden Semi-Markov Models*, tech report 2002 — foundational HSMM formulation
- Prototype + HSMM architecture: TU Darmstadt internal reference (cited in feasibility report 2026)
- Yu, *The infinite hidden Markov model*, Machine Learning 2010 — duration modelling

**Key equations:**
```
State duration prior:  p(d | y) = NegBin(r_y, p_y)   or Poisson(λ_y)
Forward variable:      α_t(y, d) = p(X_{t-d+1:t}, s_t = y, dur_t = d)
Viterbi path:          ŝ = argmax_s p(s | X, θ)
```

**Correct behaviour:**
- Duration prior is per-label (`λ_y` for each `y ∈ {event, trend, anomaly, other}`) — not a single global prior
- Minimum duration from `mvp-domain-config.json` feeds into the duration prior as a hard floor
- Smoother runs on top of prototype classifier output — it does not replace the classifier

**What to check:**
- Is the duration prior per-label or global? Global is wrong.
- Is `min_duration` from domain config correctly wired into the prior?
- Is the smoother stateless per inference call (no leakage between sessions)?

**SotA status (last checked 2026-04):**
- HSMM remains appropriate for structured segmentation with known minimum durations
- Check: transformer-based temporal segmentation (e.g. SegFormer-1D variants, PETS), Mamba-based segmenters for TS
- Key question for auditor: for the few-shot interactive setting specifically (not large-scale training), is HSMM still the right smoother? Alternatives: CRF, learnable duration model.

---

## 3. Segment Statistics

**Purpose:** Computes interpretable statistics per segment used by chunk scoring to assign labels.

**Source:**
- Slope / trend detection: standard linear regression (OLS) on smoothed signal — no external paper needed; document the smoothing kernel used
- Sign consistency: internal definition — fraction of adjacent-step sign agreements on smoothed signal
- Periodicity: Lomb-Scargle or FFT-based dominant frequency energy ratio — **verify which is implemented**
- Context contrast: local mean difference — internal definition
- WARI metric for evaluation: Arbelaez et al. adapted for TS — see evaluation section

**Key equations:**
```
Smoothed signal:    x̃ = conv(X, kernel, mode="same")     # kernel documented in stats.py
Slope:              β = OLS slope of x̃ over [b_k, e_k]
Sign consistency:   SC = (1/L) Σ 1[sign(x̃_{t+1} − x̃_t) = sign(β)]
Variance:           V = Var(X[b_k:e_k])
Residual:           R = mean|X[b_k:e_k] − linear_fit|
Peak:               P = max|X[b_k:e_k]|
Periodicity:        F = dominant_frequency_energy / total_energy    # verify: FFT or Lomb-Scargle
Context contrast:   CC = |mean(X[b_k:e_k]) − mean(X[neighbours])|
```

**What to check:**
- Slope and sign consistency computed on `x̃` (smoothed), not raw `X`
- `_smooth_series` uses `mode="same"` — correct, preserves length
- Dead code at `stats.py:269`: `if window_size < 1` is unreachable; the `<= 1` guard above already returns. Fix in dedicated ticket.
- Periodicity method: confirm whether FFT or Lomb-Scargle; document the choice and cite

**SotA status (last checked 2026-04):**
- These are interpretable feature statistics, not learned representations — SotA framing is less critical here
- Ensure that the statistics align with what domain experts use to describe time series segments in the target domain
- For periodicity specifically: Lomb-Scargle is more robust for irregular sampling; FFT assumes uniform sampling — verify which applies to the benchmark datasets used

---

## 4. Boundary Suggestion Service

**Purpose:** Proposes initial segment boundaries from the time series signal, cold-starting the user's segmentation before few-shot adaptation.

**Source:**
- ClaSP (Classification Score Profile): Ermshaus et al., *ClaSP — Time Series Segmentation*, ECML PKDD 2023
- BOCPD (Bayesian Online Change Point Detection): Adams & MacKay 2007 — alternative; verify which is used
- `ruptures` library: Truong et al., *Selective review of offline change point detection methods*, 2020

**Key behaviour (ClaSP):**
```
For each candidate boundary t:
    left_window  = X[t−w:t]
    right_window = X[t:t+w]
    score(t) = AUC of binary classifier(left, right)
Boundaries = local maxima of score profile above threshold
```

**What to check:**
- Which change-point method is actually used? Read `services/suggestion/` and document here
- Is window size `w` configurable from domain config?
- Are duplicate or near-duplicate boundary proposals deduplicated?
- Is uncertainty (score profile value) surfaced and stored for the uncertainty overlay (STEP-10)?

**SotA status (last checked 2026-04):**
- ClaSP is competitive for unsupervised change-point detection as of 2023
- Check: BinSeg with model selection, PELT with improved penalties, any 2024-2025 neural change-point detection
- Key question for auditor: for the interactive setting where the user will correct boundaries anyway, does the cold-start quality matter enough to justify a more complex method? Or is ClaSP's speed + interpretability the right tradeoff?

---

## 5. Constraint Evaluation

**Purpose:** Checks whether a proposed operation violates domain constraints and returns a status (PASS / WARN / FAIL / PROJECTED).

**Source:**
- Minimum duration: internal domain rule — document the value and its basis in `docs/domain-config-note.md`
- Monotonic trend: standard OLS sign consistency — internal definition
- Plateau stability: variance threshold — internal definition; threshold in domain config
- Label compatibility: event adjacency rule — internal; currently only `event+event` is checked

**What to check:**
- `load_domain_config()` must be decorated with `@functools.lru_cache(maxsize=1)` — it is called at the start of every constraint function and currently re-parses JSON every time (known bug)
- Label compatibility currently only checks `event+event` adjacency — other rules (`trend+trend` is valid, `anomaly+anomaly` needs review) should be documented even if not yet enforced
- Is the `PROJECTED` path implemented? Does it correctly snap to the nearest valid segmentation?

**SotA status:**
- These are rule-based constraints, not learned — SotA framing does not apply
- The key design question is whether the constraint set is *complete* for the target domain — verify against domain expert input

---

## 6. Gradient-Based Counterfactual Synthesis (within segment)

**Purpose:** Given a segment `[b_k, e_k]`, generate a counterfactual that changes the model prediction toward target class `c*` while staying close to the original and satisfying constraints.

**Source:**
- Wachter et al., *Counterfactual Explanations without Opening the Black Box*, HJLP 2018 — foundational CE objective
- Mothilal et al., *DICE: Diverse Counterfactual Explanations*, FAT* 2020 — diversity extension (if used)
- Glacier: Wang et al., ML Journal 2024 — segment-constrained gradient CE, closest prior work

**Key equations:**
```
Loss:    L = L_task(f(X_edit), c*) + α‖X_edit − X[b:e]‖² + λ·L_phys(X_edit, constraints)
Update:  X_edit ← X_edit − η · ∇_{X_edit} L
Bounds:  X_edit constrained to semantic operation space of segment type y_k
```

**Correct behaviour:**
- Optimisation operates **only on `X[b:e]`**, not the full series
- `L_phys` encodes soft constraint violations as differentiable penalties
- Hard constraints are enforced by projection after each gradient step, not via loss
- `α` and `λ` are documented hyperparameters with empirical basis

**What to check:**
- Is the gradient computation graph correctly bounded to the segment slice?
- Are hard constraints applied via projection (not just added to loss)?
- Are `α` and `λ` documented and configurable?
- Is this feature fully implemented or a stub? Check `services/` for counterfactual synthesis

**SotA status (last checked 2026-04):**
- Gradient-based CE within constrained subspace is appropriate
- Check: CONFETTI (AAAI 2026) — multi-objective CE for MTS using key subsequences; most relevant comparison
- Key question: does CONFETTI's multi-objective formulation outperform the single-objective + penalty approach? This affects the paper's technical claims.

---

## 7. Evaluation Metrics

### WARI — Weighted Adjusted Rand Index
**Source:** Adapted from Rand Index; position-sensitivity extension for temporal data.  
**Why over ARI:** Interior errors penalised more than boundary-adjacent errors; better reflects perceptual segment quality.  
**Use:** Primary segmentation quality metric in the technical evaluation.

### SMS — State Matching Score
**Source:** Internal / benchmark standard.  
**What it measures:** Error type breakdown: delay, isolation, transition, missing.  
**Use:** Diagnostic alongside WARI — tells *what kind* of error, not just how much.

### Boundary F1 @ tolerance δ
**Source:** Standard in change-point detection literature.  
**Use:** Alignment measure `A(S^U, S^M)` uses boundary F1 as one component.

### Covering
**Source:** Arbelaez et al. (image segmentation), adapted for TS; reported by TSSB benchmark.  
**Use:** Cross-benchmark comparability — report alongside WARI.

---

## 8. Sources Not Yet Verified Against Code

The following are referenced in the project but the exact implementation details need to be confirmed by reading the code:

| Algorithm | Reference | What to verify |
|---|---|---|
| Periodicity statistic | FFT vs. Lomb-Scargle | Which method is used in `stats.py`? |
| Change-point detection | ClaSP vs. BOCPD vs. `ruptures` | Which is in `services/suggestion/`? |
| HSMM variant | Murphy 2002 vs. Yu 2010 | Which duration prior is used? |
| Counterfactual synthesis | Gradient-based vs. stub | Is it implemented or placeholder in services? |

**When code access is available, run `algorithm-auditor` on each of these to fill in the correct source and verify correctness.**
