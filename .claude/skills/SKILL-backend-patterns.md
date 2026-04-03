# HypotheX-TS — Backend Patterns Skill

Load this skill before any backend work: routes, services, domain logic, models, or tests.

---

## 1. Layer Architecture

```
routes/          → thin; validate input, call service, return JSON
services/        → orchestration; coordinate domain + models + DB
domain/          → pure functions; no Flask, no DB, no I/O
core/            → config loading, path constants
models/          → SQLAlchemy ORM definitions only; no business logic
schemas/         → frozen dataclasses as response DTOs
```

**Rules:**
- Route handlers contain: input validation, one service call, error catching, JSON return. Nothing else.
- Services contain: orchestration logic, DB reads/writes, calls to domain functions.
- Domain functions are pure: same input → same output, no side effects, no imports from Flask or SQLAlchemy.
- `core/` is the only place that reads file paths or loads config.

**Violation examples to flag during review:**
- Business logic in a route handler
- A domain function importing `flask` or `db`
- A service directly reading a file path that is not from `core/`
- A route handler calling another route handler

---

## 2. Exception Hierarchy

Each service module defines its own error type. Route handlers catch these and return structured JSON.

```python
# Pattern — service module
class DatasetRegistryError(Exception):
    pass

class SuggestionServiceError(Exception):
    pass
```

```python
# Pattern — route handler
@blueprint.route("/datasets")
def list_datasets():
    try:
        result = dataset_service.list()
        return jsonify(result), 200
    except DatasetRegistryError as exc:
        return jsonify({"error": str(exc)}), 500
```

**Known issue:** the `validate_compatibility` call in `routes/benchmarks.py:81-91` has no try/except — any exception becomes an unhandled 500. Fix in dedicated ticket.

**Preferred:** use `@blueprint.errorhandler` to centralise error-to-JSON mapping per exception type rather than repeating try/except in every handler. This is a known DRY violation from the 2026-04-02 review.

---

## 3. Frozen Dataclasses for DTOs

All response DTOs and domain result objects must be frozen dataclasses. This prevents accidental mutation.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SegmentStatistics:
    slope: float
    variance: float
    sign_consistency: float
    residual: float
    peak: float
    periodicity: float
    context_contrast: float

@dataclass(frozen=True)
class ConstraintViolation:
    constraint_name: str
    status: str          # one of: PASS, WARN, FAIL, PROJECTED
    message: str
```

Never use plain dicts for domain results — frozen dataclasses give type clarity and prevent mutation bugs.

---

## 4. Dependency Injection in Services

Services accept their dependencies as constructor arguments. Never instantiate dependencies inside service methods.

```python
# Correct
class PredictionService:
    def __init__(self, registry, adapter_map):
        self._registry = registry
        self._adapters = adapter_map

    def predict(self, handle, sample):
        adapter = self._adapters[handle.family]
        return adapter.predict(handle, sample)

# Wrong
class PredictionService:
    def predict(self, handle, sample):
        registry = DatasetRegistry()   # ← instantiating per-call is wrong
        ...
```

Registries and adapters must be constructed once in `factory.py` and injected into services at app startup.

---

## 5. Domain Config Caching

`load_domain_config()` reads and parses `backend/config/mvp-domain-config.json`. It is called by every constraint function. Without caching, this is a disk read on every constraint evaluation.

**Required pattern:**

```python
import functools

@functools.lru_cache(maxsize=1)
def load_domain_config() -> DomainConfig:
    with open(CONFIG_PATH) as f:
        raw = json.load(f)
    return DomainConfig(**raw)
```

**This is a known missing fix** (issue #7 from 2026-04-02 review). Any ticket that touches `core/domain_config.py` must add this decorator.

In tests, clear the cache with `load_domain_config.cache_clear()` in fixtures to avoid test pollution.

---

## 6. Registry Initialisation

Dataset registry and model registry must be constructed once in `factory.py`, not per-request.

```python
# factory.py — correct
def create_app(config=None):
    app = Flask(__name__)
    ...
    dataset_registry = DatasetRegistry(app.config["BENCHMARKS_ROOT"])
    model_registry = ModelRegistry(app.config["MODELS_ROOT"])
    app.extensions["dataset_registry"] = dataset_registry
    app.extensions["model_registry"] = model_registry
    ...
```

```python
# routes/benchmarks.py — correct
def _get_dataset_registry():
    return current_app.extensions["dataset_registry"]
```

**Known issue:** `_get_dataset_registry()` currently creates a fresh `DatasetRegistry` (file-system reads) on every request when the config key is absent. Fix in dedicated ticket.

---

## 7. Environment Variables

Two config values must come from environment variables, not hardcoded defaults:

```python
import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://127.0.0.1:5173")

    def __init__(self):
        if not self.SECRET_KEY:
            raise RuntimeError("SECRET_KEY environment variable is not set")
```

Document both in `.env.example` at the repo root:
```
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
FRONTEND_ORIGIN=http://127.0.0.1:5173
```

---

## 8. Audit Logging Pattern

Every user operation must produce an AuditEvent. This is not optional.

```python
# Pattern — service layer
def apply_operation(session_key, op_type, segment_index, params, constraint_result):
    event = AuditEvent(
        session_id=_get_session(session_key).id,
        event_type=op_type,
        segment_index=segment_index,
        payload=json.dumps(params),
        constraint_status=constraint_result.status,  # PASS | WARN | FAIL | PROJECTED
    )
    db.session.add(event)
    db.session.commit()
```

The `decision` field on suggestion-decision events must be validated against `{"accepted", "overridden"}` — bare string is not validated in the current code (known issue from review).

---

## 9. Testing Patterns

```bash
# Run all backend tests
pytest backend/tests/

# Run with coverage
pytest backend/tests/ --cov=app --cov-fail-under=80

# Run single file
pytest backend/tests/unit/test_constraints.py -x
```

**Test structure rules:**
- Each service/domain module has a corresponding test file
- Happy path, error path, and edge cases must all be covered
- Domain functions are easy to test (pure functions) — test them directly, not through routes
- Use fixtures for DB setup; never rely on test execution order
- Clear `lru_cache` in fixtures: `load_domain_config.cache_clear()`

**Known test gaps (from 2026-04-02 review):**
- `GET /api/audit/sessions/<id>/export` — no route-level test
- `_smooth_series` with `window_size=0` — unreachable dead code, untested
- `_select_sample` with non-integer labels
- Merge operation end-to-end test missing from frontend
- `BenchmarkViewerPage.vue` has no integration test

---

## 10. Shared JSON Schema Contracts

Schemas live in `schemas/` at the repo root. They are shared across backend, frontend, model layer, and evaluation.

When adding a new API response shape:
1. Define the schema in `schemas/` first
2. Implement backend DTO as a frozen dataclass matching the schema
3. Add shape validation in `benchmarkApi.js`
4. Add an `api-validator` agent run to the ticket's Definition of Done

Do not change a schema without updating all consumers: backend DTO, frontend validation, evaluation harness, model layer if applicable.
