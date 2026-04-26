import { TIER_2_OPS } from '../operations/operationCatalog.js';

/**
 * Authoritative shape → legal Tier-2 op_name list (UI-006).
 * Derived from TIER_2_OPS in operationCatalog.js — single source of truth.
 */
export const SHAPE_GATING_TABLE = Object.fromEntries(
  Object.entries(TIER_2_OPS).map(([shape, ops]) => [shape, ops.map((op) => op.op_name)]),
);

/** Inverse: op_name → shapes that declare it as legal. */
const OP_ELIGIBLE_SHAPES = (() => {
  const map = {};
  for (const [shape, opNames] of Object.entries(SHAPE_GATING_TABLE)) {
    for (const name of opNames) {
      if (!map[name]) map[name] = [];
      map[name].push(shape);
    }
  }
  return map;
})();

/**
 * Compute the set of op_names that are legal for a given list of shapes.
 * Single shape → that shape's ops. Multiple shapes → intersection.
 */
export function computeLegalOps(shapes) {
  if (!shapes || shapes.length === 0) return new Set();
  if (shapes.length === 1) return new Set(SHAPE_GATING_TABLE[shapes[0]] ?? []);
  const sets = shapes.map((s) => new Set(SHAPE_GATING_TABLE[s] ?? []));
  return new Set([...sets[0]].filter((op) => sets.every((s) => s.has(op))));
}

/**
 * Pure factory: returns shape-gating helpers for a given selection of shapes.
 * Call inside Vue computed(() => createShapeGatingState(shapes)) for reactivity.
 */
export function createShapeGatingState(shapes = []) {
  const legalOps = computeLegalOps(shapes);

  function isEnabled(op_name) {
    return legalOps.has(op_name);
  }

  function tooltipIfDisabled(op_name) {
    if (legalOps.has(op_name)) return null;
    if (shapes.length === 0) return null;
    const eligible = OP_ELIGIBLE_SHAPES[op_name] ?? [];
    const activeStr = shapes.join(', ');
    if (eligible.length === 0) return `Not available for ${activeStr}`;
    return `Not available for ${activeStr}; applies to ${eligible.join(', ')}`;
  }

  return { isEnabled, tooltipIfDisabled, legalOps };
}

/**
 * Composable interface described in UI-006.
 * Accepts a plain { shapes } object; wrap with Vue computed for reactivity.
 */
export function useShapeGating(activeSelection) {
  return createShapeGatingState(activeSelection?.shapes ?? []);
}
