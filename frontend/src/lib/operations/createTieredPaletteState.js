import { TIER_0_OPS, TIER_1_OPS, TIER_2_OPS, TIER_3_OPS } from './operationCatalog.js';

export function createTieredPaletteState({
  selectedSegmentIds = [],
  activeShape = null,
  pendingOp = null,
} = {}) {
  const isSingleSelect = selectedSegmentIds.length === 1;
  const isMultiSelect = selectedSegmentIds.length > 1;

  function makeButton(op) {
    const enabled = op.requiresMultiSelect ? isMultiSelect : isSingleSelect;
    return { ...op, enabled, loading: pendingOp === op.op_name };
  }

  const shapeOps = isSingleSelect && activeShape != null ? (TIER_2_OPS[activeShape] ?? []) : [];
  const tier2AllDisabled = isMultiSelect;

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
      buttons: shapeOps.map((op) => ({
        ...op,
        enabled: !tier2AllDisabled,
        loading: pendingOp === op.op_name,
      })),
      disabled: tier2AllDisabled,
      intersectionTooltip: tier2AllDisabled
        ? 'Multiple segments selected — shape-specific ops require a single segment'
        : null,
    },
    tier3: {
      id: 'tier-3',
      label: 'Tier 3: composite',
      buttons: TIER_3_OPS.map(makeButton),
    },
  };
}
