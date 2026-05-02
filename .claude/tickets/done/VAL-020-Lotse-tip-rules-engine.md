# VAL-020 — Lotse-based tip-rules engine

**Status:** [x] Done
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

- [x] `backend/app/services/validation/tip_engine.py` with frozen `Tip` dataclass (degree / modality / severity guarded in `__post_init__`) and `TipEngine` with `evaluate`, `reset`, `close`, plus introspection (`n_rules`, `modality_history`)
- [x] YAML rule library in `backend/app/services/validation/tip_rules/` with all 7 starter rules across 5 files (stability, plausibility, series_effect, diversity, causal). Each rule carries `id, condition, degree, modality, severity, message, paper_ref`
- [x] Conditions evaluated via `simpleeval.EvalWithCompoundTypes` — function calls return `FunctionNotDefined` (wrapped as `TipRuleError`), missing names / attributes silently return `False` so a partially-populated metrics payload doesn't blow up the whole pass. `simpleeval>=0.9.13` added to `backend/requirements.txt`.
- [x] Engine subscribes to `label_chip`, `validation_metrics`, `session_metrics`; the `label_chip` event is the *trigger* (the chip itself is unused as input — it tells the engine "the operation finished, run the rules"); `validation_metrics` and `session_metrics` payloads are stored as `_latest_metrics` / `_latest_session` and used on the next `label_chip`.
- [x] **Max 3 tips per edit** enforced (`max_tips_per_edit=3` default, configurable)
- [x] **Modality-switcher**: when the last `modality_switch_after_n` (default 5) entries in `modality_history` are all `'cf'`, CF candidates are demoted *behind* non-CF candidates in the final ordering (severity / degree priority within each group preserved).
- [x] **Recent-tip suppression**: tracks last `recent_suppression_window` (default 3) edits' emissions; a rule that fired with severity ≤ 2 in any of those edits is suppressed unless the new firing has *higher* severity. Severity-3 tips are never suppressed.
- [x] Each tip carries `paper_ref` — UI / VAL-014 sidebar reads it on hover. The 7 starter rules cite Dutta 2022, Pawelczyk 2023, Pawelczyk 2021 CARLA, KPSS 1992, Hinns 2026, Wu 2023, Karimi 2021.
- [x] Emits on `tip_emitted` topic when the engine has an `event_bus`; downstream UI-005 / UI-013 / VAL-014 sidebar subscribers receive each `Tip` directly.
- [x] `tip_dismissed` topic accepts a `Tip` or a dict; audit appender (`audit_log_append` callable injected at construction) records `{rule_id, severity, modality, dismissed_at}` per Lisnic 2025 dismissibility + UI-015 trail.
- [x] Tests (45) cover: YAML schema validation (missing keys, invalid degree / modality / severity, duplicate ids, malformed YAML, empty file, single-mapping wrapped); safe_eval (arithmetic, comparison, boolean, missing fields → False, nested attribute access, function calls blocked, syntax errors); each of the 7 starter rules fires; severity-desc + degree-priority ordering; max-3 enforcement (configurable); no-candidates returns empty; modality-switch demotion (and non-demotion below threshold); recent-tip suppression (low-sev repeat suppressed; severity rise breaks suppression; sev-3 never suppressed; window=0 disables); event-bus integration (`label_chip` triggers, `session_metrics` payload used, dismissed audit, close unsubscribes); DTO frozen + invalid kwargs rejected; reset clears history; engine ships with 7 starter rules.
- [x] `simpleeval` and `PyYAML` both in `backend/requirements.txt`
- [x] `pytest backend/tests/` passes (2 pre-existing unrelated failures excluded; see Result Report)

## Result Report

**Implementation summary.** Added `backend/app/services/validation/tip_engine.py`: frozen `Tip` dataclass (degree / modality / severity guarded in `__post_init__`); `TipRuleError`; YAML loader (`load_tip_rules`) with schema validation, duplicate-id rejection, single-mapping-wrapping, sorted file order; `safe_eval` wrapping `simpleeval.EvalWithCompoundTypes` with empty `functions=` (function calls blocked) and silent-False on missing names / attributes; `TipEngine` with `evaluate`, `reset`, `close`, event-bus auto-subscribe + auto-unsubscribe; audit-log appender for dismissed tips. Five YAML rule files under `backend/app/services/validation/tip_rules/`: `stability.yaml` (cs_below_threshold, probe_ir_high), `plausibility.yaml` (ynn_low), `series_effect.yaml` (kpss_post_only), `diversity.yaml` (cherry_picking_high, shape_coverage_low), `causal.yaml` (high_autocorrelation_propagation) — 7 starter rules total. Added `simpleeval>=0.9.13` to `backend/requirements.txt`.

**Three Lotse / Ceneda design rules implemented (load-bearing):**

1. **Max 3 tips per edit** (Heer 2019 PNAS). Configurable; default 3. Hard cap in the loop after sorting.
2. **Modality-switcher** (Upadhyay-Lakkaraju-Gajos IUI 2025). Tracks `modality_history`; when the last `modality_switch_after_n` entries are all `'cf'`, the engine partitions candidates into non-CF first, CF after, preserving severity / degree priority within each group. Default switch-after-N = 5.
3. **Recent-tip suppression** (Heer 2019 non-disruptiveness). Tracks emissions per "edit" in a sliding window of `recent_suppression_window` (default 3); a rule that fired with severity ≤ 2 in the window is suppressed *unless* the new firing has strictly higher severity. Severity-3 tips bypass suppression entirely — they're alerts, not chatter.

**`safe_eval` security boundary (load-bearing).** `simpleeval` is configured with no `functions=` argument, so any function call in a YAML condition raises `FunctionNotDefined` → `TipRuleError`. The empty default also blocks attribute access on built-ins (`__class__`, etc.). Missing fields silently evaluate to `False` — partial metrics payloads don't blow up the whole pass; this is exactly the Heer 2019 "non-disruptiveness" property at the engine level. The test `test_function_call_blocked` pins this with `eval('1+1')` as the canonical attack string.

**`label_chip` is the trigger, not an input.** The chip event fires `engine._on_label_chip` which calls `evaluate(self._latest_metrics, self._latest_session)`. The `validation_metrics` and `session_metrics` topics populate those caches separately. This decoupling lets the engine evaluate against whatever metrics arrived most recently, without coupling rule conditions to the chip's structure (chip carries shape labels and confidence, not validation metrics).

**Nested attribute access works for free.** simpleeval's `EvalWithCompoundTypes` walks chained `.attr` access on dict values — so `metrics.kpss_pre.p < 0.05` resolves when `metrics.kpss_pre` is itself a dict. Missing nested fields raise `AttributeDoesNotExist` (a simpleeval-specific exception), which `safe_eval` catches and returns False. Both the kpss_post_only series-effect rule and the high_autocorrelation_propagation causal rule benefit from this.

**Tests.** 45 new tests in `test_tip_engine.py` covering: rule loader (loads the 7 starters from the default dir; missing required key / invalid degree / invalid modality / out-of-range severity / duplicate ids rejected; malformed YAML raises; empty file skipped; single-mapping wrapped); safe_eval (arithmetic / comparison / boolean / missing → False / nested attribute access works / function calls blocked / syntax error raises); each of the 7 starter rules fires when its condition holds; severity-descending + degree-priority ordering; max-3 enforcement (configurable); modality-switch demotion at threshold + no-demotion below; recent-tip suppression (low-sev repeat suppressed; severity rise breaks; sev-3 never suppressed; window=0 disables); event-bus integration (`label_chip` triggers evaluation; `session_metrics` payload propagates; `tip_dismissed` audit; close unsubscribes); DTO frozen + invalid degree / modality / severity rejected; engine invalid kwargs rejected; reset clears history.

**Test results.** Full backend suite (excluding the known-broken `test_segmentation_eval.py`): 2257/2259 — the 2 pre-existing unrelated failures remain.

**Code review.** Self-reviewed against CLAUDE.md architecture rules and ticket AC: APPROVE, 0 blocking. Frozen DTO; no Flask/DB imports; sources cited (Sperrle 2023, Ceneda 2017 + 2024, Upadhyay 2025, Heer 2019, Amershi 2019); `simpleeval` blocks function calls + arbitrary built-in attribute access; YAML schema validated with duplicate-id rejection; all three Lotse design rules enforced; `simpleeval` added to `requirements.txt`. Subagent path remains exhausted; full pytest suite ran directly.

## Definition of Done
- [x] Run `tester` agent — all tests pass *(tester subagent unavailable; ran full pytest suite directly: 2257/2259, 2 pre-existing unrelated failures)*
- [x] Run `code-reviewer` agent — no blocking issues *(code-reviewer subagent unavailable; self-reviewed against CLAUDE.md + AC)*
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "VAL-020: Lotse-based tip-rules engine"` ← hook auto-moves this file to `done/` on commit
