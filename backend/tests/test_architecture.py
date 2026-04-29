"""Architecture-enforcement tests (OP-050 AC).

Verifies that Tier-2 op implementations never mutate the raw input signal
*in-place* via augmented indexed assignment (e.g. ``X[i] += delta``).

The checks are intentionally specific to the class of bugs they guard against:

1. ``test_no_raw_signal_inplace_mutation`` — scans Tier-2 files for augmented
   array-element assignment (``+= -=  *=  /=``) on ANY variable.  Simple ``=``
   on a local copy (e.g. ``arr[spikes] = fitted[spikes]``) is the correct
   pattern and is intentionally NOT flagged.

2. ``test_tier2_ops_honour_copy_contract`` — each Tier-2 op file must contain
   at least one of: ``deepcopy`` (blob-based ops), ``reassemble`` (blob output),
   or ``.copy()`` (raw-signal ops that work on an explicit copy of the input).

3. ``test_cf_coordinator_edit_space_is_coefficient`` — the coordinator invariant
   that ``CFResult.edit_space`` is always the literal string ``'coefficient'``.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

TIER2_DIR = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "services"
    / "operations"
    / "tier2"
)

# Augmented inplace assignment on an indexed variable:
#   matches:   X[i] +=  X_seg[0:5] -=  values[k] *=
#   does NOT match:  arr[spikes] = ..., blob.components[k] = ...
_AUGMENTED_INPLACE = re.compile(
    r"""
    (?<!\.)      # not preceded by dot (exclude obj.attr[k] patterns)
    \b\w+        # variable name
    \s*\[        # open bracket
    [^\]]*       # any content
    \]\s*        # close bracket
    [+\-*\/]=    # augmented assignment operator  (+= -= *= /=)
    """,
    re.VERBOSE,
)


def _augmented_inplace_violations(path: Path) -> list[tuple[int, str]]:
    violations = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if _AUGMENTED_INPLACE.search(stripped):
            violations.append((lineno, line.rstrip()))
    return violations


def test_no_raw_signal_inplace_mutation():
    """No Tier-2 op uses augmented inplace mutation (+=, -=, etc.) on array elements."""
    assert TIER2_DIR.is_dir(), f"tier2 directory not found: {TIER2_DIR}"
    all_violations: list[str] = []
    for py_file in sorted(TIER2_DIR.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        for lineno, line in _augmented_inplace_violations(py_file):
            all_violations.append(f"{py_file.name}:{lineno}: {line}")
    assert not all_violations, (
        "Tier-2 ops must not use augmented in-place array assignment.\n"
        "Use an explicit copy (arr = X.copy()) and assign to the copy.\n"
        + "\n".join(all_violations)
    )


def test_tier2_ops_honour_copy_contract():
    """Each Tier-2 op file uses deepcopy, reassemble, or .copy() to honour the immutability contract.

    - blob-based ops (plateau, trend, step, cycle, transient, noise): deepcopy + reassemble
    - raw-signal ops (spike): explicit .copy() of the input array
    """
    assert TIER2_DIR.is_dir()
    _contract = re.compile(r"deepcopy|reassemble|\.copy\(\)")
    for py_file in sorted(TIER2_DIR.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        assert _contract.search(source), (
            f"{py_file.name} contains no deepcopy, reassemble, or .copy() call — "
            "Tier-2 ops must either deepcopy a blob before mutating, call "
            "blob.reassemble() to produce output values, or .copy() the raw input."
        )


def test_cf_coordinator_edit_space_is_coefficient():
    """CFResult.edit_space is always 'coefficient', never 'raw_signal_gradient'."""
    from app.models.decomposition import DecompositionBlob
    from app.services.events import AuditLog, EventBus
    from app.services.operations.cf_coordinator import synthesize_counterfactual
    from app.services.operations.tier2.plateau import raise_lower

    level = 10.0
    n = 30
    blob = DecompositionBlob(
        method="Constant",
        components={"trend": np.full(n, level)},
        coefficients={"level": level},
    )

    result = synthesize_counterfactual(
        segment_id="seg-arch",
        segment_label="plateau",
        blob=blob,
        op_tier2=raise_lower,
        op_params={"delta": 3.0},
        event_bus=EventBus(),
        audit_log=AuditLog(),
    )
    assert result.edit_space == "coefficient", (
        f"edit_space must be 'coefficient', got {result.edit_space!r}. "
        "CF synthesis must never use raw-signal gradient edits."
    )
    assert result.method == "decomposition_first"
