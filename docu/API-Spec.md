# HypotheX-TS API Specification

Base URL: `http://localhost:5000`

---

## Health

### `GET /api/health`

Returns service liveness status.

**Response 200**
```json
{ "status": "ok" }
```

---

## Benchmarks

### `GET /api/benchmarks/datasets`

List all registered benchmark datasets.

**Response 200**
```json
{
  "datasets": [
    {
      "name": "ECG200",
      "status": "prepared",
      "task_type": "classification",
      "series_type": "univariate",
      "n_channels": 1,
      "train_shape": [100, 1, 96],
      "test_shape": [100, 1, 96],
      "n_classes": 2,
      "classes": ["1", "-1"],
      "export_format": "npy",
      "tensor_layout": "n_samples x n_channels x series_length",
      "notes": "..."
    }
  ]
}
```

---

### `GET /api/benchmarks/models`

List registered model families and artifacts.

**Response 200**
```json
{
  "families": [ { "family": "fcn", "display_name": "FCN", ... } ],
  "artifacts": [ { "artifact_id": "fcn-ECG200", "family": "fcn", ... } ]
}
```

---

### `GET /api/benchmarks/sample`

Fetch a single time-series sample.

**Query parameters**
| Name           | Type   | Required | Description                 |
|----------------|--------|----------|-----------------------------|
| `dataset`      | string | yes      | Dataset name (e.g. `ECG200`) |
| `split`        | string | yes      | `train` or `test`           |
| `sample_index` | int    | yes      | Zero-based sample index     |

**Response 200**
```json
{
  "dataset_name": "ECG200",
  "split": "test",
  "sample_index": 0,
  "series_length": 96,
  "channel_count": 1,
  "label": "1",
  "values": [[0.1, -0.3, ...]]
}
```

**Errors**: 400 missing/invalid params · 404 unknown dataset

---

### `GET /api/benchmarks/prediction`

Run a model inference on a sample.

**Query parameters**: `dataset`, `artifact_id`, `split`, `sample_index` (all required)

**Response 200**
```json
{
  "dataset_name": "ECG200",
  "artifact_id": "fcn-ECG200",
  "split": "test",
  "sample_index": 0,
  "predicted_label": "1",
  "true_label": "1",
  "scores": [ { "label": "1", "score": 0.92, "probability": 0.87 } ]
}
```

**Errors**: 400 invalid params · 404 unknown dataset or model

---

### `GET /api/benchmarks/compatibility`

Check model–dataset compatibility.

**Query parameters**: `dataset`, `artifact_id` (both required)

**Response 200**
```json
{
  "dataset_name": "ECG200",
  "artifact_id": "fcn-ECG200",
  "is_compatible": true,
  "messages": []
}
```

---

### `GET /api/benchmarks/suggestion`

Propose segment boundaries and labels for a sample.

**Query parameters**: `dataset`, `split`, `sample_index` (all required)

**Response 200** — `SuggestionProposal` schema:
```json
{
  "schemaVersion": "1.0.0",
  "suggestionId": "suggestion-ECG200-test-0",
  "seriesId": "ECG200:test:0",
  "modelVersion": "suggestion-model-v1",
  "seriesLength": 96,
  "channelCount": 1,
  "candidateBoundaries": [
    { "boundaryIndex": 42, "score": 0.82, "confidence": 0.82 }
  ],
  "provisionalSegments": [
    {
      "segmentId": "segment-001",
      "startIndex": 0,
      "endIndex": 41,
      "provenance": "model",
      "label": "trend",
      "confidence": 0.73,
      "labelScores": { "trend": 0.73, "plateau": 0.18, "spike": 0.09 }
    }
  ],
  "boundaryProposer": {
    "name": "conservative-change-point-v1",
    "config": { "windowSize": 6, "minSegmentLength": 5, "scoreThreshold": 0.35, "maxBoundaries": 8 }
  }
}
```

Optional fields (present when `include_uncertainty=true` is used via the service):
- `boundaryUncertainty`: array of floats, length = `seriesLength`
- `segmentUncertainty`: array of floats, length = number of segments

**Errors**: 400 invalid params · 404 unknown dataset

---

### `GET /api/benchmarks/suggestion/uncertainty`

Compute per-timestep boundary uncertainty and per-segment label uncertainty.

**Query parameters**: `dataset`, `split`, `sample_index` (all required)

**Response 200**
```json
{
  "boundary_uncertainty": [0.0, 0.01, ..., 0.83, 0.72, ..., 0.0],
  "segment_uncertainty": [0.12, 0.54]
}
```

- `boundary_uncertainty`: length equals series length; values in [0, 1]; high near proposed boundaries
- `segment_uncertainty`: one value per segment; 0 = certain, 1 = maximally uncertain

**Errors**: 400 invalid params · 404 unknown dataset

---

### `POST /api/benchmarks/suggestion/adapt`

Apply few-shot prototype updates for a session from user-labeled support segments.

The encoder weights remain frozen; only the in-memory `PrototypeMemoryBank` for the session is updated.
Session state is held in memory per process (no DB persistence).
Confidence-gating (default threshold 0.75) and drift-guarding (default max drift 0.45) are enforced.

**Request body** (JSON)
```json
{
  "session_id": "session-abc123",
  "support_segments": [
    {
      "label": "trend",
      "values": [0.1, 0.2, 0.3, 0.4, 0.5],
      "confidence": 0.9
    },
    {
      "label": "plateau",
      "values": [0.5, 0.5, 0.5, 0.5, 0.5]
    }
  ]
}
```

| Field                            | Type   | Required | Description |
|----------------------------------|--------|----------|-------------|
| `session_id`                     | string | yes      | Arbitrary session identifier; state is initialised from default templates on first use |
| `support_segments`               | array  | yes      | Non-empty list of labeled segments |
| `support_segments[].label`       | string | yes      | Semantic label (must be in active domain labels) |
| `support_segments[].values`      | array  | yes      | Time-series values for this segment |
| `support_segments[].confidence`  | float  | no       | Caller confidence in this label (default 1.0); updates below 0.75 are rejected |

**Response 200**
```json
{
  "model_version_id": "suggestion-model-v1+adapt-2",
  "prototypes_updated": ["trend", "plateau"],
  "drift_report": { "trend": 0.12, "plateau": 0.0 }
}
```

| Field                | Type            | Description |
|----------------------|-----------------|-------------|
| `model_version_id`   | string          | Version string; `+adapt-{n}` suffix counts cumulative updates for this session |
| `prototypes_updated` | array of string | Labels whose prototype was actually applied (confidence + drift gates passed) |
| `drift_report`       | object          | Per-label Euclidean drift of the prototype after update; 0.0 for first update |

**Errors**
| Status | Condition |
|--------|-----------|
| 400    | Missing or invalid `session_id` |
| 400    | `support_segments` is absent, not a list, or empty |
| 400    | Unknown label, encoding failure, or other service error |
