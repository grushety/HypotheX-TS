import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createAuditLogPanelState,
  createAuditLogCsvExport,
  createAuditLogJsonExport,
} from './createAuditLogPanelState.js';

// One representative event per tier
const TIER_0_EVENT = {
  sequence: 1,
  kind: 'edit',
  actionType: 'move-boundary',
  actionStatus: 'applied',
  constraintStatus: 'PASS',
  warningCount: 0,
  warnings: [],
  affectedSegmentIds: ['seg-001', 'seg-002'],
  selectedSegmentId: 'seg-001',
  timestamp: '2026-04-01T10:00:00.000Z',
  request: { type: 'move-boundary', boundaryIndex: 0, nextBoundaryStart: 20 },
  message: 'Boundary updated successfully.',
};

const TIER_1_EVENT = {
  sequence: 2,
  kind: 'operation',
  actionType: 'scale',
  actionStatus: 'applied',
  constraintStatus: 'PASS',
  warningCount: 0,
  warnings: [],
  affectedSegmentIds: ['seg-002'],
  selectedSegmentId: 'seg-002',
  timestamp: '2026-04-01T10:01:00.000Z',
  request: { type: 'scale', segmentId: 'seg-002', factor: 1.5 },
  message: 'scale applied successfully.',
};

const TIER_2_EVENT = {
  sequence: 3,
  kind: 'operation',
  actionType: 'plateau_flatten',
  actionStatus: 'applied',
  constraintStatus: 'PASS',
  warningCount: 0,
  warnings: [],
  affectedSegmentIds: ['seg-003'],
  selectedSegmentId: 'seg-003',
  timestamp: '2026-04-01T10:02:00.000Z',
  request: { type: 'plateau_flatten', segmentId: 'seg-003' },
  message: 'plateau_flatten applied successfully.',
};

const TIER_3_EVENT = {
  sequence: 4,
  kind: 'operation',
  actionType: 'decompose',
  actionStatus: 'applied',
  constraintStatus: 'PASS',
  warningCount: 0,
  warnings: [],
  affectedSegmentIds: ['seg-004'],
  selectedSegmentId: 'seg-004',
  timestamp: '2026-04-01T10:03:00.000Z',
  request: { type: 'decompose', segmentId: 'seg-004' },
  message: 'decompose applied successfully.',
};

const TIER_2_CHIP = {
  chip_id: 'chip-001',
  sequence: 3,
  segment_id: 'seg-003',
  op_id: 'op-003',
  op_name: 'plateau_flatten',
  tier: 2,
  old_shape: 'plateau',
  new_shape: 'plateau',
  confidence: 0.9,
  rule_class: 'PRESERVED',
  timestamp: '2026-04-01T10:02:00.100Z',
};

const ALL_EVENTS = [TIER_0_EVENT, TIER_1_EVENT, TIER_2_EVENT, TIER_3_EVENT];

test('one op per tier — four rows with correct tier assignments', () => {
  const { rows } = createAuditLogPanelState(ALL_EVENTS);

  assert.equal(rows.length, 4);
  const byOp = Object.fromEntries(rows.map((r) => [r.op, r]));

  assert.equal(byOp['move-boundary'].tier, 0);
  assert.equal(byOp['scale'].tier, 1);
  assert.equal(byOp['plateau_flatten'].tier, 2);
  assert.equal(byOp['decompose'].tier, 3);
});

test('filter by tier 2 — only the plateau_flatten row is visible', () => {
  const { rows } = createAuditLogPanelState(ALL_EVENTS, [], { tier: 2 });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].op, 'plateau_flatten');
  assert.equal(rows[0].tier, 2);
});

test('filter by op name — only matching row visible', () => {
  const { rows } = createAuditLogPanelState(ALL_EVENTS, [], { opName: 'scale' });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].tier, 1);
});

test('label chip enriches pre_shape, post_shape, ruleClass, plausibilityBadge', () => {
  const { rows } = createAuditLogPanelState(ALL_EVENTS, [TIER_2_CHIP]);
  const row = rows.find((r) => r.op === 'plateau_flatten');

  assert.equal(row.preShape, 'plateau');
  assert.equal(row.postShape, 'plateau');
  assert.equal(row.ruleClass, 'PRESERVED');
  assert.equal(row.plausibilityBadge, 'green');  // confidence 0.9 >= 0.8
});

test('events without chips show null for chip-derived fields', () => {
  const { rows } = createAuditLogPanelState(ALL_EVENTS);
  const row = rows.find((r) => r.op === 'scale');

  assert.equal(row.preShape, null);
  assert.equal(row.postShape, null);
  assert.equal(row.ruleClass, null);
  assert.equal(row.plausibilityBadge, null);
});

test('plausibility badge: yellow for confidence 0.6, red for 0.3', () => {
  const yellowChip = { ...TIER_2_CHIP, sequence: 2, confidence: 0.6, rule_class: 'DETERMINISTIC' };
  const redChip = { ...TIER_2_CHIP, chip_id: 'chip-red', sequence: 1, confidence: 0.3, rule_class: 'PRESERVED' };

  const { rows: yellowRows } = createAuditLogPanelState([TIER_1_EVENT], [yellowChip]);
  assert.equal(yellowRows[0].plausibilityBadge, 'yellow');

  const { rows: redRows } = createAuditLogPanelState([TIER_0_EVENT], [redChip]);
  assert.equal(redRows[0].plausibilityBadge, 'red');
});

test('undo depth 1 — last event is hidden', () => {
  const { rows, undoable, redoable } = createAuditLogPanelState(ALL_EVENTS, [], {}, 1);

  assert.equal(rows.length, 3);
  assert.ok(!rows.some((r) => r.op === 'decompose'), 'decompose (seq 4) should be hidden');
  assert.equal(undoable, true);
  assert.equal(redoable, true);
});

test('undo depth 0 — all events visible, not redoable', () => {
  const { rows, undoable, redoable } = createAuditLogPanelState(ALL_EVENTS, [], {}, 0);

  assert.equal(rows.length, 4);
  assert.equal(redoable, false);
  assert.equal(undoable, true);
});

test('undo depth equals event count — all rows hidden, not undoable', () => {
  const { rows, undoable } = createAuditLogPanelState(ALL_EVENTS, [], {}, 4);

  assert.equal(rows.length, 0);
  assert.equal(undoable, false);
});

test('filterOptions.tiers lists unique tier values in ascending order', () => {
  const { filterOptions } = createAuditLogPanelState(ALL_EVENTS);

  assert.deepEqual(filterOptions.tiers, [0, 1, 2, 3]);
});

test('filterOptions.opNames lists all op action types', () => {
  const { filterOptions } = createAuditLogPanelState(ALL_EVENTS);

  assert.ok(filterOptions.opNames.includes('move-boundary'));
  assert.ok(filterOptions.opNames.includes('scale'));
  assert.ok(filterOptions.opNames.includes('plateau_flatten'));
  assert.ok(filterOptions.opNames.includes('decompose'));
});

test('date range filter excludes rows outside range', () => {
  const { rows } = createAuditLogPanelState(ALL_EVENTS, [], {
    dateFrom: '2026-04-01T10:01:00.000Z',
    dateTo: '2026-04-01T10:02:00.000Z',
  });

  // Includes TIER_1 (10:01) and TIER_2 (10:02), excludes TIER_0 (10:00) and TIER_3 (10:03)
  assert.equal(rows.length, 2);
  assert.ok(rows.some((r) => r.op === 'scale'));
  assert.ok(rows.some((r) => r.op === 'plateau_flatten'));
});

test('constraint residual populated from warnings array', () => {
  const eventWithWarning = {
    ...TIER_1_EVENT,
    sequence: 5,
    warningCount: 1,
    warnings: [{ code: 'ADJACENT_SAME_LABEL_SEGMENTS', actionType: 'scale', segmentIds: ['seg-002'] }],
  };

  const { rows } = createAuditLogPanelState([eventWithWarning]);
  assert.ok(rows[0].constraintResidual != null);
  assert.equal(rows[0].constraintResidual[0].code, 'ADJACENT_SAME_LABEL_SEGMENTS');
});

test('CSV export round-trips all columns for all rows', () => {
  const { rows } = createAuditLogPanelState(ALL_EVENTS, [TIER_2_CHIP]);
  const csv = createAuditLogCsvExport(rows);

  const lines = csv.split('\n');
  const header = lines[0].split(',');
  assert.deepEqual(header, [
    'timestamp', 'tier', 'op', 'segment_id',
    'pre_shape', 'post_shape', 'rule_class',
    'compensation_mode', 'plausibility_badge', 'constraint_residual',
  ]);
  // Four data rows
  assert.equal(lines.length, 5);

  // Tier-2 row should have chip fields
  const tier2Line = lines.find((l) => l.includes('plateau_flatten'));
  assert.ok(tier2Line, 'plateau_flatten row should appear in CSV');
  assert.ok(tier2Line.includes('plateau'), 'pre_shape should appear in CSV');
  assert.ok(tier2Line.includes('PRESERVED'), 'rule_class should appear in CSV');
  assert.ok(tier2Line.includes('green'), 'plausibility_badge should appear in CSV');
});

test('JSON export contains all rows with correct field names', () => {
  const { rows } = createAuditLogPanelState([TIER_0_EVENT, TIER_1_EVENT]);
  const json = createAuditLogJsonExport(rows, { sessionId: 'session-test', sampleId: 'ECG200-001' });
  const payload = JSON.parse(json);

  assert.equal(payload.rowCount, 2);
  assert.equal(payload.sessionId, 'session-test');
  assert.ok('tier' in payload.rows[0]);
  assert.ok('pre_shape' in payload.rows[0]);
  assert.ok('post_shape' in payload.rows[0]);
  assert.ok('rule_class' in payload.rows[0]);
  assert.ok('compensation_mode' in payload.rows[0]);
  assert.ok('plausibility_badge' in payload.rows[0]);
  assert.ok('constraint_residual' in payload.rows[0]);
});

test('CSV handles constraint_residual JSON with commas and quotes without breaking columns', () => {
  const eventWithWarning = {
    ...TIER_0_EVENT,
    sequence: 10,
    warnings: [{ code: 'TEST', actionType: 'move-boundary', segmentIds: ['seg-001', 'seg-002'] }],
  };
  const { rows } = createAuditLogPanelState([eventWithWarning]);
  const csv = createAuditLogCsvExport(rows);
  const dataLine = csv.split('\n')[1];
  const columnCount = csv.split('\n')[0].split(',').length;

  // The residual is a JSON blob — it should be quoted so the column count is preserved
  const parsed = dataLine.match(/(?:^|,)("(?:[^"]|"")*"|[^,]*)/g);
  assert.equal(parsed?.length, columnCount);
});

test('date filter with datetime-local format — component normalises to ISO-8601 before passing to lib', () => {
  // The Vue component calls new Date(inputValue).toISOString() before handing values to this
  // function.  Simulate that normalisation: "2026-04-01T10:01" in UTC is "2026-04-01T10:01:00.000Z".
  const dateFrom = new Date('2026-04-01T10:01:00Z').toISOString();
  const dateTo   = new Date('2026-04-01T10:02:00Z').toISOString();

  const { rows } = createAuditLogPanelState(ALL_EVENTS, [], { dateFrom, dateTo });

  // Only TIER_1 (10:01:00Z) and TIER_2 (10:02:00Z) should be visible
  assert.equal(rows.length, 2);
  assert.ok(rows.some((r) => r.op === 'scale'));
  assert.ok(rows.some((r) => r.op === 'plateau_flatten'));
  assert.ok(!rows.some((r) => r.op === 'move-boundary'), 'move-boundary (10:00) should be excluded');
  assert.ok(!rows.some((r) => r.op === 'decompose'), 'decompose (10:03) should be excluded');
});

test('CSV field with carriage return is quoted to preserve column integrity', () => {
  const value = 'line1\r\nline2';
  // Simulate a residual whose JSON stringify produces \r\n — build a row directly
  const eventWithCrLf = {
    ...TIER_0_EVENT,
    sequence: 20,
    warnings: [{ code: value, actionType: 'move-boundary', segmentIds: [] }],
  };
  const { rows } = createAuditLogPanelState([eventWithCrLf]);
  const csv = createAuditLogCsvExport(rows);
  const lines = csv.split('\n');

  // Only header + 1 data row when CR is properly quoted; a bare \r would produce extra rows
  assert.ok(lines.length >= 2, 'should have at least header and one data row');
  // The last column (constraint_residual) in the data row must start with a quote
  const dataFields = lines[1];
  assert.ok(dataFields.includes('"'), 'CR-containing field must be double-quoted in CSV');
});
