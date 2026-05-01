"""Semantic-layer domain packs (SEG-021).

A *semantic pack* attaches domain-meaningful labels (e.g. ``baseflow``,
``stormflow``, ``ENSO_phase``) to shape-primitive segments produced by the
SEG-008 classifier.  Each label is defined compositionally as

    (shape_primitive, detector, context_predicate)

per *HypotheX-TS — Formal Definitions* §2.3.  Packs are authored as YAML
files in this directory; the loader validates them at import time.

Public surface
--------------
- :class:`SemanticPack`, :class:`SemanticLabel` — frozen dataclasses
- :func:`load_pack` — read a YAML pack by name
- :func:`register_detector` — decorator for detector callables
- :data:`DETECTOR_REGISTRY` — populated by ``register_detector``
- :func:`match_semantic_label` — apply a single label to a segment
- :func:`evaluate_predicate` — restricted-AST predicate evaluator
- :func:`label_segment` — match every label in a pack against a segment

Detector contract
-----------------
``detector(X_seg, shape_label, context) -> (matched: bool, confidence: float)``

Detectors *mutate* ``context`` in place to add the metrics used by their
``context_predicate`` (e.g. ``Q_mean``, ``peak_Q``, ``slope``).  The matcher
then evaluates the predicate against the augmented ``context``.

User-defined labels (added at runtime per project / session) are expected
to *shadow* pack labels with the same name; this loader returns the pack
verbatim and leaves shadowing to the caller (see *Implementation Plan* §8.4).
"""
from __future__ import annotations

from .core import (
    DETECTOR_REGISTRY,
    SemanticLabel,
    SemanticPack,
    evaluate_predicate,
    label_segment,
    load_pack,
    match_semantic_label,
    register_detector,
)

# Trigger detector registration on first import of the package.
from . import detectors_hydrology  # noqa: F401, E402
from . import detectors_remote_sensing  # noqa: F401, E402
from . import detectors_seismo_geodesy  # noqa: F401, E402

__all__ = [
    "DETECTOR_REGISTRY",
    "SemanticLabel",
    "SemanticPack",
    "evaluate_predicate",
    "label_segment",
    "load_pack",
    "match_semantic_label",
    "register_detector",
]
