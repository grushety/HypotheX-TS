"""Shape-driven fitter dispatcher (SEG-019).

Maintains a module-level FITTER_REGISTRY populated by @register_fitter
decorators.  dispatch_fitter resolves a (shape_label, domain_hint) pair
to the correct registered callable.

Plugin extensibility: to add a new fitter, create a file in
app/services/decomposition/fitters/ and decorate its entry function with
@register_fitter('MethodName').  No changes to this file are needed.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Callable

FITTER_REGISTRY: dict[str, Callable[..., Any]] = {}

_fitters_loaded: bool = False

# ---------------------------------------------------------------------------
# Dispatch table (shape_label, domain_hint) -> method name
# ---------------------------------------------------------------------------

_DISPATCH_TABLE: dict[tuple[str, str | None], str] = {
    ("plateau",   None):             "Constant",
    ("trend",     "remote-sensing"): "LandTrendr",
    ("trend",     None):             "ETM",
    ("step",      None):             "ETM",
    ("spike",     None):             "Delta",
    ("cycle",     "multi-period"):   "MSTL",
    ("cycle",     None):             "STL",
    ("transient", "seismo-geodesy"): "GrAtSiD",
    ("transient", None):             "ETM",
    ("noise",     None):             "NoiseModel",
}


def register_fitter(method_name: str) -> Callable:
    """Class/function decorator that registers a fitter in FITTER_REGISTRY.

    Usage::

        @register_fitter("ETM")
        def fit_etm(X: np.ndarray, **kwargs) -> DecompositionBlob:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        FITTER_REGISTRY[method_name] = fn
        return fn
    return decorator


def _ensure_fitters_loaded() -> None:
    """Auto-import every module in the fitters/ sub-package.

    This triggers @register_fitter decorators without the caller needing
    to import individual fitter modules.  Runs at most once per process.
    """
    global _fitters_loaded
    if _fitters_loaded:
        return
    _fitters_loaded = True

    fitters_dir = Path(__file__).parent / "fitters"
    if not fitters_dir.is_dir():
        return

    for module_info in pkgutil.iter_modules([str(fitters_dir)]):
        importlib.import_module(
            f"app.services.decomposition.fitters.{module_info.name}"
        )


def dispatch_fitter(
    shape_label: str,
    domain_hint: str | None = None,
) -> Callable[..., Any]:
    """Return the registered fitter callable for (shape_label, domain_hint).

    The domain-specific entry is tried first; if not found, the generic
    (shape_label, None) entry is used.

    Args:
        shape_label:  One of the 7 shape-vocabulary labels.
        domain_hint:  Optional domain specialisation string (e.g.
                      'remote-sensing', 'seismo-geodesy', 'hydrology').

    Returns:
        The registered fitter callable.

    Raises:
        KeyError:     shape_label not in the dispatch table.
        RuntimeError: No fitter registered for the resolved method name.
    """
    _ensure_fitters_loaded()

    key: tuple[str, str | None] = (
        (shape_label, domain_hint)
        if (shape_label, domain_hint) in _DISPATCH_TABLE
        else (shape_label, None)
    )

    if key not in _DISPATCH_TABLE:
        known = sorted({s for s, _ in _DISPATCH_TABLE})
        raise KeyError(
            f"Unknown shape label {shape_label!r}. "
            f"Known shape labels: {known}. "
            "Ensure the label matches the 7-primitive shape vocabulary."
        )

    method = _DISPATCH_TABLE[key]
    fitter = FITTER_REGISTRY.get(method)
    if fitter is None:
        raise RuntimeError(
            f"No fitter registered for method {method!r}. "
            f"Ensure the corresponding fitter module is present in "
            f"app/services/decomposition/fitters/ and decorated with "
            f"@register_fitter({method!r})."
        )
    return fitter
