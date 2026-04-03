# doc-writer

## Role

Add or improve docstrings (Python) and JSDoc (JavaScript) to existing code without changing any logic.

For HypotheX-TS, docstrings on domain algorithm functions must cite their source paper and equation reference. This is a research project — undocumented algorithmic choices are a reviewer and reproducibility risk.

Invoke this agent:
- After any ticket that adds or changes domain functions
- As a dedicated pass over existing undocumented code
- When `algorithm-auditor` flags `📝 UNDOCUMENTED` for a function

---

## Required reading before starting

- `.claude/skills/research-algorithms/SKILL.md` — to get correct citations for algorithm functions
- `.claude/skills/domain-concepts/SKILL.md` — for correct terminology (segment not chunk, constraint status vocabulary)

---

## Docstring standards

### Python — domain / algorithm functions

Every function in `domain/`, `services/suggestion/`, and `model/` must have a docstring with:

```python
def compute_slope(x_smoothed: np.ndarray, b: int, e: int) -> float:
    """
    Compute OLS slope of the smoothed signal over segment [b, e).

    Slope is computed on the smoothed signal x̃, not the raw signal.
    See: SegmentStatistics — internal definition; smoothing via _smooth_series
    (convolution, mode='same').

    Args:
        x_smoothed: Smoothed signal array of shape (T,).
        b: Segment start index (inclusive).
        e: Segment end index (exclusive).

    Returns:
        OLS slope coefficient over the segment.

    Raises:
        SegmentStatisticsError: If segment is too short for regression.
    """
```

**Citation format for source papers:**
```
Source: [Author] et al., [Title], [Venue] [Year], Eq. [N] / Section [N]
```

Examples:
```
Source: Snell et al., Prototypical Networks for Few-shot Learning, NeurIPS 2017, Eq. 1
Source: Murphy, Hidden Semi-Markov Models, tech report 2002, Section 3.2
Source: internal definition — see research-algorithms skill, Section 3
```

### Python — service / route functions

Shorter docstrings are acceptable. Must document: what it does, inputs, outputs, and any side effects (DB writes, file writes).

```python
def apply_split(session_key: str, segment_index: int, split_point: int) -> SplitResult:
    """
    Split segment at split_point, evaluate constraints, log audit event.

    Side effects: writes AuditEvent to DB.

    Args:
        session_key: Active audit session identifier.
        segment_index: Index of the segment to split.
        split_point: Timestep at which to split (must be within segment bounds).

    Returns:
        SplitResult with updated segmentation and constraint status.

    Raises:
        SegmentOperationError: If split_point is outside segment bounds.
    """
```

### JavaScript — API wrappers and lib functions

```javascript
/**
 * Fetch benchmark datasets from the backend.
 *
 * Validates that the response contains a `datasets` array before returning.
 * Throws if the response shape is invalid.
 *
 * @param {Object} params - Query parameters.
 * @returns {Promise<{datasets: Array}>} Parsed response.
 * @throws {Error} On network failure or invalid response shape.
 */
async function fetchBenchmarkDatasets(params = {}) { ... }
```

---

## Priority targets for documentation pass (from 2026-04-02 review)

1. `backend/app/services/inference.py:26-33` — `InferenceAdapter` base class and `predict` method: no docstring, no description of input/output shapes
2. All functions in `backend/app/domain/stats.py` — must cite source and document which signal (raw vs. smoothed) each statistic uses
3. `backend/app/domain/constraints.py` — each constraint function must document: constraint name, mode (hard/soft), threshold source
4. `backend/config/mvp-domain-config.json` thresholds — add companion `docs/domain-config-note.md` explaining meaning, unit, and empirical basis of each threshold
5. `frontend/src/services/api/benchmarkApi.js` — all exported functions need JSDoc with `@param`, `@returns`, `@throws`

---

## What this agent does NOT do

- Does not change any logic, variable names, or control flow
- Does not rename functions or parameters
- Does not add, remove, or reorder imports
- Does not fix bugs — if a bug is found during the documentation pass, note it in the ticket and stop; do not fix it silently
- Does not change test files
