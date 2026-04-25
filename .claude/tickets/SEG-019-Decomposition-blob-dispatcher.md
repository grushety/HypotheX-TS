# SEG-019 — Decomposition blob schema + method dispatcher

**Status:** [x] Done
**Depends on:** — (foundational)

---

## Goal

Define the `DecompositionBlob` data structure and a shape-driven dispatcher that routes each segment to the appropriate fitter (SEG-013..018). The blob is the central data structure that makes the **decomposition-first CF architecture** possible: every Tier-2 op is a coefficient-level edit on a blob.

**Why:** Without a unified schema, each fitter would emit its own proprietary representation, forcing every Tier-2 op to know about every fitter. With a common `DecompositionBlob` contract, OP-020..026 operate on `blob.components[key]` and `blob.coefficients[name]` uniformly, and new fitters (e.g. HANTS, CCDC) can be added without touching op code.

**How it fits:** Foundational. All fitters (SEG-013..018) emit `DecompositionBlob`. All Tier-2 ops (OP-020..026) consume it. Storage: per-segment SQLite JSON column (default per [[HypotheX-TS - Implementation Plan]] §8). SEG-020 (few-shot update) does not touch the blob.

---

## Paper references

Design ticket; no paper reference. Schema semantics follow [[_project HypotheX-TS/HypotheX-TS - Formal Definitions]] §6.

---

## Schema sketch

```python
@dataclass(frozen=False)
class DecompositionBlob:
    method: Literal['ETM', 'STL', 'MSTL', 'BFAST', 'LandTrendr',
                    'Eckhardt', 'GrAtSiD', 'Constant', 'Delta',
                    'NoiseModel']
    components: dict[str, np.ndarray]        # named additive components
    coefficients: dict[str, Any]             # method-specific named params
    residual: np.ndarray | None              # optional if already in components
    fit_metadata: dict                       # rmse, rank, n_params, convergence, version

    def reassemble(self) -> np.ndarray:
        return sum(self.components.values())

    def to_json(self) -> dict: ...
    @classmethod
    def from_json(cls, d: dict) -> 'DecompositionBlob': ...

FITTER_REGISTRY: dict[str, Callable] = {}

def register_fitter(method_name: str):
    def decorator(fn): FITTER_REGISTRY[method_name] = fn; return fn
    return decorator

def dispatch_fitter(shape_label: str, domain_hint: str | None = None) -> Callable:
    table = {
        ('plateau',   None):              'Constant',
        ('trend',     'remote-sensing'):  'LandTrendr',
        ('trend',     None):              'ETM',
        ('step',      None):              'ETM',
        ('spike',     None):              'Delta',
        ('cycle',     'multi-period'):    'MSTL',
        ('cycle',     None):              'STL',
        ('transient', 'seismo-geodesy'):  'GrAtSiD',
        ('transient', None):              'ETM',
        ('noise',     None):              'NoiseModel',
    }
    key = (shape_label, domain_hint) if (shape_label, domain_hint) in table else (shape_label, None)
    method = table[key]
    return FITTER_REGISTRY[method]
```

---

## Acceptance Criteria

- [ ] `backend/app/models/decomposition.py` with:
  - `DecompositionBlob` dataclass per schema above
  - `to_json` / `from_json` round-trip preserves all fields bit-identically for numeric arrays (use `np.allclose` in round-trip test)
  - `reassemble() -> np.ndarray` returning sum of components
- [ ] `backend/app/services/decomposition/dispatcher.py` with:
  - `FITTER_REGISTRY` module-level dict
  - `register_fitter(method_name)` decorator
  - `dispatch_fitter(shape_label, domain_hint=None) -> Callable`
  - Dispatch table covers all 7 shapes
- [ ] All fitters (SEG-013..018) use `@register_fitter(...)` to register themselves at import time
- [ ] Storage: SQLAlchemy model `Segment` gains a `decomposition_json: JSON` column; migration script provided
- [ ] Round-trip test: `blob → json → blob'` preserves components within `np.allclose(rtol=1e-12)`
- [ ] Dispatcher returns a fitter for every shape in the 7-vocab (else explicit `KeyError` with helpful message)
- [ ] Dispatcher honors optional `domain_hint` in {hydrology, seismo-geodesy, remote-sensing, other}
- [ ] Plugin extensibility: adding a new fitter requires only creating a file and decorating the entry function — no changes to dispatcher or models
- [ ] Tests cover: registration, dispatch for all 7 shapes × 4 domain hints, JSON round-trip, unknown-shape error, `reassemble` correctness
- [ ] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent — schema review: confirm dispatch table matches [[_project HypotheX-TS/HypotheX-TS - Formal Definitions]] §6 and is consistent with the paper's Novelty Positioning decomposition-first claim
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-019: decomposition blob schema + shape-driven fitter dispatcher"`
- [ ] Update Status to `[x] Done`

## Work Done

- `backend/app/models/decomposition.py` — `DecompositionBlob` dataclass; `to_json`/`from_json` with base64-encoded arrays (bit-identical round-trip); `reassemble()` sums components; recursive `_serialize_value`/`_deserialize_value` helpers handle nested arrays in coefficients
- `backend/app/models/segment.py` — `Segment` SQLAlchemy model with `decomposition_json: JSON` column
- `backend/app/models/__init__.py` — added `Segment` import so `db.create_all()` picks it up
- `backend/app/services/decomposition/__init__.py` — package init
- `backend/app/services/decomposition/dispatcher.py` — `FITTER_REGISTRY`, `register_fitter` decorator, `dispatch_fitter` with auto-discovery via `pkgutil.iter_modules`; dispatch table covers all 7 shapes × domain hints; plugin extensibility: drop a file in `fitters/`, no other changes needed
- `backend/app/services/decomposition/fitters/` — 9 stub fitters: `constant.py`, `delta.py`, `etm.py`, `stl.py`, `mstl.py`, `bfast.py`, `landtrendr.py`, `eckhardt.py`, `gratsid.py`, `noise_model.py`; each uses `@register_fitter`; all stubs produce valid blobs where `reassemble()` recovers X within tolerance
- `backend/migrations/add_segment_table.py` — migration script (safe for existing DBs; adds column if missing)
- `backend/tests/test_decomposition.py` — 83 tests: reassemble, JSON round-trip (bit-identical + allclose), serialisation helpers, registration, dispatch for all 7 shapes × 5 domain hints, unknown-shape KeyError, end-to-end blob validity + reassemble + JSON round-trip for all 7 shapes

---
