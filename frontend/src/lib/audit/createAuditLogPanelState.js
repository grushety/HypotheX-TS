import { TIER_0_OPS, TIER_1_OPS, TIER_2_OPS, TIER_3_OPS } from '../operations/operationCatalog.js';

const ACTION_TIER = new Map([
  ['move-boundary', 0],
  ['update-label', 0],
  ['edit_boundary', 0],
  ['split', 0],
  ['merge', 0],
  ['reclassify', 0],
]);
for (const op of TIER_0_OPS) ACTION_TIER.set(op.op_name, 0);
for (const op of TIER_1_OPS) ACTION_TIER.set(op.op_name, 1);
for (const group of Object.values(TIER_2_OPS)) {
  for (const op of group) ACTION_TIER.set(op.op_name, 2);
}
for (const op of TIER_3_OPS) ACTION_TIER.set(op.op_name, 3);

function plausibilityFromConfidence(confidence) {
  if (confidence == null) return null;
  if (confidence >= 0.8) return 'green';
  if (confidence >= 0.5) return 'yellow';
  return 'red';
}

function makeRow(event, chip) {
  const tier = chip?.tier ?? ACTION_TIER.get(event.actionType) ?? null;
  return {
    id: `${event.sequence ?? 'pending'}-${event.kind}-${event.actionType}`,
    timestamp: event.timestamp ?? null,
    tier,
    op: event.actionType ?? null,
    segmentId: event.affectedSegmentIds?.[0] ?? event.selectedSegmentId ?? null,
    preShape: chip?.old_shape ?? null,
    postShape: chip?.new_shape ?? null,
    ruleClass: chip?.rule_class ?? null,
    compensationMode: event.request?.compensationMode ?? null,
    plausibilityBadge: plausibilityFromConfidence(chip?.confidence ?? null),
    constraintResidual: event.warnings?.length ? event.warnings : null,
    sequence: event.sequence ?? null,
    actionStatus: event.actionStatus ?? null,
    constraintStatus: event.constraintStatus ?? null,
    kind: event.kind ?? null,
    fullEvent: event,
    fullChip: chip ?? null,
  };
}

function matchesFilters(row, filters) {
  if (filters.tier !== null && filters.tier !== undefined && row.tier !== filters.tier) return false;
  if (filters.ruleClass && row.ruleClass !== filters.ruleClass) return false;
  if (filters.plausibilityBadge && row.plausibilityBadge !== filters.plausibilityBadge) return false;
  if (filters.opName && row.op !== filters.opName) return false;
  if (filters.dateFrom && row.timestamp) {
    if (new Date(row.timestamp) < new Date(filters.dateFrom)) return false;
  }
  if (filters.dateTo && row.timestamp) {
    if (new Date(row.timestamp) > new Date(filters.dateTo)) return false;
  }
  return true;
}

export function createAuditLogPanelState(events = [], labelChips = [], filters = {}, undoDepth = 0) {
  const chipBySequence = new Map();
  for (const chip of labelChips) {
    if (chip.sequence != null) chipBySequence.set(chip.sequence, chip);
  }

  const visibleCount = Math.max(0, events.length - undoDepth);
  const visibleEvents = events.slice(0, visibleCount);

  const allRows = visibleEvents.map((event) => makeRow(event, chipBySequence.get(event.sequence) ?? null));
  const rows = allRows.filter((row) => matchesFilters(row, filters));

  const tiers = [...new Set(allRows.map((r) => r.tier).filter((t) => t != null))].sort((a, b) => a - b);
  const ruleClasses = [...new Set(allRows.map((r) => r.ruleClass).filter(Boolean))];
  const plausibilityBadges = [...new Set(allRows.map((r) => r.plausibilityBadge).filter(Boolean))];
  const opNames = [...new Set(allRows.map((r) => r.op).filter(Boolean))];

  return {
    rows,
    allRows,
    undoable: visibleCount > 0,
    redoable: undoDepth > 0,
    filterOptions: { tiers, ruleClasses, plausibilityBadges, opNames },
  };
}

function csvField(value) {
  if (value == null) return '';
  const str = String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function createAuditLogCsvExport(rows) {
  const headers = [
    'timestamp', 'tier', 'op', 'segment_id',
    'pre_shape', 'post_shape', 'rule_class',
    'compensation_mode', 'plausibility_badge', 'constraint_residual',
  ];
  const lines = [headers.join(',')];
  for (const row of rows) {
    const residual = row.constraintResidual ? JSON.stringify(row.constraintResidual) : '';
    lines.push([
      csvField(row.timestamp),
      csvField(row.tier),
      csvField(row.op),
      csvField(row.segmentId),
      csvField(row.preShape),
      csvField(row.postShape),
      csvField(row.ruleClass),
      csvField(row.compensationMode),
      csvField(row.plausibilityBadge),
      csvField(residual),
    ].join(','));
  }
  return lines.join('\n');
}

export function createAuditLogJsonExport(rows, context = {}) {
  return JSON.stringify(
    {
      schemaVersion: '1.0.0',
      exportedAt: new Date().toISOString(),
      sessionId: context.sessionId ?? null,
      sampleId: context.sampleId ?? null,
      rowCount: rows.length,
      rows: rows.map((row) => ({
        timestamp: row.timestamp,
        tier: row.tier,
        op: row.op,
        segment_id: row.segmentId,
        pre_shape: row.preShape,
        post_shape: row.postShape,
        rule_class: row.ruleClass,
        compensation_mode: row.compensationMode,
        plausibility_badge: row.plausibilityBadge,
        constraint_residual: row.constraintResidual,
      })),
    },
    null,
    2,
  );
}
