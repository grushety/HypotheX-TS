---
tags: [my-paper, section]
parent: [[MyPaper - HypotheX-TS]]
created: 2026-03-28
status: revised
---

# MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operations

## 3.X Formal Definitions for Semantic Chunk Types and Typed Operations

This section formalizes the semantic chunk vocabulary and the typed operation space used in HypotheX-TS. The goal is not to encode a universal ontology for all time series, but to define a compact, operationally usable vocabulary that supports interaction, model assistance, and constraint-aware what-if reasoning.

## 1. Time series and segmentation space

Let

$$
X = (x_t)_{t=1}^{T}, \qquad x_t \in \mathbb{R}^d
$$

be a univariate or multivariate time series, and let

$$
\tilde{X} = (\tilde{x}_t)_{t=1}^{T}
$$

denote a smoothed version of the signal.

A segment is a contiguous interval

$$
s = [b,e], \qquad 1 \le b \le e \le T
$$

with length

$$
|s| = e-b+1.
$$

A semantic segmentation is a partition

$$
S = \{(b_k,e_k,y_k)\}_{k=1}^{K}
$$

such that:

1. $1 = b_1 \le e_1 < b_2 \le \dots < b_K \le e_K = T$,
2. segments are contiguous and non-overlapping,
3. each segment has label $y_k \in \mathcal{Y}$.

We define the chunk vocabulary as

$$
\mathcal{Y} = \{\text{trend}, \text{plateau}, \text{spike}, \text{event}, \text{transition}, \text{periodic}\}.
$$

Each segment may additionally store confidence $c_k \in [0,1]$, boundary uncertainty $(\sigma_{b_k}, \sigma_{e_k})$, and provenance $\pi_k \in \{\text{user}, \text{model}, \text{imported}\}$.

## 2. Segment statistics

For any segment $s=[b,e]$, define:

### 2.1 Mean

$$
\mu(s) = \frac{1}{|s|}\sum_{t=b}^{e} x_t
$$

### 2.2 Variance

$$
\mathrm{Var}(s) = \frac{1}{|s|}\sum_{t=b}^{e}\|x_t - \mu(s)\|^2
$$

### 2.3 Linear slope

Fit a least-squares line to the smoothed signal in the segment:

$$
\tilde{x}_t \approx \alpha_s + \beta_s t, \qquad t \in [b,e]
$$

where $\beta_s$ is the segment slope.

### 2.4 Sign consistency

Let

$$
\Delta_t = \tilde{x}_{t+1} - \tilde{x}_t.
$$

Define

$$
\rho_{\mathrm{sign}}(s)
=
\max\left(
\frac{1}{|s|-1}\sum_{t=b}^{e-1}\mathbf{1}[\Delta_t>0],
\frac{1}{|s|-1}\sum_{t=b}^{e-1}\mathbf{1}[\Delta_t<0]
\right).
$$

### 2.5 Residual to line

$$
R_{\mathrm{lin}}(s)
=
\frac{1}{|s|}\sum_{t=b}^{e}\|\tilde{x}_t - (\alpha_s + \beta_s t)\|^2
$$

### 2.6 Context contrast

Let $s^-=[b-w,b-1]$ and $s^+=[e+1,e+w]$ be context windows when defined. Then

$$
C_{\mathrm{ctx}}(s)
=
\left\| \mu(s) - \frac{\mu(s^-)+\mu(s^+)}{2} \right\|.
$$

### 2.7 Peak score

Using a local rolling mean $\mu_{\mathrm{local}}(t)$ and standard deviation $\sigma_{\mathrm{local}}(t)$, define

$$
z_t = \frac{x_t - \mu_{\mathrm{local}}(t)}{\sigma_{\mathrm{local}}(t)+\varepsilon}
$$

and then

$$
P_{\max}(s) = \max_{t \in s} |z_t|.
$$

### 2.8 Periodicity score

For a lag set $\mathcal{L}$,

$$
\rho_{\mathrm{per}}(s) = \max_{\ell \in \mathcal{L}} |\mathrm{ACF}_s(\ell)|
$$

or equivalently a normalized dominant spectral peak.

## 3. Calibrated chunk scoring

Instead of assigning chunk types by a hard priority cascade alone, HypotheX-TS uses calibrated per-class scores

$$
q_y(s) \in [0,1], \qquad y \in \mathcal{Y}.
$$

Thresholds such as $\tau_{\mathrm{slope}}$, $\tau_{\mathrm{peak}}$, and $\tau_{\mathrm{per}}$ are not treated as universal constants. They are calibrated from data using small validation sets or robust empirical percentiles. For example:

- $\tau_{\mathrm{slope}}$: upper quantile of absolute slope in background segments,
- $\tau_{\mathrm{peak}}$: high quantile of local z-score magnitude,
- $\tau_{\mathrm{per}}$: lower bound on meaningful periodicity from annotated periodic segments.

The default model assignment is

$$
y^*(s) = \arg\max_{y \in \mathcal{Y}} q_y(s).
$$

If the score margin is too small,

$$
\max_y q_y(s) - \max_{y' \ne y} q_{y'}(s) < \delta,
$$

the segment is marked as uncertain and left for user confirmation.

## 4. Semantic chunk types

### 4.1 Trend

A segment $s$ is trend-like when:

$$
|\beta_s| \ge \tau_{\mathrm{slope}}, \qquad
\rho_{\mathrm{sign}}(s) \ge \tau_{\mathrm{sign}}, \qquad
R_{\mathrm{lin}}(s) \le \tau_{\mathrm{lin}}.
$$

Interpretation: sustained monotone behavior.

### 4.2 Plateau

A segment $s$ is plateau-like when:

$$
|\beta_s| < \tau_{\mathrm{slope}}, \qquad
\mathrm{Var}(s) \le \tau_{\mathrm{var}}, \qquad
\rho_{\mathrm{per}}(s) < \tau_{\mathrm{per}}.
$$

Interpretation: low-variance steady regime.

### 4.3 Spike

A segment $s$ is spike-like when:

$$
|s| \le L_{\mathrm{spike}}^{\max}, \qquad
P_{\max}(s) \ge \tau_{\mathrm{peak}}, \qquad
C_{\mathrm{ctx}}(s) \ge \tau_{\mathrm{ctx}}.
$$

Interpretation: short anomalous impulse.

### 4.4 Event

A segment $s$ is event-like when:

$$
L_{\mathrm{event}}^{\min} \le |s| \le L_{\mathrm{event}}^{\max}, \qquad
C_{\mathrm{ctx}}(s) \ge \tau_{\mathrm{ctx}},
$$

and the segment is not already better explained as a spike or periodic chunk.

Interpretation: bounded meaningful interval, for example an intervention, attack, seizure, or labeled activity.

### 4.5 Transition

A segment $s=[b,e]$ is transition-like when it connects two distinct regimes and unfolds over non-zero duration, for example when

$$
\|\mu(s^-)-\mu(s^+)\| \ge \tau_{\mathrm{jump}}
\quad \text{or} \quad
|\beta_{s^-}-\beta_{s^+}| \ge \tau_{\beta}
$$

with

$$
|s| \ge L_{\mathrm{trans}}^{\min}.
$$

Interpretation: onset, offset, or ramp between regimes.

### 4.6 Periodic

A segment $s$ is periodic-like when it contains at least two cycles and has a sufficiently high periodicity score:

$$
|s| \ge 2\hat{p}_s, \qquad
\rho_{\mathrm{per}}(s) \ge \tau_{\mathrm{per}}.
$$

Interpretation: repeating oscillatory structure.

## 5. Practical ontology note

The six-type ontology is the full conceptual vocabulary. If annotation volume is limited, the first empirical version may collapse:

- `transition` into a subtype of `trend`,
- `periodic` into a subtype of `event` or an optional extended label set.

This simplification is methodological, not conceptual. The full typed operation space remains defined below.

## 6. Operation definition

An operation is a function

$$
\mathrm{op} : (X,S,\phi) \mapsto (X',S',\Delta)
$$

where:

- $X'$ is the edited time series,
- $S'$ is the updated segmentation,
- $\phi$ contains operation parameters and constraints,
- $\Delta$ is an audit record.

We distinguish:

1. structural operations on boundaries and labels,
2. content operations on values within segments.

## 7. Structural operations

### 7.1 EditBoundary

$$
(b_k,e_k) \mapsto (b_k + \delta_b, e_k + \delta_e)
$$

subject to contiguity and minimum duration.

### 7.2 Split

$$
[b,e] \mapsto [b,t^*] \cup [t^*+1,e], \qquad b < t^* < e.
$$

### 7.3 Merge

$$
[b_k,e_k] \cup [b_{k+1},e_{k+1}] \mapsto [b_k,e_{k+1}].
$$

### 7.4 Reclassify

$$
(b,e,y) \mapsto (b,e,y').
$$

## 8. Generic value operations

### 8.1 LevelShift

$$
x_t' =
\begin{cases}
x_t + \Delta, & t \in [b,e] \\
x_t, & \text{otherwise}
\end{cases}
$$

### 8.2 AmplitudeScale

$$
x_t' =
\begin{cases}
\mu(s) + a(x_t-\mu(s)), & t \in [b,e] \\
x_t, & \text{otherwise}
\end{cases}
$$

### 8.3 TimeShift

Relocate the segment by $\delta$ timesteps using interpolation to resolve gaps and overlaps.

### 8.4 DurationScale / TimeWarp

Let

$$
u(t) = \frac{t-b}{e-b}, \qquad u' = \frac{u}{\gamma}.
$$

Then reconstruct by interpolation so that $\gamma>1$ stretches and $0<\gamma<1$ compresses the segment.

### 8.5 NoiseInject

$$
x_t' =
\begin{cases}
x_t + \eta_t, & t \in [b,e],\; \eta_t \sim \mathcal{N}(0,\sigma^2) \\
x_t, & \text{otherwise}
\end{cases}
$$

### 8.6 RemoveAndFill

Delete a segment and fill it by interpolation between neighboring values.

## 9. Typed operations per chunk

### 9.1 Trend

Allowed operations:

- ChangeSlope
- ReverseTrend
- ShiftTrendInTime
- ExtendTrend
- ShortenTrend
- Split
- Merge

Core semantic rule: preserve monotonicity unless the user explicitly requests reversal.

### 9.2 Plateau

Allowed operations:

- ShiftLevel
- AddNoise
- ExtendPlateau
- ShortenPlateau
- MergePlateaus
- Split

Core semantic rule: remain near-zero slope and low variance.

### 9.3 Spike

Allowed operations:

- ScaleSpike
- DampenSpike
- SuppressSpike
- MoveSpike
- WidenSpike
- NarrowSpike

Core semantic rule: remain short and locally exceptional.

### 9.4 Event

Allowed operations:

- ShiftEvent
- ChangeEventDuration
- ChangeEventIntensity
- RemoveEvent
- DuplicateEvent
- Split
- Merge

Core semantic rule: preserve contextual distinctness and, where relevant, causal order.

### 9.5 Transition

Allowed operations:

- ChangeTransitionSlope
- AccelerateTransition
- DecelerateTransition
- ShiftTransitionOnset
- ReverseTransition

Core semantic rule: remain a smooth regime change rather than an instantaneous jump.

### 9.6 Periodic

Allowed operations:

- ChangeAmplitude
- ChangeFrequency
- PhaseShift
- DuplicateCycle
- RemoveCycle
- Split

Core semantic rule: preserve recognizably periodic structure.

## 10. Constraints

A hard constraint is a predicate

$$
g(X',S') \le 0
$$

that must hold after an operation. A soft constraint contributes a penalty

$$
\mathcal{L}_{\mathrm{soft}}(X',S')
=
\sum_j \lambda_j \max(0,g_j(X',S')).
$$

Examples include:

- minimum duration,
- monotonic trend consistency,
- plateau stability,
- periodicity preservation,
- conservation-type constraints,
- causal ordering constraints.

## 11. Operation validity

Given a segment $s$ with label $y$, an operation is valid if:

1. it belongs to the legal set $\mathcal{O}_y$,
2. all hard constraints are satisfied after application,
3. the resulting segment remains semantically compatible unless the user explicitly requests relabeling.

Formally,

$$
\mathrm{Valid}(\mathrm{op}, s)
=
\mathbf{1}[\mathrm{op} \in \mathcal{O}_y]
\cdot
\mathbf{1}[g_j(X',S') \le 0 \; \forall j].
$$

A graded validity score is

$$
V(\mathrm{op}, s)
=
\exp\left(-\sum_j \lambda_j \max(0,g_j(X',S'))\right).
$$

## 12. Annotation schema for training

Each annotated segment should store at minimum:

- `start`
- `end`
- `chunk_type`
- `confidence`
- `provenance`

Optional derived fields:

- `mean`
- `variance`
- `slope`
- `sign_consistency`
- `peak_score`
- `periodicity_score`
- `context_contrast`

These fields support both chunk classification and later operation-aware learning.

## 13. Design rationale

This revised formalization keeps the full semantic idea intact while addressing the main weaknesses of the earlier version. Chunk definitions are still operational and mathematically grounded, but assignment is now score-based rather than purely heuristic, thresholds are explicitly calibrated from data, and ambiguity is surfaced instead of hidden. This makes the chunk vocabulary more stable for both annotation and model assistance without weakening the central idea of semantic, user-centered time-series interaction.
