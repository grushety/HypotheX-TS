"""DecompositionBlob — central data structure for segment decompositions (SEG-019).

Every fitter (SEG-013..018) emits a DecompositionBlob.  Every Tier-2 op
(OP-020..026) consumes one through blob.components[key] and
blob.coefficients[name].  Adding a new fitter requires no changes here.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

import numpy as np

VALID_METHODS: frozenset[str] = frozenset({
    "ETM", "STL", "MSTL", "BFAST", "LandTrendr",
    "Eckhardt", "GrAtSiD", "Constant", "Delta", "NoiseModel",
})


# ---------------------------------------------------------------------------
# Array serialisation helpers
# ---------------------------------------------------------------------------


def _serialize_value(v: Any) -> Any:
    """Recursively encode a value; numpy arrays become tagged base64 dicts."""
    if isinstance(v, np.ndarray):
        return {
            "__ndarray__": True,
            "dtype": str(v.dtype),
            "shape": list(v.shape),
            "data_b64": base64.b64encode(v.tobytes()).decode("ascii"),
        }
    if isinstance(v, dict):
        return {k: _serialize_value(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_serialize_value(item) for item in v]
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


def _deserialize_value(v: Any) -> Any:
    """Recursively decode a value; tagged base64 dicts become numpy arrays."""
    if isinstance(v, dict) and v.get("__ndarray__"):
        raw = base64.b64decode(v["data_b64"])
        arr = np.frombuffer(raw, dtype=np.dtype(v["dtype"])).copy()
        return arr.reshape(v["shape"])
    if isinstance(v, dict):
        return {k: _deserialize_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_deserialize_value(item) for item in v]
    return v


# ---------------------------------------------------------------------------
# DecompositionBlob
# ---------------------------------------------------------------------------


@dataclass
class DecompositionBlob:
    """Additive decomposition of a single time-series segment.

    Attributes:
        method:       Fitter method name (e.g. 'ETM', 'STL', 'Constant').
        components:   Named additive component arrays (e.g. 'trend',
                      'seasonal', 'residual').  sum(components.values())
                      should equal the original segment within float tolerance.
        coefficients: Method-specific named parameters (scalars, arrays,
                      or nested structures).
        residual:     Optional dedicated residual array.  If None, residual
                      is expected inside components['residual'] (if present).
        fit_metadata: Diagnostic dict with at least:
                      rmse, rank, n_params, convergence (bool), version (str).
    """

    method: str
    components: dict[str, np.ndarray] = field(default_factory=dict)
    coefficients: dict[str, Any] = field(default_factory=dict)
    residual: np.ndarray | None = None
    fit_metadata: dict = field(default_factory=dict)

    def reassemble(self) -> np.ndarray:
        """Return the sum of all named components."""
        arrays = list(self.components.values())
        if not arrays:
            raise ValueError("DecompositionBlob has no components to reassemble.")
        result = arrays[0].copy()
        for arr in arrays[1:]:
            result = result + arr
        return result

    def with_coefficients(
        self,
        coefficients: dict[str, Any],
        *,
        components: dict[str, np.ndarray] | None = None,
    ) -> "DecompositionBlob":
        """Return a deep copy with updated ``coefficients`` (and optionally
        ``components``).

        Used by VAL-032 (CS in coefficient space): the validator perturbs
        coefficients, then a method-specific reconstructor produces fresh
        components consistent with the new values, and ``with_coefficients``
        bundles both into an immutable new blob.

        When ``components=None`` the original components are deep-copied
        unchanged — useful when the caller plans to call ``reassemble()``
        on the original signal regardless of the coefficient change. The
        common path for VAL-032 is to pass both arguments together so that
        ``reassemble()`` reflects the new coefficients.
        """
        import copy as _copy
        return DecompositionBlob(
            method=self.method,
            components=_copy.deepcopy(components) if components is not None else _copy.deepcopy(self.components),
            coefficients=_copy.deepcopy(coefficients),
            residual=self.residual.copy() if self.residual is not None else None,
            fit_metadata=_copy.deepcopy(self.fit_metadata),
        )

    def to_json(self) -> dict:
        """Serialize to a JSON-compatible dict.

        numpy arrays are base64-encoded so that from_json(to_json(blob))
        is bit-identical (not just np.allclose).
        """
        return {
            "method": self.method,
            "components": _serialize_value(self.components),
            "coefficients": _serialize_value(self.coefficients),
            "residual": _serialize_value(self.residual),
            "fit_metadata": _serialize_value(self.fit_metadata),
        }

    @classmethod
    def from_json(cls, d: dict) -> "DecompositionBlob":
        """Reconstruct a DecompositionBlob from a JSON-compatible dict."""
        return cls(
            method=d["method"],
            components=_deserialize_value(d.get("components", {})),
            coefficients=_deserialize_value(d.get("coefficients", {})),
            residual=_deserialize_value(d.get("residual")),
            fit_metadata=_deserialize_value(d.get("fit_metadata", {})),
        )
