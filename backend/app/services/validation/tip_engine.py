"""Lotse-based tip-rules engine (VAL-020).

Translates the per-edit and session-level metrics from VAL-001..014 into
short, dismissible, ranked guidance messages following:

  Sperrle, Ceneda, El-Assady, "Lotse: A Practical Framework for Guidance
  in Visual Analytics," *IEEE TVCG* 29:1124–1134 (2023),
  DOI:10.1109/TVCG.2022.3209393.

Each tip declares:
  * **Ceneda guidance degree** — orienting / directing / prescribing
    (Ceneda et al. *IEEE TVCG* 23:111–120, 2017).
  * **modality** — cf / feature_importance / contingency / contrastive
    (Upadhyay-Lakkaraju-Gajos IUI 2025).

The engine enforces three Lotse / Ceneda design rules:
  1. **Max 3 tips per edit** (Heer 2019 PNAS, agency-plus-automation).
  2. **Modality switching:** after N consecutive CF tips, demote CF
     candidates to prevent over-reliance (Upadhyay 2025).
  3. **Recent-tip suppression:** a rule that fired in the last K edits
     with severity ≤ 2 is suppressed unless severity rises (Heer 2019,
     non-disruptiveness).

Rules live as YAML in ``backend/app/services/validation/tip_rules/*.yaml``;
each rule's ``condition`` is evaluated via ``simpleeval`` — never the
stdlib ``eval()`` — so an attacker who edits a YAML file cannot escape
to arbitrary Python execution.

Sources (binding for ``algorithm-auditor``):

  - Sperrle et al. TVCG 2023 — Lotse framework.
  - Ceneda et al. TVCG 2017 — guidance degrees.
  - Ceneda et al. TVCG 2024 — guidance heuristics (non-disruptiveness,
    controllability, visibility).
  - Upadhyay-Lakkaraju-Gajos IUI 2025 — modality-switching motivation.
  - Heer PNAS 2019 — agency-plus-automation, max-3 + dismissibility.
  - Amershi et al. CHI 2019 — Guidelines for Human-AI Interaction.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml
from simpleeval import (
    AttributeDoesNotExist,
    EvalWithCompoundTypes,
    FeatureNotAvailable,
    FunctionNotDefined,
    NameNotDefined,
)

from app.services.events import EventBus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TipRuleError(RuntimeError):
    """Raised when a YAML rule fails schema validation or condition evaluation."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DEGREE_ORIENTING = "orienting"
DEGREE_DIRECTING = "directing"
DEGREE_PRESCRIBING = "prescribing"
_ALLOWED_DEGREES = frozenset({DEGREE_ORIENTING, DEGREE_DIRECTING, DEGREE_PRESCRIBING})

MODALITY_CF = "cf"
MODALITY_FEATURE_IMPORTANCE = "feature_importance"
MODALITY_CONTINGENCY = "contingency"
MODALITY_CONTRASTIVE = "contrastive"
_ALLOWED_MODALITIES = frozenset({
    MODALITY_CF, MODALITY_FEATURE_IMPORTANCE,
    MODALITY_CONTINGENCY, MODALITY_CONTRASTIVE,
})

MIN_SEVERITY = 1
MAX_SEVERITY = 3

DEFAULT_MAX_TIPS_PER_EDIT = 3
DEFAULT_MODALITY_SWITCH_AFTER_N = 5
DEFAULT_RECENT_SUPPRESSION_WINDOW = 3
DEFAULT_RULES_DIR = Path(__file__).resolve().parent / "tip_rules"

# Required YAML keys per rule.
_REQUIRED_RULE_KEYS = frozenset({
    "id", "condition", "degree", "modality", "severity", "message", "paper_ref",
})

# Topic names (subscribers in VAL-014's sidebar / UI-005 palette / UI-013).
TOPIC_LABEL_CHIP = "label_chip"
TOPIC_VALIDATION_METRICS = "validation_metrics"
TOPIC_SESSION_METRICS = "session_metrics"
TOPIC_TIP_EMITTED = "tip_emitted"
TOPIC_TIP_DISMISSED = "tip_dismissed"

# simpleeval safe defaults: arithmetic + comparison + boolean only.
# We deliberately do NOT add functions or attribute access — rule
# conditions should reference ``metrics.<key>`` and ``session.<key>``
# via the namespace dict the engine constructs, plus literals.

_DEGREE_PRIORITY: dict[str, int] = {
    DEGREE_PRESCRIBING: 3, DEGREE_DIRECTING: 2, DEGREE_ORIENTING: 1,
}


# ---------------------------------------------------------------------------
# Tip DTO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tip:
    """A single guidance message rendered from a fired rule."""

    rule_id: str
    degree: str
    modality: str
    severity: int
    message: str
    paper_ref: str
    dismissible: bool = True
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if self.degree not in _ALLOWED_DEGREES:
            raise ValueError(
                f"degree must be one of {sorted(_ALLOWED_DEGREES)}; got {self.degree!r}"
            )
        if self.modality not in _ALLOWED_MODALITIES:
            raise ValueError(
                f"modality must be one of {sorted(_ALLOWED_MODALITIES)}; "
                f"got {self.modality!r}"
            )
        if not MIN_SEVERITY <= self.severity <= MAX_SEVERITY:
            raise ValueError(
                f"severity must be in [{MIN_SEVERITY}, {MAX_SEVERITY}]; "
                f"got {self.severity}"
            )


# ---------------------------------------------------------------------------
# Rule loader
# ---------------------------------------------------------------------------


def _validate_rule_schema(rule: Any, source: Path) -> None:
    """Raise ``TipRuleError`` if ``rule`` does not match the rule schema."""
    if not isinstance(rule, dict):
        raise TipRuleError(f"{source}: rule must be a dict, got {type(rule).__name__}")
    missing = _REQUIRED_RULE_KEYS - rule.keys()
    if missing:
        raise TipRuleError(
            f"{source}: rule {rule.get('id', '<unknown>')!r} missing keys: "
            f"{sorted(missing)}"
        )
    if not isinstance(rule["id"], str) or not rule["id"]:
        raise TipRuleError(f"{source}: rule id must be a non-empty string")
    if not isinstance(rule["condition"], str):
        raise TipRuleError(
            f"{source}: rule {rule['id']!r} condition must be a string"
        )
    if rule["degree"] not in _ALLOWED_DEGREES:
        raise TipRuleError(
            f"{source}: rule {rule['id']!r} degree must be one of "
            f"{sorted(_ALLOWED_DEGREES)}"
        )
    if rule["modality"] not in _ALLOWED_MODALITIES:
        raise TipRuleError(
            f"{source}: rule {rule['id']!r} modality must be one of "
            f"{sorted(_ALLOWED_MODALITIES)}"
        )
    if not isinstance(rule["severity"], int) or not (
        MIN_SEVERITY <= rule["severity"] <= MAX_SEVERITY
    ):
        raise TipRuleError(
            f"{source}: rule {rule['id']!r} severity must be int in "
            f"[{MIN_SEVERITY}, {MAX_SEVERITY}]"
        )
    if not isinstance(rule["message"], str) or not rule["message"]:
        raise TipRuleError(
            f"{source}: rule {rule['id']!r} message must be a non-empty string"
        )
    if not isinstance(rule["paper_ref"], str):
        raise TipRuleError(
            f"{source}: rule {rule['id']!r} paper_ref must be a string"
        )


def load_tip_rules(
    rule_dirs: Iterable[Path | str] | None = None,
) -> list[dict[str, Any]]:
    """Load and validate all YAML rule files under the given directories.

    Each file is parsed as a list-of-rules; if a file contains a single
    mapping, it's wrapped in a list. Rules with duplicate ``id`` values
    raise ``TipRuleError`` so a typo doesn't silently shadow another rule.
    """
    dirs = [Path(d) for d in (rule_dirs or [DEFAULT_RULES_DIR])]
    rules: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for d in dirs:
        if not d.exists():
            logger.debug("load_tip_rules: %s does not exist; skipping.", d)
            continue
        for path in sorted(d.glob("*.yaml")):
            try:
                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                raise TipRuleError(f"{path}: failed to parse YAML: {exc}") from exc
            if payload is None:
                continue
            entries = payload if isinstance(payload, list) else [payload]
            for entry in entries:
                _validate_rule_schema(entry, path)
                if entry["id"] in seen_ids:
                    raise TipRuleError(
                        f"duplicate rule id {entry['id']!r} (second occurrence at {path})"
                    )
                seen_ids.add(entry["id"])
                rules.append(entry)
    return rules


# ---------------------------------------------------------------------------
# safe_eval
# ---------------------------------------------------------------------------


class _Namespace:
    """Lightweight ``dot.access`` wrapper around a dict for simpleeval.

    simpleeval's compound-types evaluator already supports attribute
    access on namespaces; this helper just makes ``metrics.foo`` and
    ``session.bar`` look natural in the YAML conditions.
    """

    def __init__(self, mapping: dict[str, Any]) -> None:
        self._mapping = mapping

    def __getattr__(self, name: str) -> Any:
        try:
            return self._mapping[name]
        except KeyError as exc:
            raise NameNotDefined(name, name) from exc


def safe_eval(expression: str, env: dict[str, Any]) -> Any:
    """Evaluate ``expression`` against ``env`` via simpleeval.

    Returns the expression's value; raises ``TipRuleError`` only on
    parser-level failures. NameError / KeyError on undefined fields are
    *swallowed* and converted to ``False`` so a partially-populated
    metrics payload doesn't blow up the whole evaluation pass — the
    caller can log and skip individual rules.
    """
    wrapped: dict[str, Any] = {}
    for key, val in env.items():
        wrapped[key] = _Namespace(val) if isinstance(val, dict) else val
    evaluator = EvalWithCompoundTypes(names=wrapped)
    try:
        return evaluator.eval(expression)
    except (NameNotDefined, AttributeDoesNotExist, KeyError, AttributeError):
        # Missing field: rule cannot fire; treat as False.
        return False
    except FunctionNotDefined as exc:
        # YAML rule attempted a function call that is not in the
        # (empty) allowlist — this is an authoring error, not a missing
        # field, so surface it loudly.
        raise TipRuleError(
            f"tip-rule condition {expression!r} attempted a disallowed function call: {exc}"
        ) from exc
    except FeatureNotAvailable as exc:
        raise TipRuleError(
            f"unsupported expression in tip-rule condition: {expression!r}: {exc}"
        ) from exc
    except SyntaxError as exc:
        raise TipRuleError(
            f"failed to parse tip-rule condition {expression!r}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class TipEngine:
    """Lotse tip-rules engine.

    Construction:

        engine = TipEngine(rule_dirs=[Path('.../tip_rules')], event_bus=bus)

    auto-loads + validates every YAML rule in the directories. Pass
    ``event_bus`` to subscribe to the three input topics
    (``label_chip``, ``validation_metrics``, ``session_metrics``); each
    subscription forwards the payload through ``evaluate``. Emitted
    tips are published on ``tip_emitted``; dismissals received on
    ``tip_dismissed`` are appended to the audit log (when supplied) and
    re-published for downstream consumers (UI-015).
    """

    def __init__(
        self,
        rule_dirs: Iterable[Path | str] | None = None,
        *,
        event_bus: EventBus | None = None,
        max_tips_per_edit: int = DEFAULT_MAX_TIPS_PER_EDIT,
        modality_switch_after_n: int = DEFAULT_MODALITY_SWITCH_AFTER_N,
        recent_suppression_window: int = DEFAULT_RECENT_SUPPRESSION_WINDOW,
        audit_log_append: Any = None,
    ) -> None:
        if max_tips_per_edit < 1:
            raise ValueError(f"max_tips_per_edit must be ≥ 1; got {max_tips_per_edit}")
        if modality_switch_after_n < 1:
            raise ValueError(
                f"modality_switch_after_n must be ≥ 1; got {modality_switch_after_n}"
            )
        if recent_suppression_window < 0:
            raise ValueError(
                f"recent_suppression_window must be ≥ 0; got {recent_suppression_window}"
            )

        self.rules = load_tip_rules(rule_dirs)
        self.max_tips_per_edit = int(max_tips_per_edit)
        self.modality_switch_after_n = int(modality_switch_after_n)
        self.recent_suppression_window = int(recent_suppression_window)

        self._modality_history: list[str] = []
        self._recent_emissions: list[list[tuple[str, int]]] = []
        # _recent_emissions is a list of "edits"; each edit is a list of
        # (rule_id, severity) emitted on that edit. Up to
        # ``recent_suppression_window`` entries kept.

        self._event_bus = event_bus
        self._audit_log_append = audit_log_append
        self._latest_metrics: dict[str, Any] = {}
        self._latest_session: dict[str, Any] = {}

        if event_bus is not None:
            event_bus.subscribe(TOPIC_LABEL_CHIP, self._on_label_chip)
            event_bus.subscribe(TOPIC_VALIDATION_METRICS, self._on_validation_metrics)
            event_bus.subscribe(TOPIC_SESSION_METRICS, self._on_session_metrics)
            event_bus.subscribe(TOPIC_TIP_DISMISSED, self._on_tip_dismissed)

    # -------- public API ---------------------------------------------------

    def evaluate(
        self,
        metrics: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[Tip]:
        """Evaluate every rule against ``(metrics, session, context)`` and
        return up to ``max_tips_per_edit`` tips, applying modality-switch
        and recent-tip suppression."""
        env: dict[str, Any] = {
            "metrics": dict(metrics or {}),
            "session": dict(session or {}),
        }
        if context:
            env.update(context)

        candidates: list[Tip] = []
        for rule in self.rules:
            try:
                fired = safe_eval(rule["condition"], env)
            except TipRuleError as exc:
                logger.warning("tip rule %r failed to evaluate: %s", rule["id"], exc)
                continue
            if not fired:
                continue
            try:
                tip = self._render(rule, env)
            except KeyError as exc:
                logger.warning(
                    "tip rule %r message references missing placeholder %s; skipping.",
                    rule["id"], exc,
                )
                continue
            candidates.append(tip)

        # Severity desc, then degree desc (prescribing > directing > orienting).
        candidates.sort(
            key=lambda t: (-t.severity, -_DEGREE_PRIORITY[t.degree]),
        )

        # Modality-switch demotion.
        if self._last_n_all_same_modality(MODALITY_CF, self.modality_switch_after_n):
            cf = [t for t in candidates if t.modality == MODALITY_CF]
            others = [t for t in candidates if t.modality != MODALITY_CF]
            candidates = others + cf

        # Recent-tip suppression: a rule that fired in the last K edits
        # with severity ≤ 2 is suppressed *unless* this firing has higher
        # severity than the highest recent firing of the same rule.
        recent_max_sev = self._recent_max_severity_by_rule()
        out: list[Tip] = []
        for c in candidates:
            if len(out) >= self.max_tips_per_edit:
                break
            prev_sev = recent_max_sev.get(c.rule_id)
            if prev_sev is not None and prev_sev <= 2 and c.severity <= prev_sev:
                continue
            out.append(c)

        self._record_emission(out)
        if self._event_bus is not None:
            for tip in out:
                self._event_bus.publish(TOPIC_TIP_EMITTED, tip)
        return out

    def reset(self) -> None:
        """Zero modality history + recent emissions (e.g. on session end)."""
        self._modality_history.clear()
        self._recent_emissions.clear()

    def close(self) -> None:
        """Unsubscribe from the event bus; idempotent."""
        if self._event_bus is None:
            return
        for topic, handler in (
            (TOPIC_LABEL_CHIP, self._on_label_chip),
            (TOPIC_VALIDATION_METRICS, self._on_validation_metrics),
            (TOPIC_SESSION_METRICS, self._on_session_metrics),
            (TOPIC_TIP_DISMISSED, self._on_tip_dismissed),
        ):
            try:
                self._event_bus.unsubscribe(topic, handler)
            except Exception:  # noqa: BLE001
                pass
        self._event_bus = None

    # -------- introspection ------------------------------------------------

    @property
    def n_rules(self) -> int:
        return len(self.rules)

    @property
    def modality_history(self) -> list[str]:
        return list(self._modality_history)

    # -------- rule rendering ----------------------------------------------

    def _render(self, rule: dict[str, Any], env: dict[str, Any]) -> Tip:
        """Substitute ``{placeholder}`` tokens in the rule message with
        values from the env (flattened: ``{ynn_pct}`` reads ``env['ynn_pct']``,
        ``{metrics.ynn}`` is *not* supported on purpose — keep templates
        simple)."""
        flat: dict[str, Any] = {}
        for key, val in env.items():
            if isinstance(val, dict):
                for sub, sub_val in val.items():
                    flat[sub] = sub_val
            else:
                flat[key] = val
        try:
            message = rule["message"].format(**flat) if flat else rule["message"]
        except KeyError:
            # Missing placeholder → render the raw template; the user
            # still sees the gist of the tip and a debug log warns.
            logger.debug(
                "tip rule %r message has unresolved placeholders; rendering raw.",
                rule["id"],
            )
            message = rule["message"]
        return Tip(
            rule_id=rule["id"],
            degree=rule["degree"],
            modality=rule["modality"],
            severity=int(rule["severity"]),
            message=message,
            paper_ref=rule["paper_ref"],
            dismissible=bool(rule.get("dismissible", True)),
        )

    # -------- modality + suppression helpers -------------------------------

    def _last_n_all_same_modality(self, modality: str, n: int) -> bool:
        if len(self._modality_history) < n:
            return False
        return all(m == modality for m in self._modality_history[-n:])

    def _recent_max_severity_by_rule(self) -> dict[str, int]:
        """Walk the recent-emission window and return the highest severity
        each rule_id has fired with, so we can suppress duplicates."""
        out: dict[str, int] = {}
        for emissions in self._recent_emissions[-self.recent_suppression_window:]:
            for rule_id, sev in emissions:
                if rule_id not in out or sev > out[rule_id]:
                    out[rule_id] = sev
        return out

    def _record_emission(self, emitted: list[Tip]) -> None:
        self._recent_emissions.append([(t.rule_id, t.severity) for t in emitted])
        if len(self._recent_emissions) > self.recent_suppression_window:
            del self._recent_emissions[: len(self._recent_emissions) - self.recent_suppression_window]
        for tip in emitted:
            self._modality_history.append(tip.modality)

    # -------- bus handlers -------------------------------------------------

    def _on_label_chip(self, _chip: Any) -> None:
        """A label_chip event is the trigger to evaluate the latest
        per-edit metrics + session state. The chip itself is not used as
        an input — it tells us "the operation finished, run the rules"."""
        self.evaluate(self._latest_metrics, self._latest_session)

    def _on_validation_metrics(self, payload: Any) -> None:
        if isinstance(payload, dict):
            self._latest_metrics = dict(payload)
        elif hasattr(payload, "__dict__"):
            # Allow CFResult-shaped payloads to be normalised into a flat
            # dict of metric values.
            self._latest_metrics = {k: v for k, v in vars(payload).items()
                                     if not k.startswith("_")}
        else:
            warnings.warn(
                f"TipEngine: unexpected validation_metrics payload type "
                f"{type(payload).__name__}; ignoring.",
                RuntimeWarning,
                stacklevel=2,
            )

    def _on_session_metrics(self, payload: Any) -> None:
        if isinstance(payload, dict):
            self._latest_session = dict(payload)
        elif hasattr(payload, "__dict__"):
            self._latest_session = {k: v for k, v in vars(payload).items()
                                     if not k.startswith("_")}
        else:
            warnings.warn(
                f"TipEngine: unexpected session_metrics payload type "
                f"{type(payload).__name__}; ignoring.",
                RuntimeWarning,
                stacklevel=2,
            )

    def _on_tip_dismissed(self, payload: Any) -> None:
        """Audit a dismissed tip (Lisnic 2025 dismissibility + UI-015 trail).

        The payload may be a ``Tip`` (rule_id, severity, etc.) or a dict
        ``{'rule_id': ..., 'dismissed_at': ISO-8601}``. We add a
        ``dismissed_at`` if missing, then forward to the audit-log
        appender — typically ``audit_log.append`` from VAL-010's pattern.
        """
        record: dict[str, Any] = {}
        if isinstance(payload, Tip):
            record = {
                "rule_id": payload.rule_id,
                "severity": payload.severity,
                "modality": payload.modality,
                "dismissed_at": datetime.now(timezone.utc).isoformat(),
            }
        elif isinstance(payload, dict):
            record = dict(payload)
            record.setdefault("dismissed_at", datetime.now(timezone.utc).isoformat())
        else:
            warnings.warn(
                f"TipEngine: unexpected tip_dismissed payload type "
                f"{type(payload).__name__}; ignoring.",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        if self._audit_log_append is not None:
            try:
                self._audit_log_append(record)
            except Exception as exc:  # noqa: BLE001
                logger.warning("TipEngine: audit append failed: %s", exc)
