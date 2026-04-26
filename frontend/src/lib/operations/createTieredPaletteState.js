import { TIER_0_OPS, TIER_1_OPS, TIER_2_OPS, TIER_3_OPS } from './operationCatalog.js';
import { createShapeGatingState } from '../viewer/shapeGating.js';

export function createTieredPaletteState({
  selectedSegmentIds = [],
  selectedShapes = [],
  pendingOp = null,
} = {}) {
  const isSingleSelect = selectedSegmentIds.length === 1;
  const isMultiSelect = selectedSegmentIds.length > 1;

  const gating = createShapeGatingState(selectedShapes);

  function makeButton(op) {
    const enabled = op.requiresMultiSelect ? isMultiSelect : isSingleSelect;
    return { ...op, enabled, loading: pendingOp === op.op_name };
  }

  // Build the Tier-2 op list: single-select shows active shape's ops;
  // multi-select shows the union so shape-gating can enable/disable individually.
  let shapeOps = [];
  if (isSingleSelect && selectedShapes.length >= 1) {
    shapeOps = TIER_2_OPS[selectedShapes[0]] ?? [];
  } else if (isMultiSelect && selectedShapes.length > 0) {
    const seen = new Set();
    for (const shape of selectedShapes) {
      for (const op of TIER_2_OPS[shape] ?? []) {
        if (!seen.has(op.op_name)) {
          seen.add(op.op_name);
          shapeOps.push(op);
        }
      }
    }
  }

  const tier2Buttons = shapeOps.map((op) => ({
    ...op,
    enabled: gating.isEnabled(op.op_name),
    loading: pendingOp === op.op_name,
    disabledTooltip: gating.tooltipIfDisabled(op.op_name),
  }));

  const tier2Disabled =
    isMultiSelect &&
    (tier2Buttons.length === 0 || tier2Buttons.every((b) => !b.enabled));

  return {
    tier0: {
      id: 'tier-0',
      label: 'Tier 0: structural',
      buttons: TIER_0_OPS.map(makeButton),
    },
    tier1: {
      id: 'tier-1',
      label: 'Tier 1: basic atoms',
      buttons: TIER_1_OPS.map(makeButton),
    },
    tier2: {
      id: 'tier-2',
      label: 'Tier 2: shape-specific',
      buttons: tier2Buttons,
      disabled: tier2Disabled,
      intersectionTooltip: tier2Disabled
        ? 'Multiple segments selected — no shared shape-specific operations'
        : null,
    },
    tier3: {
      id: 'tier-3',
      label: 'Tier 3: composite',
      buttons: TIER_3_OPS.map(makeButton),
    },
  };
}
