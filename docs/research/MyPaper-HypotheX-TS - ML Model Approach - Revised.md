# MyPaper-HypotheX-TS - ML Model Approach

## 3.X Operation-Aware Suggestion Model for Semantic Time-Series Segmentation

HypotheX-TS uses a suggestion model to support interactive semantic segmentation without making the model the sole source of truth. The formal chunk ontology is defined independently by operational predicates over the signal; the model only estimates where plausible chunk boundaries and chunk labels are likely to occur, with what confidence, and how its proposals should adapt after user correction.

This separation is central to the framework. The contribution is not a purely algorithmic segmentation model, but a user-centered interaction layer in which semantic segmentation serves both as a manipulation space and as an instrument for probing temporal mental models.

## 3.X.1 Model role

The suggestion model has three functions:

1. propose candidate segment boundaries,
2. assign chunk labels to candidate segments,
3. update its proposals from accepted user corrections.

The model therefore acts as an assistive component rather than an oracle. Final authority remains with the user, and all downstream typed operations are still checked by the constraint engine.

## 3.X.2 Input representation

Let

$$
X = (x_t)_{t=1}^{T}, \qquad x_t \in \mathbb{R}^d
$$

be a univariate or multivariate time series. The model operates on an augmented representation

$$
X^{\mathrm{feat}} \in \mathbb{R}^{T \times d'}
$$

where $d' \ge d$ may include:

- raw signal,
- smoothed signal $\tilde{X}$,
- first difference $\Delta x_t = x_t - x_{t-1}$,
- second difference,
- local z-score,
- missingness mask.

For few-shot adaptation, the model additionally receives a support set of user-validated segments

$$
\mathcal{D}_{\mathrm{sup}} = \{(X_{b:e}, y, b, e)\}
$$

where $[b,e]$ are accepted boundaries and $y \in \mathcal{Y}$ is the semantic chunk label.

## 3.X.3 Output space

Given a series $X$, the model returns a segmentation proposal

$$
S^M = \{(\hat{b}_k, \hat{e}_k, \hat{y}_k, c_k, u_k)\}_{k=1}^{\hat{K}}
$$

where:

- $[\hat{b}_k, \hat{e}_k]$ are proposed segment boundaries,
- $\hat{y}_k \in \mathcal{Y}$ is the proposed chunk label,
- $c_k \in [0,1]$ is confidence,
- $u_k$ is uncertainty.

Internally, the proposal is decomposed into:

1. boundary scores
   $$
   p_t^{\mathrm{bdry}} = p(\text{boundary at } t \mid X),
   $$
2. segment embeddings
   $$
   z_s = f_{\theta}(X_{b:e}) \in \mathbb{R}^{m},
   $$
3. chunk probabilities
   $$
   p(y \mid X_{b:e}), \qquad y \in \mathcal{Y}.
   $$

## 3.X.4 Architecture

The revised architecture is intentionally minimal for the first implementation.

### Boundary proposal

In the minimum viable system, boundaries are proposed by a change-point detector such as ClaSP or an equivalent unsupervised segmentation method. This produces a set of candidate boundaries

$$
B(X) = \{t \in \{2,\dots,T-1\} : p_t^{\mathrm{bdry}} \ge \tau_{\mathrm{bdry}}\}
$$

or directly a provisional segmentation. A learned boundary head is not required in the first version; it can be added later only if boundary quality becomes the dominant bottleneck.

### Segment encoder

Each candidate segment $s=[b,e]$ is mapped to a fixed-dimensional representation

$$
z_s = f_{\theta}(X_{b:e}) \in \mathbb{R}^{m}.
$$

For the first implementation, $f_{\theta}$ is a small 1D temporal convolutional encoder. To reduce length bias, segment inputs are either resampled to a fixed length or pooled with attention rather than naive mean pooling.

### Prototype classifier

Each chunk type $y \in \mathcal{Y}$ is represented by a prototype vector

$$
\mu_y = \frac{1}{|D_y|} \sum_{s \in D_y} \bar{z}_s
$$

where $D_y$ is the set of support segments for class $y$ and $\bar{z}_s$ denotes an L2-normalized embedding.

Chunk probabilities are then computed by cosine similarity:

$$
p(y \mid s)
=
\frac{\exp(\cos(\bar{z}_s, \bar{\mu}_y)/\tau)}
{\sum_{y' \in \mathcal{Y}} \exp(\cos(\bar{z}_s, \bar{\mu}_{y'})/\tau)}.
$$

This preserves the few-shot advantages of prototype learning while making the geometry of the embedding space more stable than raw Euclidean distance.

### Duration regularization

In the first implementation, temporal coherence is enforced by simple duration rules rather than a full HSMM. Let $L_{\min}(y)$ denote the minimum plausible duration of class $y$. If a predicted segment violates this rule, it is merged with the most compatible neighbor according to label probability and embedding similarity.

A full HSMM decoder remains an optional extension for later ablations, but it is not required for the MVP.

## 3.X.5 Training objective

The model is trained incrementally. The initial objective is deliberately simple:

$$
\mathcal{L} = \mathcal{L}_{\mathrm{cls}}.
$$

### Classification loss

For support set segments with labels $y_s$,

$$
\mathcal{L}_{\mathrm{cls}}
=
-\sum_{s \in \mathcal{D}_{\mathrm{sup}}}
\log p(y_s \mid s).
$$

This loss is sufficient for the first prototype-based version.

### Optional boundary loss

If a learned boundary module is later introduced, it can be trained with

$$
\mathcal{L}_{\mathrm{bdry}}
=
-\sum_{t=1}^{T}
\left[
\hat{g}_t \log p_t^{\mathrm{bdry}}
+
(1-\hat{g}_t)\log(1-p_t^{\mathrm{bdry}})
\right]
$$

where $\hat{g}_t$ is the ground-truth boundary indicator.

### Optional consistency loss

If classification proves brittle under mild perturbations, add

$$
\mathcal{L}_{\mathrm{cons}}
=
\sum_s D\bigl(p(\cdot \mid s), p(\cdot \mid a(s))\bigr)
$$

for semantic-preserving augmentations $a(\cdot)$ such as light amplitude scaling, mild time shifts, or small additive noise.

### Optional constraint-aware penalty

To integrate the segmentation model more tightly with the constraint engine, define a constraint-violation penalty

$$
\mathcal{L}_{\mathrm{const}} = \alpha \cdot \mathrm{Viol}(S^M)
$$

where $\mathrm{Viol}(S^M)$ counts or weights proposed segments that systematically induce invalid typed operations. This term is not required for the first implementation, but it provides a natural path toward operation-aware learning.

## 3.X.6 Few-shot adaptation from interaction

The model is updated only from accepted user corrections. Online adaptation is restricted to prototype updates in the first version.

After every $N$ validated edits, prototypes are recomputed from a bounded memory buffer per class:

$$
\mu_y^{\mathrm{new}} = \frac{1}{|D_y^{\mathrm{buf}}|} \sum_{s \in D_y^{\mathrm{buf}}} \bar{z}_s.
$$

Two safeguards stabilize adaptation:

1. **confidence gating**: only corrections above a minimum acceptance quality are used for prototype updates,
2. **bounded memory**: each class stores only the most recent or most representative $M$ support segments.

Prototype drift is tracked by

$$
\Delta_y^{(t)} = \|\mu_y^{(t)} - \mu_y^{(t-1)}\|,
$$

and updates can be frozen if drift exceeds a preset threshold.

Encoder weights remain frozen online in the MVP. Fine-tuning can be added later if enough curated corrections accumulate.

## 3.X.7 Inference procedure

At inference time, the model proceeds in five steps:

1. propose candidate boundaries,
2. encode each provisional segment,
3. assign chunk label probabilities from prototypes,
4. apply duration-based cleanup,
5. expose the proposal to the user together with confidence and uncertainty.

The user may then accept, reject, split, merge, or relabel any segment. Accepted corrections are logged and later used for few-shot adaptation.

## 3.X.8 Relation to the formal chunk vocabulary

The suggestion model does not define the semantic chunk ontology. It operates over the formally defined chunk space and estimates where those chunk types are likely to occur. The formal predicates still determine what counts as a plausible trend, plateau, spike, event, transition, or periodic segment; the model only supplies candidate boundaries, label probabilities, and uncertainty estimates. This preserves the central design principle of HypotheX-TS: semantic segmentation remains a user-centered interaction layer rather than a hidden backend abstraction.

## 3.X.9 Minimal API

```python
propose_segments(X, context=None, priors=None) -> SegmentationProposal
encode_segment(X, b, e) -> embedding
predict_chunk_label(X, b, e) -> label_probs
adapt_model(support_set, budget=None) -> model_version
score_uncertainty(X, S) -> boundary_uncertainty, label_uncertainty
```

## 3.X.10 Design rationale

This revised model design intentionally avoids premature complexity. It preserves the project's core logic — semantic chunk formalism, typed operations, and few-shot interaction-driven adaptation — while reducing unnecessary moving parts in the initial system. The architecture can therefore be implemented and evaluated as a stable assistive layer first, and only later extended with learned boundary heads, HSMM decoding, or stronger operation-aware training if ablations justify them.
