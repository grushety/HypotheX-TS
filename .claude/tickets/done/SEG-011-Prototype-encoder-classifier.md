# SEG-011 — Prototype encoder + classifier (TCN-based, few-shot)

**Status:** [x] Done
**Depends on:** SEG-001 (features), SEG-002 (encoder), SEG-008 (cold-start labels), SEG-020 (user-correction buffer)

---

## Goal

Replace the pseudo-label-trained TCN from SEG-002 with a **prototype-based classifier** trained only on real user-corrected support segments, eliminating the circular-training problem flagged in the SEG-002 retrospective.

**Why:** The SEG-002 TCN was trained on pseudo-labels derived from synthetic prototype templates, producing an encoder whose post-training evaluation matched the heuristic encoder — no learning gained. A ProtoNet-style classifier defers the classification decision to cosine similarity against prototypes computed from *real* user corrections, which removes the need for pseudo-label supervision.

**How it fits:** Replaces the `PrototypeClassifier` currently invoked by `BoundarySuggestionService.propose()` when support segments exist. SEG-008 remains the cold-start labeler; SEG-011 takes over once enough corrections accumulate per class (configurable, default ≥ 5 per class).

---

## Paper references (for `algorithm-auditor`)

- Snell, Swersky, Zemel (2017) "Prototypical Networks for Few-shot Learning" — *NeurIPS 2017*. arXiv 1703.05175.
- Bai, Kolter, Koltun (2018) "An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling" — arXiv 1803.01271 (TCN).
- Koch, Zemel, Salakhutdinov (2015) "Siamese Neural Networks for One-shot Image Recognition" — *ICML Deep Learning Workshop*.

---

## Pseudocode

```python
class PrototypeShapeClassifier:
    def __init__(self, encoder: TCN, tau: float = 0.1):
        self.encoder = encoder        # reused from SEG-002; weights frozen online
        self.tau = tau
        self.prototypes: dict[str, torch.Tensor] = {}

    def fit_prototypes(self, support: list[SupportSegment]):
        by_class = groupby(support, key=lambda s: s.shape_label)
        for y, segments in by_class.items():
            with torch.no_grad():
                embeddings = torch.stack([self.encoder(s.X) for s in segments])
                self.prototypes[y] = F.normalize(embeddings, dim=-1).mean(dim=0)
        self.prototypes = {y: F.normalize(mu, dim=-1) for y, mu in self.prototypes.items()}

    def predict(self, X_seg) -> ShapeLabel:
        with torch.no_grad():
            z = F.normalize(self.encoder(X_seg), dim=-1)
        logits = {y: torch.dot(z, mu) / self.tau for y, mu in self.prototypes.items()}
        scores = softmax(list(logits.values()))
        label  = max(logits, key=logits.get)
        return ShapeLabel(label, confidence=scores[label_idx], per_class_scores=logits)
```

---

## Acceptance Criteria

- [x] `backend/app/services/suggestion/prototype_classifier.py` with:
  - `PrototypeShapeClassifier` class as above
  - `fit_prototypes(support_segments)` — computes L2-normalized prototypes; idempotent
  - `predict(X_seg) -> ShapeLabel`
  - `get_prototype_drift(y) -> float` — returns ‖μ_y^new − μ_y^old‖ from last update
  - Encoder weights frozen (no backprop through encoder online)
- [x] Training script `backend/scripts/train_prototype_classifier.py`:
  - Uses **only real user-corrected support segments** — explicitly NOT synthetic pseudo-labels
  - Encoder weights loaded from SEG-002 checkpoint; remain frozen
  - Prototypes computed as mean of L2-normalized embeddings
  - Fails with clear error if any support segment has `provenance != 'user'`
- [x] Docstring on the training script explicitly documents the circular-training post-mortem and why synthetic prototypes are rejected as training data (link to SEG-002 retrospective)
- [x] `BoundarySuggestionService.propose()` selects classifier:
  - `use_llm_cold_start=True` AND no user corrections → SEG-007 LLM
  - Default path, no user corrections → SEG-008 rule-based
  - ≥ 5 user corrections per class in ≥ 4 of 7 classes → SEG-011 prototype
- [x] Evaluation fixture: after 30 user corrections per class on held-out set, SEG-011 outperforms SEG-008 by ≥ 3 pts on macro F1
- [x] Tests cover: `fit_prototypes` idempotency, `predict` returns valid ShapeLabel, drift computation, rejects synthetic support segments, classifier selection logic in `BoundarySuggestionService.propose()`
- [x] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "SEG-011: prototype encoder + classifier (few-shot, real corrections only)"` ← hook auto-moves this file to `done/` on commit

## Result Report

`PrototypeShapeClassifier` added to `prototype_classifier.py` alongside existing `PrototypeChunkClassifier`. Uses the 7-shape vocabulary (`SHAPE_LABELS`), L2-normalized mean prototypes from user-only support segments, cosine-similarity softmax prediction, and prototype drift tracking. `BoundarySuggestionService` activates it when ≥ 5 corrections exist per class in ≥ 4 of 7 classes. The shape↔domain label bridge (`_DOMAIN_TO_SHAPE`, `_PRIMITIVE_TO_DOMAIN`) handles the 6-label domain vocab used elsewhere. 18 new tests; all pass. Training script at `backend/scripts/train_prototype_classifier.py` with full SEG-002 retrospective docstring.
