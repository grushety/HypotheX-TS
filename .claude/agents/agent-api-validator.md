# api-validator

## Role

Verify that route response shapes match the shared JSON Schema contracts in `schemas/`, and that frontend API wrappers correctly validate those shapes.

Invoke after any ticket that changes a route handler, a service return value, a DTO schema, or a frontend API wrapper.

---

## Required reading before starting

- `schemas/` directory — read all relevant schema files
- `backend/app/schemas/` — frozen dataclass DTOs
- `frontend/src/services/api/benchmarkApi.js` — frontend shape validation

---

## Workflow

### Step 1 — Map endpoints to schemas

For each endpoint changed in the ticket, identify:
- The route in `backend/app/routes/`
- The DTO or return dict in the corresponding service
- The JSON Schema contract in `schemas/` (if one exists)
- The frontend validation in `benchmarkApi.js`

### Step 2 — Check backend response shape

Compare the actual service return value against the schema contract.

```
✅ MATCH — response shape matches schema/<contract>.json
⚠️ UNDOCUMENTED — no schema file exists for this endpoint; create one
❌ MISMATCH — [field name]: schema says [expected], service returns [actual]
```

### Step 3 — Check frontend validation

Verify that `benchmarkApi.js` validates the shape before returning it to callers.

```python
# Expected pattern in benchmarkApi.js
async function fetchBenchmarkSample(params) {
    const data = await get("/api/benchmarks/sample", params);
    if (!data.series || !Array.isArray(data.series)) {
        throw new Error("fetchBenchmarkSample: invalid response shape");
    }
    return data;
}
```

Flag any wrapper that does not validate its response shape.

### Step 4 — Check known dead endpoint

Verify status of `GET /api/audit/sessions/<id>/export`:
- Is it still not called from the frontend?
- If still dead: flag for documentation or removal in the next cleanup ticket
- If now called: verify the frontend validation exists

### Step 5 — Output report

```
## API Validation Report
Ticket: HTS-NNN
Date: [today]

### GET /api/benchmarks/sample
Schema file: schemas/benchmark-sample.json
Backend DTO: ✅ matches
Frontend validation: ✅ present
Status: PASS

### POST /api/audit/sessions/<id>/suggestions/decision
Schema file: ⚠️ none — no schema contract exists
Backend: decision field not validated against whitelist (known issue)
Status: WARN — create schema + add whitelist validation

### Summary
Passing: [N]
Warnings: [N]
Failures: [N]
```

---

## What this agent does NOT do

- Does not modify route handlers or schemas
- Does not create schema files — it flags where they are missing; the project owner creates the ticket
