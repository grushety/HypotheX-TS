# HypotheX-TS — Code Review

**Reviewed:** 2026-04-02  
**Reviewer:** Claude Code (automated senior review)  
**Scope:** Full repository — backend, frontend, schemas, evaluation, model layer

---

## Executive Summary

1. 🔴 **Hardcoded secret key** — `SECRET_KEY = "dev"` in `backend/app/config.py:12` is used in every environment with no override mechanism; Flask session signatures are trivially forgeable.
2. 🔴 **No authentication layer** — All API endpoints are fully public. No session validation, no CSRF protection, no rate limiting.
3. 🟡 **Dead code in `_smooth_series`** — `stats.py:269` has an unreachable `if window_size < 1` branch (the preceding `<= 1` guard already returns); the `SegmentStatisticsError` for invalid window size is silently skipped.
4. 🟡 **Per-request service re-instantiation** — `_get_dataset_registry()` and siblings in `benchmarks.py:19-43` create a fresh `DatasetRegistry` (file-system reads) on every request when the config key is absent, which is the common path in non-test environments.
5. 🟡 **Backend audit-export endpoint has no frontend caller** — `GET /api/audit/sessions/<id>/export` is implemented but never called by the frontend; the frontend generates log exports entirely client-side, making the endpoint dead in the running application.
6. 🟡 **Hardcoded CORS origin and no `.env.example`** — `FRONTEND_ORIGIN = "http://127.0.0.1:5173"` in `config.py:22` is not overridable via environment; there is no `.env.example` documenting required variables.
7. 🔵 **`load_domain_config()` is called once per constraint evaluation call** — every invocation of `evaluate_constraints`, `evaluate_minimum_segment_duration`, etc. loads and parses the JSON file from disk independently, with no caching.
8. 🔵 **Naming inconsistency between "chunk" and "segment"** — `chunk_scoring.py`, `chunk_scoring`, `ChunkScores`, `operationsByChunk` (backend) vs. `segments`, `SegmentStatistics`, `provisionalSegments` (everywhere else). The two terms are used interchangeably with no clear distinction.
9. 🔵 **No API versioning** — All routes are `/api/<resource>` with no version prefix; any breaking schema change requires coordinated frontend/backend deployment with no backward-compatibility path.
10. 🔵 **No TypeScript in a project named "-TS"** — The frontend is plain JavaScript with no type annotations (no JSDoc, no `.d.ts`, no `tsconfig.json`). Runtime shape mismatches are only caught by manual structural checks in `benchmarkApi.js`.

---

## 1. Project Overview

### Stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.10+ |
| Backend framework | Flask 3.1.0 |
| ORM / database | Flask-SQLAlchemy 3.1.1 / SQLite |
| CORS | Flask-Cors 5.0.1 |
| Numerics | NumPy 2.4.3 |
| Backend tests | pytest 8.3.5 |
| Frontend framework | Vue 3.5.13 |
| Frontend build | Vite 6.2.3 |
| Frontend language | JavaScript (ES modules, no TypeScript) |
| Frontend tests | Node's built-in `--test` runner |

### Architecture

```
HypotheX-TS/
├── backend/
│   ├── app/
│   │   ├── config.py              # Config classes (no env override for SECRET_KEY)
│   │   ├── factory.py             # App factory
│   │   ├── extensions.py          # SQLAlchemy + CORS init
│   │   ├── core/                  # Domain config loader, path constants
│   │   ├── domain/                # Pure business logic (stats, constraints, scoring)
│   │   ├── models/                # SQLAlchemy models (AuditSession, AuditEvent)
│   │   ├── routes/                # Flask blueprints (benchmarks, audit, health)
│   │   ├── schemas/               # Dataclass-based response DTOs
│   │   └── services/              # Orchestration layer (datasets, models, inference…)
│   │       └── suggestion/        # Boundary proposal + prototype classifier package
│   ├── tests/                     # 25 test files (~2 600 LOC)
│   └── config/
│       └── mvp-domain-config.json
├── frontend/
│   └── src/
│       ├── views/BenchmarkViewerPage.vue  # Main page
│       ├── components/            # UI components (viewer, operations, history…)
│       ├── lib/                   # Framework-agnostic business logic
│       └── services/api/          # Fetch wrappers (benchmarkApi.js)
├── model/                         # Standalone model modules (suggestion, encoder)
├── evaluation/                    # Evaluation harness and metrics
└── schemas/                       # Shared JSON Schema contracts
```

### Implemented Features

**Backend**
- Dataset registry (load manifests, enumerate datasets, load NPZ samples)
- Model registry (load manifest, enumerate families/artifacts)
- Model–dataset compatibility validation
- Prototype-based nearest-centroid inference (one adapter family: `nearest_prototype`)
- Boundary suggestion service (boundary proposals + prototype chunk classification)
- Segment statistics (slope, variance, sign consistency, residual, peak, periodicity, context contrast)
- Chunk scoring (maps statistics to 6 ontology labels)
- Constraint evaluation (minimum duration, monotonic trend, plateau stability, label compatibility)
- Audit log (session + event persistence via SQLite; suggestion decision logging)
- Audit session export endpoint
- Health endpoint with DB probe

**Frontend**
- Time-series rendering with segmentation overlay (`TimeSeriesChart`, `SegmentationOverlay`)
- Segment selection and highlighting
- Boundary dragging
- Label editing
- Split, merge, reclassify semantic operations
- Soft-constraint warnings (client-side evaluation)
- Interaction history panel (newest-first)
- Client-side JSON interaction-log export
- Benchmark selector (dataset / model / split)
- Prediction panel with scores
- Model comparison panel

---

## 2. Frontend ↔ Backend Coverage Check

| Backend Endpoint | Frontend Call | Status |
|---|---|---|
| `GET /api/health` | Not called from UI | ⚠️ partially — only useful for ops/smoke tests |
| `GET /api/benchmarks/datasets` | `fetchBenchmarkDatasets()` in `benchmarkApi.js:28` | ✅ covered |
| `GET /api/benchmarks/models` | `fetchBenchmarkModels()` in `benchmarkApi.js:39` | ✅ covered |
| `GET /api/benchmarks/compatibility` | `fetchBenchmarkCompatibility()` in `benchmarkApi.js:61` | ✅ covered |
| `GET /api/benchmarks/sample` | `fetchBenchmarkSample()` in `benchmarkApi.js:76` | ✅ covered |
| `GET /api/benchmarks/prediction` | `fetchBenchmarkPrediction()` in `benchmarkApi.js:96` | ✅ covered |
| `GET /api/benchmarks/suggestion` | `fetchBenchmarkSuggestion()` in `benchmarkApi.js:119` | ✅ covered |
| `GET /api/benchmarks/operation-registry` | `fetchBenchmarkOperationRegistry()` in `benchmarkApi.js:50` | ✅ covered |
| `GET /api/audit/sessions/<id>/export` | **No frontend call** | ❌ missing |
| `POST /api/audit/sessions/<id>/suggestions/decision` | `submitSuggestionDecision()` in `benchmarkApi.js:137` | ✅ covered |

**Finding:** `GET /api/audit/sessions/<session_id>/export` (`audit.py:12`) is not called from the frontend. The frontend builds and downloads the interaction log entirely in the browser via `createInteractionLogExport()` (`BenchmarkViewerPage.vue:508`). The backend endpoint is either dead code or intended for a future server-side export flow.

---

## 3. Code Issues

### 3.1 Security

#### 🔴 Hardcoded secret key
**File:** `backend/app/config.py:12`
```python
class Config:
    SECRET_KEY = "dev"
```
`SECRET_KEY` is never read from an environment variable and is not overridden in any non-test config class. Flask uses this key to sign session cookies. An attacker who knows this value (it is public in the repo) can forge any session.

**Suggestion:** Replace with:
```python
SECRET_KEY = os.environ.get("SECRET_KEY") or (
    "dev" if os.environ.get("FLASK_ENV") == "development" else None
)
```
Raise a startup error if `SECRET_KEY` is `None` in a non-development environment.

#### 🔴 No authentication or authorization
**File:** `backend/app/routes/benchmarks.py`, `backend/app/routes/audit.py`  
All endpoints are fully public. Any caller with network access can enumerate datasets, trigger inference, and write audit events.

**Suggestion:** Add a minimal API-key check (e.g. `X-API-Key` header validated against an env var) or a Flask-Login session check at the blueprint level before any production exposure.

#### 🟡 Hardcoded CORS origin
**File:** `backend/app/config.py:22`
```python
FRONTEND_ORIGIN = "http://127.0.0.1:5173"
```
Not configurable at runtime. Deployments on non-localhost origins will be rejected by the browser.

**Suggestion:**
```python
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://127.0.0.1:5173")
```

---

### 3.2 Bugs / Logic Errors

#### 🟡 Dead code — unreachable validation branch in `_smooth_series`
**File:** `backend/app/domain/stats.py:266-270`
```python
def _smooth_series(segment: np.ndarray, window_size: int) -> np.ndarray:
    if window_size <= 1:        # line 267 — returns immediately for window_size == 1 or < 1
        return segment
    if window_size < 1:         # line 269 — NEVER REACHED
        raise SegmentStatisticsError("Smoothing window must be at least 1.")
```
The `if window_size < 1` guard on line 269 is never reached because the `<= 1` guard on line 267 already returns. Any caller passing a window size of 0 or negative silently receives the unsmoothed segment rather than an error.

**Suggestion:** Swap the order — validate first, return early second:
```python
if window_size < 1:
    raise SegmentStatisticsError("Smoothing window must be at least 1.")
if window_size == 1:
    return segment
```

#### 🟡 Misleading variable name in `evaluate_plateau_stability`
**File:** `backend/app/domain/constraints.py:200-208`
```python
periodicity_ok = (
    statistics.segmentLength < periodic_min_length
    or statistics.periodicityScore < periodicity_min
)
```
The variable is named `periodicity_ok` but it actually means "periodicity does NOT disqualify this as a plateau." A segment with high periodicity and long length sets `periodicity_ok = False`, triggering a violation. The naming is inverted relative to its meaning, making the condition hard to audit.

**Suggestion:** Rename to `no_periodicity_disqualifier` or expand the inline comment:
```python
# True when periodicity does NOT disqualify the plateau
no_periodicity_issue = (
    statistics.segmentLength < periodic_min_length
    or statistics.periodicityScore < periodicity_min
)
```

#### 🟡 `evaluate_label_compatibility` only checks `event + event` adjacency
**File:** `backend/app/domain/constraints.py:244-259`  
The domain config (`mvp-domain-config.json`) declares constraint defaults for `label_compatibility`, but the implementation only flags the single case of two consecutive `event` segments. Other potentially illegal adjacencies (e.g., `spike + spike`, or `transition` at the series boundary) are silently ignored.

**Suggestion:** If the ontology defines additional adjacency rules, implement them or document explicitly that this constraint is intentionally minimal for MVP scope.

#### 🟡 `_select_sample` uses index-based label lookup without bounds guard on `label_space`
**File:** `backend/app/services/inference.py:223-226`
```python
label_index = int(labels[sample_index])
true_label = None
if 0 <= label_index < len(dataset.summary.classes):
    true_label = dataset.summary.classes[label_index]
```
If `labels[sample_index]` is not an integer-castable value (e.g., a string class name in some datasets), `int(labels[sample_index])` raises `ValueError` and the request returns an unhandled 500.

**Suggestion:** Wrap in a try/except or validate the dataset label format earlier in `DatasetRegistry`.

---

### 3.3 Performance

#### 🟡 Per-request registry and service instantiation
**File:** `backend/app/routes/benchmarks.py:19-43`
```python
def _get_dataset_registry() -> DatasetRegistry:
    return current_app.config.get("DATASET_REGISTRY") or DatasetRegistry()
```
`DatasetRegistry()` reads and parses the dataset manifest JSON from disk. This happens on every request that does not pre-populate the config key. In tests the key is injected via fixtures; in production the key is never set, so every `/api/benchmarks/*` call re-reads the manifest.

**Suggestion:** Initialize the registries once in the app factory:
```python
# factory.py
app.config["DATASET_REGISTRY"] = DatasetRegistry()
app.config["MODEL_REGISTRY"] = ModelRegistry()
```

#### 🟡 `load_domain_config()` reads and parses JSON on every call
**File:** `backend/app/core/domain_config.py:47-49`  
Called from `compute_segment_statistics`, `evaluate_constraints`, `compute_chunk_scores`, and their sub-functions. Each call opens and parses `mvp-domain-config.json` from disk. Under load this is unnecessary I/O and parsing overhead.

**Suggestion:** Cache the result using `functools.lru_cache`:
```python
@functools.lru_cache(maxsize=1)
def load_domain_config(path: Path = DEFAULT_DOMAIN_CONFIG_PATH) -> DomainConfig:
    ...
```
Note: `lru_cache` requires a hashable argument; `Path` is hashable.

---

### 3.4 Error Handling

#### 🟡 `log_suggestion_decision` does not validate `decision` field values
**File:** `backend/app/routes/audit.py:28-31`  
The endpoint validates presence of `required_fields` but does not validate that `decision` is one of the expected values (e.g., `"accepted"` / `"overridden"`). An arbitrary string is passed straight to `AuditLogService`.

**Suggestion:** Add:
```python
VALID_DECISIONS = {"accepted", "overridden"}
if payload["decision"] not in VALID_DECISIONS:
    return jsonify({"error": f"decision must be one of {sorted(VALID_DECISIONS)}"}), 400
```

#### 🔵 `_get_audit_log_service()` in `audit.py` can raise uncaught errors
**File:** `backend/app/routes/audit.py:8-9`  
`AuditLogService()` instantiates a SQLAlchemy session internally. Any DB connection failure at this point is not caught and will surface as an unhandled 500. The benchmarks blueprint has the same pattern.

**Suggestion:** Add a shared `@app.errorhandler(Exception)` that returns a structured 500 JSON response and logs the traceback, rather than Flask's default HTML error page.

---

### 3.5 Dead Code / Unused

#### 🔵 `GET /api/audit/sessions/<id>/export` — backend endpoint with no frontend caller
**File:** `backend/app/routes/audit.py:12-19`  
As shown in §2, the frontend never calls this endpoint; it builds exports client-side. The endpoint is either dead or planned for a future non-browser client.

**Suggestion:** Either document the intended future caller, or remove the endpoint if purely client-side export is the long-term design.

#### 🔵 Unused `AuditSession` relationship (if any)
Verify in `backend/app/models/audit_log.py` whether the SQLAlchemy relationship between `AuditSession` and `AuditEvent` is fully exercised by the export path, or whether the session creation path is never called from the running application.

---

## 4. Documentation Issues

### 4.1 Missing `.env.example`
🟡 There is no `.env.example` file. The following configuration values are only discoverable by reading `config.py`:

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Flask session signing | `"dev"` (hardcoded) |
| `FRONTEND_ORIGIN` | CORS allowed origin | `"http://127.0.0.1:5173"` (hardcoded) |
| `FLASK_ENV` | Not currently read | Not used |

**Suggestion:** Create `.env.example` at repo root documenting all runtime-configurable variables.

### 4.2 README gaps
**File:** `README.md`

| Missing item | Severity |
|---|---|
| No mention of `schemas/` directory and how it relates to the API | 🔵 info |
| No mention of `evaluation/` harness or how to run it | 🔵 info |
| No mention of `model/` directory | 🔵 info |
| Backend startup instructions use Windows syntax (`.venv\Scripts\activate`) — won't work on Linux/macOS | 🟡 warning |
| No description of required environment variables | 🟡 warning |
| No troubleshooting section for common failures (missing manifest, DB not initialized) | 🔵 info |

### 4.3 Domain config is undocumented inline
**File:** `backend/config/mvp-domain-config.json`  
Threshold values (`slopeAbsMin: 0.1`, `varianceMax: 0.05`, etc.) have no inline explanation of their meaning, unit, or empirical basis.

**Suggestion:** Add a companion `docs/domain-config-note.md` (referenced in README) explaining each threshold and duration limit. The file `docs/domain-config-note.md` is referenced in `README.md:27` but may not fully document the threshold rationale.

### 4.4 `InferenceAdapter` base class undocumented
**File:** `backend/app/services/inference.py:26-33`
```python
class InferenceAdapter:
    def predict(self, handle, sample):
        raise NotImplementedError
```
No docstring on the abstract method, no description of expected input/output shapes.

---

## 5. Code Quality

### 5.1 Naming Inconsistencies

| Context | Term A | Term B | Impact |
|---|---|---|---|
| Ontology labels | `chunk` (`chunk_scoring.py`, `operationsByChunk`) | `segment` (`SegmentStatistics`, `provisionalSegments`) | Confusing when crossing module boundaries |
| API query params | `sample_index` (snake_case) | `sampleIndex` (camelCase in JSON bodies) | Inconsistent; callers must track which format to use |
| Constraint modes | `"soft"` / `"hard"` | `"ALLOW"` / `"DENY"` in operation validation | Different vocabulary for related concepts |
| Split identifiers | `"train"` / `"test"` | No enum; bare strings compared in `_select_sample` | Risk of silent typo bugs |

### 5.2 DRY Violations

#### Repeated error-response pattern across route handlers
**File:** `backend/app/routes/benchmarks.py` (6 occurrences)
```python
except DatasetRegistryError as exc:
    return jsonify({"error": str(exc)}), 500
```
The same try/except → jsonify pattern is repeated in `list_datasets`, `predict_sample`, `fetch_sample`, and `fetch_suggestion`. The status code and format are inconsistent in one case (compatibility endpoint returns no try/except at all — any exception from `validator.validate()` becomes an unhandled 500).

**Suggestion:** Create a decorator or use Flask's `@blueprint.errorhandler` to centralize error-to-JSON mapping per exception type.

#### Domain config loaded per-function instead of being injected
`load_domain_config()` is the first call in `evaluate_constraints`, `evaluate_minimum_segment_duration`, `evaluate_monotonic_trend_consistency`, `evaluate_plateau_stability`, `evaluate_label_compatibility`, `compute_chunk_scores`, and `compute_segment_statistics`. The result is never threaded through — each function independently reloads it.

### 5.3 Test Coverage Gaps

#### Backend
| Gap | Severity |
|---|---|
| `GET /api/audit/sessions/<id>/export` — no route-level test for this endpoint | 🟡 |
| `_smooth_series` with `window_size=0` — the dead-code bug is untested | 🟡 |
| `_select_sample` with non-integer labels — edge case not tested | 🟡 |
| `PredictionService` with missing `_ADAPTERS` key (unknown family) | 🔵 |
| Manifest missing / corrupt JSON — tested? (verify in `test_benchmark_manifest.py`) | 🟡 |
| `evaluate_label_compatibility` with non-event adjacency rules | 🔵 |

#### Frontend
| Gap | Severity |
|---|---|
| `BenchmarkViewerPage.vue` has no integration test | 🟡 |
| `benchmarkApi.js` — network timeout behavior untested | 🔵 |
| `submitSuggestionDecision` — POST error path untested | 🔵 |
| Operations that affect multiple segments simultaneously (merge) — end-to-end untested | 🟡 |

### 5.4 Dependency Notes

**Backend** (`backend/requirements.txt`) — all dependencies pinned, no known vulnerabilities in listed versions. No linter (`flake8`, `ruff`) or type checker (`mypy`) in the dependency list, so quality gates are not enforced by CI.

**Frontend** (`frontend/package.json`) — only 3 runtime dependencies, all with caret ranges. No linter (`eslint`), formatter (`prettier`), or type checker in `devDependencies`. The test runner uses Node's experimental `--test` flag, which has changed APIs across Node versions.

---

## 6. Suggestions Index

| # | File | Line | Severity | Issue | Suggestion |
|---|---|---|---|---|---|
| 1 | `backend/app/config.py` | 12 | 🔴 | Hardcoded `SECRET_KEY = "dev"` | Read from env var; raise at startup if absent in non-dev |
| 2 | `backend/app/routes/benchmarks.py` | all | 🔴 | No authentication on any endpoint | Add API-key or session middleware at blueprint level |
| 3 | `backend/app/domain/stats.py` | 269 | 🟡 | Dead code — `if window_size < 1` unreachable | Move validation before early-return guard |
| 4 | `backend/app/domain/constraints.py` | 200 | 🟡 | Misleading variable name `periodicity_ok` | Rename to `no_periodicity_issue` with a comment |
| 5 | `backend/app/routes/benchmarks.py` | 19–43 | 🟡 | Per-request manifest re-reads | Initialize registries once in `factory.py` |
| 6 | `backend/app/core/domain_config.py` | 47 | 🟡 | `load_domain_config()` parses JSON on every call | Add `@functools.lru_cache(maxsize=1)` |
| 7 | `backend/app/config.py` | 22 | 🟡 | Hardcoded `FRONTEND_ORIGIN` | Read from env var with localhost fallback |
| 8 | `backend/app/routes/audit.py` | 43 | 🟡 | `decision` field not validated against allowed values | Whitelist `{"accepted", "overridden"}` |
| 9 | `backend/app/services/inference.py` | 223 | 🟡 | `int(labels[sample_index])` may raise on string labels | Wrap in try/except with a `SampleSelectionError` |
| 10 | `backend/app/routes/audit.py` | 12 | 🔵 | Backend audit-export endpoint never called by frontend | Document intended caller or remove |
| 11 | `backend/app/routes/benchmarks.py` | 81–91 | 🟡 | `validate_compatibility` has no exception handler | Wrap `validator.validate()` in try/except |
| 12 | (repo root) | — | 🟡 | No `.env.example` | Create one listing `SECRET_KEY`, `FRONTEND_ORIGIN` |
| 13 | `README.md` | 38 | 🟡 | Windows-only venv activation path | Add cross-platform alternative |
| 14 | `backend/app/domain/constraints.py` | 244 | 🔵 | `label_compatibility` only checks `event+event` | Document or extend if other adjacency rules apply |
| 15 | `frontend/` | — | 🔵 | No TypeScript / JSDoc | Add JSDoc types for key service functions |
| 16 | `frontend/package.json` | — | 🔵 | No `eslint` / `prettier` in devDependencies | Add linting to keep code consistent |
| 17 | `backend/` | — | 🔵 | No `mypy` or `ruff` in requirements | Add to a `requirements-dev.txt` and CI |

---

## 7. Positive Observations

- **Well-layered architecture** — clear separation: routes → services → domain → core. Business logic does not leak into route handlers.
- **Custom exception hierarchy** — every service defines its own error types (`DatasetRegistryError`, `SuggestionServiceError`, etc.), making error routing in route handlers explicit.
- **Response validation in `benchmarkApi.js`** — the frontend validates response shape before using it, giving early and clear errors for API contract violations.
- **Frozen dataclasses throughout** — `SegmentStatistics`, `ChunkScores`, `ConstraintViolation`, `DomainConfig`, etc. are immutable, preventing accidental mutation bugs.
- **Dependency injection in services** — `PredictionService`, `CompatibilityValidator`, and `BoundarySuggestionService` all accept their dependencies as constructor arguments, making them straightforwardly testable.
- **JSON schema contracts in `schemas/`** — shared contracts across backend, frontend, model, and evaluation layers reduce cross-layer drift.
- **`suggestion/` package is properly structured** — `__init__.py` re-exports the public API cleanly; the import in `benchmarks.py:13` is valid.
- **`prototype_classifier.py`'s `build_default_support_segments`** is correctly exported and importable.
- **Comprehensive backend test suite** — 25 files covering domain logic, services, and routes individually.
- **`_smooth_series` smoothing is mathematically correct** (convolution mode `"same"` preserves segment length) — only the guard order has a bug.
