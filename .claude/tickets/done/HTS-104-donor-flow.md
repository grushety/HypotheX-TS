# HTS-104 — Donor flow (backend `/api/donors/propose` + DonorPicker for `replace_from_library`)

**Status:** [x] Done
**Depends on:** HTS-101, OP-012 (replace_from_library + DonorEngine)

---

## Goal

Wire the Tier-1 `replace_from_library` op end-to-end:

1. Ship the missing backend route `POST /api/donors/propose` documented in `frontend/src/services/api/donorApi.js` (per UI-008's deferred-items note in `context.md`)
2. Mount `DonorPicker` in `BenchmarkViewerPage.vue` so that clicking `replace_from_library` opens the picker; on Accept, the chosen donor values flow into `invokeOperation(...)` via the standard HTS-101 dispatcher.

`SETSDonor` and `DiscordDonor` are flagged unsupported in the picker today; the route should return `501 Not Implemented` for those backends so the frontend's "coming soon" warning fires correctly. `NativeGuide` and `UserDrawn` are the supported paths.

---

## Acceptance Criteria

- [x] New file `backend/app/routes/donors.py` exposing `POST /api/donors/propose`, registered in `app/routes/__init__.py` *(registered in `factory.py` per existing convention — `app/routes/__init__.py` is empty in this repo)*
- [x] Request payload (per `donorApi.js`): `backend` (string ∈ {`NativeGuide`, `SETSDonor`, `DiscordDonor`, `TimeGAN`, `ShapeDBA`, `UserDrawn`}), `segment_values` (float array), `target_class` (any), `k` (int default 1), `exclude_ids` (string array, default empty) *(also accepts `dataset` to identify the training corpus; donorApi.js extended to forward it)*
- [x] Response payload: `{backend, candidates: [{donor_id, values, distance, metric}, ...]}`
- [x] `NativeGuide` path: instantiate the existing OP-012 `NativeGuide` engine, call its `propose(...)` on the dataset's training corpus, return the top-`k` candidates excluding `exclude_ids`. Pulls training corpus via `DatasetRegistry`. *(Inlines the DTW ranking in the route since the picker walks one candidate at a time via incremented `k` — same engine, same DTW math, just exposes the ranked list rather than only the closest.)*
- [x] `SETSDonor`, `DiscordDonor`, `TimeGAN`, `ShapeDBA`: route returns `501` with a body `{error: "<backend> not yet supported", supported: ["NativeGuide", "UserDrawn"]}`
- [x] `UserDrawn`: route is not called for this backend (frontend bypasses the network and inlines values into the op call); add a guard returning `400` if it is called by mistake
- [x] Pytest coverage in `backend/tests/routes/test_donors.py`: NativeGuide happy path, NativeGuide with `exclude_ids`, NativeGuide with `k>1`, each unsupported backend returns 501, malformed payload returns 400
- [x] Frontend: in `BenchmarkViewerPage.vue`, when `handleOpInvoked` receives `{tier:1, op_name:'replace_from_library'}`, open the `DonorPicker` modal with the selected segment + target class. On Accept, call `invokeOperation` with the chosen `donor_values` + `crossfade_width` in `params`. On Cancel, close the modal and emit no audit event.
- [x] `DonorPicker` cleans up its subscriptions and closes deterministically on Accept / Cancel / Escape
- [x] `npm test` and `npm run build` pass; `pytest backend/tests/routes/test_donors.py` passes

---

## Definition of Done
- [x] Run `tester` agent — all tests pass *(subagent budget exhausted; ran `pytest tests/routes/test_donors.py`: 9/9, `npm test`: 695/695, `npm run build` clean)*
- [x] Run `code-reviewer` agent — no blocking issues *(subagent budget exhausted; self-reviewed against CLAUDE.md — see Result Report)*
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "HTS-104: donor flow (backend route + DonorPicker for replace_from_library)"`

---

## Result Report

**What shipped**

*Backend*
- `backend/app/routes/donors.py` — `POST /api/donors/propose`. Validates payload (backend / segment_values / target_class / dataset / k / exclude_ids), routes by backend: NativeGuide ranks the dataset's training-corpus members of `target_class` by DTW distance to the segment via `tslearn.metrics.dtw`, returns the candidate at offset `k` after removing `exclude_ids`; SETSDonor / DiscordDonor / TimeGAN / ShapeDBA → 501 with `{supported: ['NativeGuide', 'UserDrawn']}`; UserDrawn → 400 (frontend inlines values, never hits this route); malformed payload → 400; unknown dataset → 404.
- `backend/app/factory.py` — register `donors_bp`.
- `backend/app/services/operations/invoke_service.py` — added `_PrebuiltDonorEngine` (a `DonorEngine`-shaped stub that returns the inlined `donor_values` as the donor signal) and `_prepare_replace_from_library_params` (translates the picker's `{backend, donor_id, donor_values, crossfade_width}` into the `donor_engine` + `target_class` kwargs `replace_from_library` expects). Wired into `_dispatch_tier1` so a Tier-1 `replace_from_library` invocation no longer 400s.

*Frontend*
- `frontend/src/services/api/donorApi.js` — `proposeDonor` accepts and forwards an optional `dataset` field.
- `frontend/src/components/donors/DonorPicker.vue` — accepts `dataset` prop, threads it through to `proposeDonor`. Adds a window-level Escape-key listener with `onUnmounted` cleanup.
- `frontend/src/lib/donors/createDonorPickerState.js` — `buildAcceptPayload` now inlines `donor_values` for *every* backend (was UserDrawn-only). The backend `_PrebuiltDonorEngine` reads this directly so the route never needs a server-side donor-id cache.
- `frontend/src/lib/operations/buildInvokeRequest.js` — added `bypassPickerCheck` flag so the page can let `replace_from_library` (and gap-heavy `suppress`) through after the corresponding picker resolves.
- `frontend/src/views/BenchmarkViewerPage.vue` — added `donorPickerOpen` ref and `donorPickerTargetClass` computed; intercept `{tier:1, op_name:'replace_from_library'}` in `handleOpInvoked` to open the picker; mount `<DonorPicker/>` in the chart panel when open; new `handleDonorAccepted` calls `dispatchTier123Op(..., bypassPickerCheck: true)` so the picker's payload sails through `buildInvokeRequest`. `handleDonorPickerClose` just closes (no audit on cancel).
- `frontend/src/lib/operations/buildInvokeRequest.test.js` — 1 new test pinning the `bypassPickerCheck` flag.
- `backend/tests/routes/test_donors.py` — 9 new route tests (happy path, exclude_ids walk, k>1 with empty-list past corpus end, four 501 backends, UserDrawn 400, malformed-payload 400).

**Donor-id-vs-values trade-off (load-bearing)**
The original UI-008 design used `donor_id` as the only handle from picker → invoke (the backend was assumed to keep a per-session cache of proposed donors). This ticket inlines `donor_values` instead so the invoke route is stateless and identical for both NativeGuide and UserDrawn paths. `donor_id` is still passed through for traceability (audit log) but is *not* required for the round-trip to succeed — `_PrebuiltDonorEngine` only reads `donor_values`. Trade-off: the request body grows by ~one segment-length array of floats. Net: no per-session server state, no donor cache to invalidate, exactly one HTTP path for both supported backends.

**Self-review against CLAUDE.md**
- *Routes thin*: `donors.py` is 130 lines — validates, calls `_native_guide_rank`, serialises. The DTW ranking is a small private helper that mirrors NativeGuide's existing math; it's inlined here because the picker needs the *ranked list* (or at least offset-k access), and the production NativeGuide engine only exposes "the closest". No reach into Flask context inside the helper.
- *Domain pure*: `_PrebuiltDonorEngine` lives in the service layer (not the route), satisfies the `DonorEngine` Protocol, no Flask. ✓
- *Frozen DTOs*: not introduced. ✓
- *No fetch in Vue components*: DonorPicker uses `proposeDonor` from `services/api/donorApi.js`. ✓
- *Audit log non-optional*: every accepted donor pick goes through `dispatchTier123Op` → `applyInvokeResponse` → `appendAuditEvent`. Cancel emits no audit (per AC). ✓

**Tests**
- `pytest tests/routes/test_donors.py`: 9/9.
- `npm test`: 695/695 (1 new).
- `npm run build`: 96 modules transformed, 700 ms, 202 kB / 67 kB gzipped.

**Subagent budget**
Subagents (`tester`, `code-reviewer`) remain unavailable. Used direct `pytest` / `npm test` / `npm run build` + the self-review checklist.
