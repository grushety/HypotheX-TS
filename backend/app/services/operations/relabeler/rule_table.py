"""OP-040 relabeler rule table.

Canonical source for every (old_shape, op_name, param_predicate) → (rule_class, target)
mapping.  Referenced by HypotheX-TS Operation Vocabulary Research §6.

Structure
---------
RULE_TABLE   — dict mapping (old_shape, op_name, predicate) → (rule_class, target | None).
               old_shape='*' matches any shape (used for shape-agnostic Tier-0/1 ops).
               predicate is a string like 'alpha=0' or None.
               Lookup order in relabeler.relabel():
                 1. (old_shape, op, predicate)      — shape-specific + predicate
                 2. ('*',       op, predicate)      — wildcard + predicate
                 3. (old_shape, op, None)           — shape-specific, no predicate
                 4. ('*',       op, None)           — wildcard shape, no predicate
               Step 2 exists so that wildcard predicate rules (e.g. scale alpha=0 → plateau)
               are not shadowed by shape-specific no-predicate rules (e.g. cycle scale → PRESERVED).

_param_predicate(op_params) — maps an op_params dict to the matching predicate string.
                               Returns 'alpha=0' when op_params['alpha'] == 0.0.
                               Returns None otherwise.

UnknownRelabelRule — raised by relabeler.relabel() when no rule is found.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class UnknownRelabelRule(ValueError):
    """Raised when no rule exists for (old_shape, operation) in RULE_TABLE."""


# ---------------------------------------------------------------------------
# Param predicate
# ---------------------------------------------------------------------------


def _param_predicate(op_params: dict[str, Any] | None) -> str | None:
    """Map op_params to a predicate string for RULE_TABLE lookup.

    Currently the only discriminating predicate is 'alpha=0', which fires
    when op_params contains alpha == 0.0.  All other param combinations
    fall through to None (the generic rule for that operation).

    Args:
        op_params: Dict of operation parameters, or None.

    Returns:
        'alpha=0' if op_params['alpha'] == 0.0, else None.
    """
    if not op_params:
        return None
    alpha = op_params.get("alpha")
    if alpha is not None and float(alpha) == 0.0:
        return "alpha=0"
    return None


# ---------------------------------------------------------------------------
# Rule table
# ---------------------------------------------------------------------------

# (old_shape, op_name, param_predicate) → (rule_class, target_shape | None)
#
# Rule classes:
#   PRESERVED              — new_shape = old_shape, confidence = 1.0
#   DETERMINISTIC          — new_shape = target_shape, confidence = 1.0
#   RECLASSIFY_VIA_SEGMENTER — invokes SEG-008 classifier on edited_series
#
# Source: HypotheX-TS Operation Vocabulary Research §6.

RULE_TABLE: dict[tuple[str, str, str | None], tuple[str, str | None]] = {
    # ------------------------------------------------------------------
    # Tier-0 structural ops (shape-agnostic)
    # ------------------------------------------------------------------
    ("*", "edit_boundary", None): ("PRESERVED", None),
    ("*", "split", None): ("RECLASSIFY_VIA_SEGMENTER", None),
    ("*", "merge", None): ("RECLASSIFY_VIA_SEGMENTER", None),

    # ------------------------------------------------------------------
    # Tier-1 amplitude atoms (shape-agnostic)
    # ------------------------------------------------------------------
    ("*", "scale", "alpha=0"): ("DETERMINISTIC", "plateau"),
    ("*", "scale", None): ("PRESERVED", None),
    ("*", "offset", None): ("PRESERVED", None),
    ("*", "mute_zero", None): ("DETERMINISTIC", "plateau"),

    # ------------------------------------------------------------------
    # Tier-1 time atoms (shape-agnostic)
    # ------------------------------------------------------------------
    ("*", "time_shift", None): ("PRESERVED", None),
    ("*", "reverse_time", None): ("PRESERVED", None),
    ("*", "resample", None): ("PRESERVED", None),

    # ------------------------------------------------------------------
    # Tier-1 stochastic atoms (shape-agnostic)
    # ------------------------------------------------------------------
    ("*", "suppress", None): ("RECLASSIFY_VIA_SEGMENTER", None),
    ("*", "add_uncertainty", None): ("PRESERVED", None),

    # ------------------------------------------------------------------
    # Tier-1 library atom (shape-agnostic)
    # ------------------------------------------------------------------
    ("*", "replace_from_library", None): ("RECLASSIFY_VIA_SEGMENTER", None),

    # ------------------------------------------------------------------
    # Tier-2 plateau
    # ------------------------------------------------------------------
    ("plateau", "raise_lower", None): ("PRESERVED", None),
    ("plateau", "invert", None): ("PRESERVED", None),
    ("plateau", "replace_with_trend", None): ("DETERMINISTIC", "trend"),
    ("plateau", "replace_with_cycle", None): ("DETERMINISTIC", "cycle"),
    ("plateau", "tilt_detrend", None): ("PRESERVED", None),

    # ------------------------------------------------------------------
    # Tier-2 trend
    # ------------------------------------------------------------------
    ("trend", "flatten", None): ("DETERMINISTIC", "plateau"),
    ("trend", "reverse_direction", None): ("PRESERVED", None),
    ("trend", "change_slope", "alpha=0"): ("DETERMINISTIC", "plateau"),
    ("trend", "change_slope", None): ("PRESERVED", None),
    ("trend", "linearise", None): ("PRESERVED", None),
    ("trend", "extrapolate", None): ("PRESERVED", None),
    ("trend", "add_acceleration", None): ("PRESERVED", None),

    # ------------------------------------------------------------------
    # Tier-2 step
    # ------------------------------------------------------------------
    ("step", "de_jump", None): ("RECLASSIFY_VIA_SEGMENTER", None),
    ("step", "invert_sign", None): ("PRESERVED", None),
    ("step", "scale_magnitude", "alpha=0"): ("DETERMINISTIC", "plateau"),
    ("step", "scale_magnitude", None): ("PRESERVED", None),
    ("step", "shift_in_time", None): ("PRESERVED", None),
    ("step", "convert_to_ramp", None): ("DETERMINISTIC", "transient"),
    ("step", "duplicate", None): ("RECLASSIFY_VIA_SEGMENTER", None),

    # ------------------------------------------------------------------
    # Tier-2 spike
    # ------------------------------------------------------------------
    ("spike", "remove", None): ("RECLASSIFY_VIA_SEGMENTER", None),
    ("spike", "clip_cap", None): ("PRESERVED", None),
    ("spike", "amplify", None): ("PRESERVED", None),
    ("spike", "smear_to_transient", None): ("DETERMINISTIC", "transient"),
    ("spike", "duplicate", None): ("RECLASSIFY_VIA_SEGMENTER", None),
    ("spike", "shift_time", None): ("PRESERVED", None),

    # ------------------------------------------------------------------
    # Tier-2 cycle
    # ------------------------------------------------------------------
    ("cycle", "deseasonalise_remove", None): ("RECLASSIFY_VIA_SEGMENTER", None),
    ("cycle", "amplify_amplitude", "alpha=0"): ("DETERMINISTIC", "plateau"),
    ("cycle", "amplify_amplitude", None): ("PRESERVED", None),
    ("cycle", "dampen_amplitude", None): ("PRESERVED", None),
    ("cycle", "phase_shift", None): ("PRESERVED", None),
    ("cycle", "change_period", None): ("PRESERVED", None),
    ("cycle", "change_harmonic_content", None): ("PRESERVED", None),
    ("cycle", "replace_with_flat", None): ("DETERMINISTIC", "plateau"),

    # ------------------------------------------------------------------
    # Tier-2 transient
    # ------------------------------------------------------------------
    ("transient", "remove", None): ("RECLASSIFY_VIA_SEGMENTER", None),
    ("transient", "amplify", None): ("PRESERVED", None),
    ("transient", "dampen", "alpha=0"): ("DETERMINISTIC", "plateau"),
    ("transient", "dampen", None): ("PRESERVED", None),
    ("transient", "shift_time", None): ("PRESERVED", None),
    ("transient", "change_duration", None): ("PRESERVED", None),
    ("transient", "change_decay_constant", None): ("PRESERVED", None),
    ("transient", "replace_shape", None): ("PRESERVED", None),
    ("transient", "duplicate", None): ("PRESERVED", None),
    ("transient", "convert_to_step", None): ("DETERMINISTIC", "step"),

    # ------------------------------------------------------------------
    # Tier-2 noise
    # ------------------------------------------------------------------
    ("noise", "suppress_denoise", None): ("RECLASSIFY_VIA_SEGMENTER", None),
    ("noise", "amplify", None): ("PRESERVED", None),
    ("noise", "change_color", None): ("PRESERVED", None),
    ("noise", "inject_synthetic", None): ("PRESERVED", None),
    ("noise", "whiten", None): ("PRESERVED", None),
}
