# VAL-020 — Lotse-based tip-rules engine

**Status:** [ ] Done
**Depends on:** VAL-001..014 (validation metrics produce the inputs); UI-005 (palette consumes tier=orienting tips); UI-013 (predicted-label chip consumes tier=directing tips)

---

## Goal

Implement the **tip-generation layer** that consumes per-edit and session-level validation outputs (VAL-001..014) and emits short, dismissible, ranked guidance messages to the user. Built on the **Lotse** YAML-strategy framework (Sperrle et al. TVCG 2023). Each tip declares its **Ceneda guidance degree** (orienting / directing / prescribing) and its **modality** (CF / feature-importance / contingency / contrastive). A modality-switcher (Upadhyay-Lakkaraju-Gajos IUI 2025) prevents over-reliance on a single tip type.

**Why:** Without this layer, the validation metrics are diagnostic numbers a researcher reads off badges — but most users will not act on raw p-values. Tips translate metrics into actionable suggestions ("try a sparser primitive", "this segment has high uncertainty") and constitute the **fourth publishable contribution** of HypotheX-TS — first deployed Lotse-style guidance system in TS-XAI.

**How it fits:** Subscribes to the event bus (label_chip events + per-edit metric events). On each event, evaluates rules in priority order, emits up to 3 tips per edit. Tips render in a dedicated UI-005 sidebar slot below the operation palette.

---

## Paper references (for `algorithm-auditor`)

- Sperrle, Ceneda, El-Assady, **"Lotse: A Practical Framework for Guidance in Visual Analytics,"** *IEEE TVCG* 29:1124–1134 (2023), DOI 10.1109/TVCG.2022.3209393.
- Ceneda, Gschwandtner, May, Miksch, Schulz, Streit, Tominski, **"Characterizing Guidance in Visual Analytics,"** *IEEE TVCG* 23:111–120 (2017), DOI 10.1109/TVCG.2016.2598468 (orienting / directing / prescribing degrees).
- Ceneda, Collins, El-Assady, Miksch, Tominski, Arleo, **"A Heuristic Approach for Dual Expert/End-User Evaluation of Guidance,"** *IEEE TVCG* 30:997–1007 (2024), DOI 10.1109/TVCG.2023.3327152 (non-disruptiveness, controllability, visibility heuristics).
- Upadhyay, Lakkaraju, Gajos, **"Counterfactual Explanations May Not Be the Best Algorithmic Recourse Approach,"** *IUI 2025*, DOI 10.1145/3708359.3712095 (modality-switching motivation).
- Heer, **"Agency plus Automation,"** *PNAS* 116:1844–1850 (2019), DOI 10.1073/pnas.1807184115 (max-3-tips and dismissibility design rationale).
- Amershi et al., **"Guidelines for Human-AI Interaction,"** *CHI 2019*, DOI 10.1145/3290605.3300233.

---

## Tip-rule library (initial — derived from Statistical Validation SOTA §D.5)

YAML rules in `backend/app/services/validation/tip_rules/*.yaml`. Each rule is a triplet `{condition, message_template, metadata}`.

```yaml
# backend/app/services/validation/tip_rules/stability.yaml
- id: cs_below_threshold
  condition: "metrics.cs < 0.6"
  degree: directing
  modality: cf
  severity: 2
  message: "Edit is fragile: small jitter in {coefficient_name} flips ~{invalidation_pct}% of nearby predictions. Try perturbing by ±10%."
  paper_ref: "Dutta et al. ICML 2022"

- id: probe_ir_high
  condition: "metrics.probe_ir > 0.2"
  degree: directing
  modality: cf
  severity: 2
  message: "~{ir_pct}% of imperfect realisations of this edit would invalidate the CF. Consider a larger amplitude for a robustness margin."
  paper_ref: "Pawelczyk et al. ICLR 2023"

# backend/app/services/validation/tip_rules/plausibility.yaml
- id: ynn_low
  condition: "metrics.ynn < 0.5"
  degree: directing
  modality: contrastive
  severity: 1
  message: "Edited series has few same-class neighbours — likely off-manifold. Consider replace_from_library with a Native-Guide donor."
  paper_ref: "Pawelczyk CARLA NeurIPS 2021 D&B"

# backend/app/services/validation/tip_rules/series_effect.yaml
- id: kpss_post_only
  condition: "metrics.kpss_pre.p > 0.05 and metrics.kpss_post.p < 0.05"
  degree: orienting
  modality: cf
  severity: 1
  message: "Edit appears to have introduced non-stationary drift (KPSS rejected post-edit only)."
  paper_ref: "Kwiatkowski-Phillips-Schmidt-Shin 1992"

# backend/app/services/validation/tip_rules/diversity.yaml
- id: cherry_picking_high
  condition: "session.cherry_picking_score > 0.7"
  degree: prescribing
  modality: contrastive
  severity: 3
  message: "{cherry_picking_recommendation}"
  paper_ref: "Hinns et al. arXiv 2601.04977 (2026)"

- id: shape_coverage_low
  condition: "session.shape_coverage < 0.4 and session.edit_count >= 5"
  degree: orienting
  modality: contrastive
  severity: 1
  message: "You have only explored {shapes_used}/7 shape primitives. Try {underexplored_shape} for contrast."
  paper_ref: "Wu et al. ScatterShot IUI 2023"

# backend/app/services/validation/tip_rules/causal.yaml
- id: high_autocorrelation_propagation
  condition: "metrics.autocorr_at_lag_k > 0.5 and metrics.k_steps_after_edit_in_horizon"
  degree: directing
  modality: contingency
  severity: 2
  message: "Edit at t={t_edit} likely propagates to t={t_edit + k}; verify CF validity downstream."
  paper_ref: "Karimi-Schölkopf-Valera FAccT 2021"
```

---

## Pseudocode

```python
# backend/app/services/validation/tip_engine.py
@dataclass(frozen=True)
class Tip:
    rule_id: str
    degree: Literal['orienting', 'directing', 'prescribing']
    modality: Literal['cf', 'feature_importance', 'contingency', 'contrastive']
    severity: int                  # 1=info, 2=warn, 3=alert
    message: str                   # rendered (placeholders filled)
    paper_ref: str
    dismissible: bool = True
    timestamp: str = ...

class TipEngine:
    def __init__(self, rule_dirs: list[Path], max_tips_per_edit: int = 3,
                 modality_switch_after_n: int = 5):
        self.rules = self._load_yaml_rules(rule_dirs)
        self.max_tips_per_edit = max_tips_per_edit
        self.modality_history = []        # last N tip modalities
        self.modality_switch_after_n = modality_switch_after_n

    def evaluate(self, metrics: dict, session: dict, context: dict) -> list[Tip]:
        # 1. Evaluate all rules
        env = {'metrics': metrics, 'session': session, **context}
        candidates = []
        for rule in self.rules:
            try:
                if safe_eval(rule['condition'], env):
                    candidates.append(self._render(rule, env))
            except Exception as exc:
                log_warning(f"tip rule {rule['id']} eval failed: {exc}")

        # 2. Sort by severity (desc) then degree (prescribing > directing > orienting)
        degree_order = {'prescribing': 3, 'directing': 2, 'orienting': 1}
        candidates.sort(key=lambda t: (-t.severity, -degree_order[t.degree]))

        # 3. Modality-switching: if last N tips were all `cf`, demote `cf` candidates
        if self._last_n_all_same_modality('cf', self.modality_switch_after_n):
            candidates = [c for c in candidates if c.modality != 'cf'] + \
                         [c for c in candidates if c.modality == 'cf']

        # 4. Take top-k, suppress duplicates of recent tips
        out = []
        for c in candidates:
            if len(out) >= self.max_tips_per_edit: break
            if self._was_emitted_recently(c.rule_id): continue
            out.append(c)

        for tip in out:
            self.modality_history.append(tip.modality)
        return out
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/tip_engine.py` with `Tip` dataclass and `TipEngine` per pseudocode
- [ ] YAML rule library in `backend/app/services/validation/tip_rules/` with at least the 7 starter rules above (stability, plausibility, series-effect, diversity, causal). Each rule carries `id, condition, degree, modality, severity, message, paper_ref`
- [ ] Conditions evaluated via a sandboxed `safe_eval` (no `eval()` on raw user YAML — use `simpleeval` or a vetted alternative listed in `requirements.txt`)
- [ ] Engine subscribes to event bus topics: `label_chip` (post-op), `validation_metrics` (per-edit), `session_metrics` (every accepted CF)
- [ ] **Max 3 tips per edit, enforced**
- [ ] **Modality-switcher:** if last 5 consecutive emitted tips all have `modality == 'cf'`, the next round demotes CF candidates and prefers non-CF modalities (Upadhyay-Lakkaraju-Gajos IUI 2025 design rule)
- [ ] **Recent-tip suppression:** a rule that fired in the last 3 edits with severity ≤ 2 is suppressed unless severity rises (Heer 2019 design rule)
- [ ] Each tip carries the originating paper reference; UI surfaces it on hover (researcher-mode)
- [ ] Tips emit on the `tip_emitted` event bus topic; UI-005 sidebar slot subscribes
- [ ] Dismissed tips are logged in audit (UI-015) with `dismissed_at` timestamp
- [ ] Tests cover: each starter rule fires when its condition holds; max-3 enforcement; modality-switch after 5 CF tips; recent-tip suppression; severity ordering; YAML schema validation
- [ ] `simpleeval` and `pyyaml` added to `backend/requirements.txt`
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "VAL-020: Lotse-based tip-rules engine"` ← hook auto-moves this file to `done/` on commit
