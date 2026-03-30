# Pilot Readiness Note

`HTS-602` formalizes the first pilot-ready comparison setup without changing runtime product behavior.

Chosen comparison conditions:

- `semantic-interface`: full semantic workflow, including optional suggestion review.
- `rule-only-baseline`: semantic editing with constraint feedback but without using the suggestion workflow.

Why the rule-only baseline is used now:

- It is already fully supported by the shipped system.
- It produces comparable session exports with the current audit schema.
- It avoids inventing a partially instrumented raw-waveform baseline before pilot telemetry is stable.

Telemetry status from the current export schema:

- Supported now:
  - session duration
  - operation diversity
  - constraint feedback rate
  - suggestion uptake or override rate
  - target-segment coverage from logged IDs
- Explicitly missing today:
  - `conditionId`
  - `participantId`
  - `taskId`
  - `taskOutcome`
  - `taskCompletedAt`

Implications:

- Internal pilot comparisons are feasible if condition and participant metadata are attached externally.
- Later study-ready exports should add explicit condition and task metadata rather than relying on file naming or manual notebooks.

Pilot scenario pack:

- Boundary cleanup on GunPoint
- Suggestion review and override
- Constraint-limited merge decision

Recommended next study-prep step:

- Add explicit condition and task identifiers to the exported session log before any formal participant data collection begins.
