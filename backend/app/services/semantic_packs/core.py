"""Core types, registry, loader, predicate evaluator, and matcher for the
semantic-pack subsystem (SEG-021).

References
----------
HypotheX-TS — *Formal Definitions* §2.3 (compositional semantic-label
definition);  *Implementation Plan* §8.4 (user-defined labels shadow pack
labels per project).
"""
from __future__ import annotations

import ast
import builtins
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shape vocabulary (must mirror SEG-008 ``_SHAPE_LABELS``)
# ---------------------------------------------------------------------------


VALID_SHAPES: frozenset[str] = frozenset(
    {"plateau", "trend", "step", "spike", "cycle", "transient", "noise"}
)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


DetectorFn = Callable[[np.ndarray, str, dict[str, Any]], tuple[bool, float]]


@dataclass(frozen=True)
class SemanticLabel:
    """One named entry in a semantic pack.

    Attributes:
        name:               Label name as seen by the user (e.g. ``baseflow``).
        shape_primitive:    Required shape primitive — must be in
                            :data:`VALID_SHAPES`.  Filters the candidate
                            segments before the detector even runs.
        detector_name:      Key into :data:`DETECTOR_REGISTRY`.
        detector_params:    Extra parameters merged into the detector's
                            ``context`` argument (e.g. ``{'BFImax': 0.8}``).
        context_predicate:  Optional Python expression evaluated against the
                            detector-augmented context (e.g.
                            ``"Q_mean < BFImax * Q_median"``).  Empty string
                            means no additional predicate.
    """

    name: str
    shape_primitive: str
    detector_name: str
    detector_params: dict[str, Any] = field(default_factory=dict)
    context_predicate: str = ""


@dataclass(frozen=True)
class SemanticPack:
    """A named, versioned bundle of :class:`SemanticLabel` entries."""

    name: str
    version: str
    semantic_labels: dict[str, SemanticLabel] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Detector registry
# ---------------------------------------------------------------------------


DETECTOR_REGISTRY: dict[str, DetectorFn] = {}


def register_detector(name: str) -> Callable[[DetectorFn], DetectorFn]:
    """Decorator that registers a detector callable in :data:`DETECTOR_REGISTRY`.

    Usage::

        @register_detector("eckhardt_baseflow")
        def baseflow(X_seg, shape_label, context):
            ...
            return matched, confidence
    """

    def decorator(fn: DetectorFn) -> DetectorFn:
        if name in DETECTOR_REGISTRY and DETECTOR_REGISTRY[name] is not fn:
            logger.warning(
                "register_detector: re-registering %r — previous callable replaced.",
                name,
            )
        DETECTOR_REGISTRY[name] = fn
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Restricted predicate evaluator (Python ``eval`` with AST whitelist)
# ---------------------------------------------------------------------------


_ALLOWED_AST_NODES: tuple[type, ...] = (
    ast.Expression,
    ast.BoolOp,
    ast.UnaryOp,
    ast.BinOp,
    ast.Compare,
    ast.Constant,
    ast.Name,
    ast.Call,
    ast.List,
    ast.Tuple,
    ast.And,
    ast.Or,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.FloorDiv,
    ast.Lt,
    ast.LtE,
    ast.Eq,
    ast.NotEq,
    ast.GtE,
    ast.Gt,
    ast.In,
    ast.NotIn,
    ast.Load,
)


_ALLOWED_BUILTINS: dict[str, Callable[..., Any]] = {
    name: getattr(builtins, name)
    for name in ("abs", "max", "min", "len", "all", "any", "round", "sum")
}


_STRICT_DISALLOWED_NODES: tuple[type, ...] = (ast.Pow,)


def _validate_predicate_ast(tree: ast.AST, *, strict: bool = False) -> None:
    """Reject any AST node outside the safe whitelist; reject calls to
    anything other than the small whitelisted-builtins set.

    When ``strict=True`` the additional ``_STRICT_DISALLOWED_NODES`` tuple
    is rejected — used for user-uploaded packs (UI-014) where ``2 ** 10 ** 8``
    would otherwise let an attacker freeze the worker.
    """
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST_NODES):
            raise ValueError(
                f"Predicate uses disallowed syntax: {type(node).__name__}"
            )
        if strict and isinstance(node, _STRICT_DISALLOWED_NODES):
            raise ValueError(
                "Predicate uses disallowed operator '**' in strict mode "
                "(uploaded packs cannot use exponentiation)."
            )
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError(
                    "Predicate calls must reference a name directly "
                    "(no attribute access, no nested calls)."
                )
            if node.func.id not in _ALLOWED_BUILTINS:
                raise ValueError(
                    f"Predicate calls disallowed function {node.func.id!r}; "
                    f"allowed: {sorted(_ALLOWED_BUILTINS)}."
                )


def validate_predicate_strict(predicate: str) -> None:
    """Validate an uploaded-pack predicate against the strict whitelist.

    Raises :class:`ValueError` on any disallowed syntax, including the
    exponentiation operator ``**``. Empty predicates pass.
    """
    if not predicate or not predicate.strip():
        return
    tree = ast.parse(predicate, mode="eval")
    _validate_predicate_ast(tree, strict=True)


def evaluate_predicate(predicate: str, context: dict[str, Any]) -> bool:
    """Evaluate a context predicate string against a namespace.

    The predicate is parsed with :mod:`ast` and validated against a small
    whitelist of nodes (boolean ops, comparisons, arithmetic, calls to a
    fixed set of safe builtins).  Names resolve to keys in ``context``.

    An empty / whitespace-only predicate is treated as "always matches"
    and returns ``True``.

    **Trust model**: pack YAML files are *author-controlled* (shipped with
    the codebase), so the AST guard is defence-in-depth, not the primary
    boundary.  In particular, the evaluator does **not** bound the CPU /
    memory of arithmetic operations — a malicious predicate such as
    ``2 ** 10 ** 8`` would happily run.

    UI-014 widened the trust boundary to accept user-uploaded packs over
    HTTP. The mitigation lives at the route layer rather than in this
    evaluator: see :func:`validate_predicate_strict` (rejects ``ast.Pow``)
    plus the body-size cap in ``app.routes.semantic_packs._load_custom_pack``.
    Built-in pack predicates continue to flow through this non-strict path
    unchanged.

    Args:
        predicate: Python boolean expression as a string.
        context:   Namespace for name lookups.

    Returns:
        ``bool(eval(predicate, …))``.

    Raises:
        ValueError:  If the predicate uses disallowed syntax.
        NameError:   If the predicate references a name not in ``context``.
    """
    if not predicate or not predicate.strip():
        return True
    tree = ast.parse(predicate, mode="eval")
    _validate_predicate_ast(tree)
    safe_globals = {"__builtins__": {}}
    safe_locals = {**_ALLOWED_BUILTINS, **context}
    return bool(eval(  # noqa: S307 — restricted by AST validation above
        compile(tree, filename="<predicate>", mode="eval"),
        safe_globals,
        safe_locals,
    ))


# ---------------------------------------------------------------------------
# YAML pack loader
# ---------------------------------------------------------------------------


_PACK_DIR = pathlib.Path(__file__).parent


def load_pack(name: str, pack_dir: pathlib.Path | None = None) -> SemanticPack:
    """Load a semantic pack from ``{pack_dir}/{name}.yaml``.

    The loader validates that

    1. Every ``shape_primitive`` is in :data:`VALID_SHAPES`.
    2. Every named ``detector`` resolves in :data:`DETECTOR_REGISTRY`.

    Args:
        name:     Pack name (file stem).  Loader appends ``.yaml``.
        pack_dir: Optional override for the directory.  Defaults to the
                  semantic-packs package directory.

    Returns:
        :class:`SemanticPack`.

    Raises:
        FileNotFoundError: Pack YAML file is missing.
        ValueError:        Schema invalid — unknown shape, unknown detector,
                           or duplicate label name.
    """
    pdir = pack_dir if pack_dir is not None else _PACK_DIR
    path = pdir / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"load_pack: pack file not found at {path}. "
            f"Available packs: {sorted(p.stem for p in pdir.glob('*.yaml'))}."
        )

    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    pack_name = str(raw.get("name", name))
    pack_version = str(raw.get("version", "0.0"))
    raw_labels = raw.get("semantic_labels", {}) or {}

    labels: dict[str, SemanticLabel] = {}
    for label_name, body in raw_labels.items():
        if label_name in labels:
            raise ValueError(
                f"load_pack {name!r}: duplicate label name {label_name!r}."
            )
        body = body or {}
        shape = str(body.get("shape_primitive", ""))
        if shape not in VALID_SHAPES:
            raise ValueError(
                f"load_pack {name!r}: label {label_name!r} has unknown "
                f"shape_primitive {shape!r}.  Valid: {sorted(VALID_SHAPES)}."
            )
        detector_name = str(body.get("detector", ""))
        if detector_name not in DETECTOR_REGISTRY:
            raise ValueError(
                f"load_pack {name!r}: label {label_name!r} references "
                f"unknown detector {detector_name!r}.  Registered: "
                f"{sorted(DETECTOR_REGISTRY)}."
            )
        labels[label_name] = SemanticLabel(
            name=label_name,
            shape_primitive=shape,
            detector_name=detector_name,
            detector_params=dict(body.get("detector_params", {}) or {}),
            context_predicate=str(body.get("context_predicate", "") or ""),
        )

    return SemanticPack(name=pack_name, version=pack_version, semantic_labels=labels)


# ---------------------------------------------------------------------------
# Match a single label / a whole pack against a segment
# ---------------------------------------------------------------------------


def match_semantic_label(
    label: SemanticLabel,
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any] | None = None,
) -> tuple[bool, float]:
    """Apply one :class:`SemanticLabel` to a segment.

    Pipeline:
      1. Reject if ``shape_label != label.shape_primitive``.
      2. Build the detector context as ``{**context, **label.detector_params}``.
      3. Run the detector — it may mutate the context dict to add metrics.
      4. If the detector reports ``matched=False``, stop here.
      5. Evaluate ``label.context_predicate`` against the augmented context;
         if False, return non-match with the predicate's failure recorded.
      6. Return ``(True, detector_confidence)``.

    Args:
        label:        The :class:`SemanticLabel` to match.
        X_seg:        Segment values, shape (n,).
        shape_label:  The shape primitive assigned by SEG-008.
        context:      Caller-supplied context (full-series stats, neighbour
                      flags, ``dt``, ``Q_median``…).  Mutated by the detector.

    Returns:
        ``(matched, confidence)``.  ``confidence`` is 0.0 on non-match.
    """
    if shape_label != label.shape_primitive:
        return False, 0.0
    detector = DETECTOR_REGISTRY.get(label.detector_name)
    if detector is None:
        logger.warning(
            "match_semantic_label: detector %r not registered; "
            "label %r returns no-match.",
            label.detector_name,
            label.name,
        )
        return False, 0.0

    ctx: dict[str, Any] = dict(context or {})
    for key, value in label.detector_params.items():
        ctx.setdefault(key, value)

    try:
        matched, confidence = detector(X_seg, shape_label, ctx)
    except Exception as exc:  # noqa: BLE001 — never let a detector crash the matcher
        logger.warning(
            "Detector %r raised %s on label %r: %s",
            label.detector_name,
            type(exc).__name__,
            label.name,
            exc,
        )
        return False, 0.0

    if not matched:
        return False, 0.0

    if label.context_predicate:
        try:
            if not evaluate_predicate(label.context_predicate, ctx):
                return False, 0.0
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Predicate %r failed on label %r: %s",
                label.context_predicate,
                label.name,
                exc,
            )
            return False, 0.0

    return True, float(confidence)


def label_segment(
    pack: SemanticPack,
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any] | None = None,
) -> list[tuple[str, float]]:
    """Match every label in ``pack`` against ``X_seg``.

    Returns a list of ``(label_name, confidence)`` for every label that
    matched, sorted by descending confidence.  Each label receives its
    *own* shallow copy of ``context`` so that detector mutations do not
    leak between labels.
    """
    out: list[tuple[str, float]] = []
    for label_name, label in pack.semantic_labels.items():
        matched, conf = match_semantic_label(label, X_seg, shape_label, context)
        if matched:
            out.append((label_name, conf))
    out.sort(key=lambda item: -item[1])
    return out
