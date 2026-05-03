# HTS-104 — Donor flow (backend `/api/donors/propose` + DonorPicker for `replace_from_library`)

**Status:** [ ] Done
**Depends on:** HTS-101, OP-012 (replace_from_library + DonorEngine)

---

## Goal

Wire the Tier-1 `replace_from_library` op end-to-end:

1. Ship the missing backend route `POST /api/donors/propose` documented in `frontend/src/services/api/donorApi.js` (per UI-008's deferred-items note in `context.md`)
2. Mount `DonorPicker` in `BenchmarkViewerPage.vue` so that clicking `replace_from_library` opens the picker; on Accept, the chosen donor values flow into `invokeOperation(...)` via the standard HTS-101 dispatcher.

`SETSDonor` and `DiscordDonor` are flagged unsupported in the picker today; the route should return `501 Not Implemented` for those backends so the frontend's "coming soon" warning fires correctly. `NativeGuide` and `UserDrawn` are the supported paths.

---

## Acceptance Criteria

- [ ] New file `backend/app/routes/donors.py` exposing `POST /api/donors/propose`, registered in `app/routes/__init__.py`
- [ ] Request payload (per `donorApi.js`): `backend` (string ∈ {`NativeGuide`, `SETSDonor`, `DiscordDonor`, `TimeGAN`, `ShapeDBA`, `UserDrawn`}), `segment_values` (float array), `target_class` (any), `k` (int default 1), `exclude_ids` (string array, default empty)
- [ ] Response payload: `{backend, candidates: [{donor_id, values, distance, metric}, ...]}`
- [ ] `NativeGuide` path: instantiate the existing OP-012 `NativeGuide` engine, call its `propose(...)` on the dataset's training corpus, return the top-`k` candidates excluding `exclude_ids`. Pulls training corpus via `DatasetRegistry`.
- [ ] `SETSDonor`, `DiscordDonor`, `TimeGAN`, `ShapeDBA`: route returns `501` with a body `{error: "<backend> not yet supported", supported: ["NativeGuide", "UserDrawn"]}`
- [ ] `UserDrawn`: route is not called for this backend (frontend bypasses the network and inlines values into the op call); add a guard returning `400` if it is called by mistake
- [ ] Pytest coverage in `backend/tests/routes/test_donors.py`: NativeGuide happy path, NativeGuide with `exclude_ids`, NativeGuide with `k>1`, each unsupported backend returns 501, malformed payload returns 400
- [ ] Frontend: in `BenchmarkViewerPage.vue`, when `handleOpInvoked` receives `{tier:1, op_name:'replace_from_library'}`, open the `DonorPicker` modal with the selected segment + target class. On Accept, call `invokeOperation` with the chosen `donor_values` + `crossfade_width` in `params`. On Cancel, close the modal and emit no audit event.
- [ ] `DonorPicker` cleans up its subscriptions and closes deterministically on Accept / Cancel / Escape
- [ ] `npm test` and `npm run build` pass; `pytest backend/tests/routes/test_donors.py` passes

---

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "HTS-104: donor flow (backend route + DonorPicker for replace_from_library)"`
