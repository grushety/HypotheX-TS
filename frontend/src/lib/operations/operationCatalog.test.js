import test from 'node:test';
import assert from 'node:assert/strict';

import { TIER_0_OPS, TIER_1_OPS, TIER_2_OPS, TIER_3_OPS, TIER_LABELS } from './operationCatalog.js';

const ALL_SHAPES = ['plateau', 'trend', 'step', 'spike', 'cycle', 'transient', 'noise'];

test('TIER_0_OPS contains exactly 3 structural ops', () => {
  assert.equal(TIER_0_OPS.length, 3);
  const names = TIER_0_OPS.map((op) => op.op_name);
  assert.ok(names.includes('edit_boundary'));
  assert.ok(names.includes('split'));
  assert.ok(names.includes('merge'));
});

test('TIER_1_OPS contains exactly 9 label-agnostic atom ops', () => {
  assert.equal(TIER_1_OPS.length, 9);
});

test('TIER_1_OPS contains all required atoms', () => {
  const names = new Set(TIER_1_OPS.map((op) => op.op_name));
  for (const name of [
    'scale', 'offset', 'mute_zero', 'time_shift', 'reverse_time',
    'resample', 'suppress', 'replace_from_library', 'add_uncertainty',
  ]) {
    assert.ok(names.has(name), `missing atom: ${name}`);
  }
});

test('TIER_2_OPS covers all 7 shapes', () => {
  assert.deepEqual(new Set(Object.keys(TIER_2_OPS)), new Set(ALL_SHAPES));
});

test('plateau has exactly 5 shape-specific ops', () => {
  assert.equal(TIER_2_OPS.plateau.length, 5);
});

test('cycle has exactly 7 shape-specific ops', () => {
  assert.equal(TIER_2_OPS.cycle.length, 7);
});

test('all other shapes have exactly 5 or 6 ops', () => {
  const counts = { plateau: 5, trend: 6, step: 5, spike: 5, cycle: 7, transient: 5, noise: 5 };
  for (const [shape, expected] of Object.entries(counts)) {
    assert.equal(TIER_2_OPS[shape].length, expected, `${shape}: expected ${expected} ops`);
  }
});

test('TIER_3_OPS contains exactly 4 composite ops', () => {
  assert.equal(TIER_3_OPS.length, 4);
});

test('align_warp has requiresMultiSelect: true', () => {
  const alignWarp = TIER_3_OPS.find((op) => op.op_name === 'align_warp');
  assert.ok(alignWarp, 'align_warp not found in TIER_3_OPS');
  assert.equal(alignWarp.requiresMultiSelect, true);
});

test('no op_name duplicates across tier 0, 1, and 3', () => {
  const names = [
    ...TIER_0_OPS.map((op) => op.op_name),
    ...TIER_1_OPS.map((op) => op.op_name),
    ...TIER_3_OPS.map((op) => op.op_name),
  ];
  assert.equal(names.length, new Set(names).size, 'duplicate op_name found');
});

test('every op has required fields: op_name, label, tier', () => {
  const all = [
    ...TIER_0_OPS,
    ...TIER_1_OPS,
    ...Object.values(TIER_2_OPS).flat(),
    ...TIER_3_OPS,
  ];
  for (const op of all) {
    assert.ok(typeof op.op_name === 'string' && op.op_name.length > 0, `${JSON.stringify(op)} missing op_name`);
    assert.ok(typeof op.label === 'string' && op.label.length > 0, `${op.op_name} missing label`);
    assert.ok(typeof op.tier === 'number', `${op.op_name} missing tier`);
  }
});

test('tier numbers are correct per array', () => {
  for (const op of TIER_0_OPS) assert.equal(op.tier, 0);
  for (const op of TIER_1_OPS) assert.equal(op.tier, 1);
  for (const op of Object.values(TIER_2_OPS).flat()) assert.equal(op.tier, 2);
  for (const op of TIER_3_OPS) assert.equal(op.tier, 3);
});

test('TIER_LABELS has 4 entries matching tier ids', () => {
  assert.equal(TIER_LABELS.length, 4);
  assert.ok(TIER_LABELS[0].includes('0'));
  assert.ok(TIER_LABELS[1].includes('1'));
  assert.ok(TIER_LABELS[2].includes('2'));
  assert.ok(TIER_LABELS[3].includes('3'));
});

test('TIER_LABELS exact strings match expected labels', () => {
  assert.equal(TIER_LABELS[0], 'Tier 0: structural');
  assert.equal(TIER_LABELS[1], 'Tier 1: basic atoms');
  assert.equal(TIER_LABELS[2], 'Tier 2: shape-specific');
  assert.equal(TIER_LABELS[3], 'Tier 3: composite');
});

test('no op_name duplicates across all TIER_2_OPS shapes', () => {
  const all = Object.values(TIER_2_OPS).flat();
  const names = all.map((op) => op.op_name);
  assert.equal(names.length, new Set(names).size, 'duplicate op_name found in TIER_2_OPS');
});

test('TIER_0_OPS every op has an icon field', () => {
  for (const op of TIER_0_OPS) {
    assert.ok(typeof op.icon === 'string' && op.icon.length > 0, `${op.op_name} missing icon`);
  }
});

test('TIER_1_OPS every op has an icon field', () => {
  for (const op of TIER_1_OPS) {
    assert.ok(typeof op.icon === 'string' && op.icon.length > 0, `${op.op_name} missing icon`);
  }
});

test('TIER_3_OPS contains decompose, align_warp, enforce_conservation, aggregate', () => {
  const names = new Set(TIER_3_OPS.map((op) => op.op_name));
  for (const name of ['decompose', 'align_warp', 'enforce_conservation', 'aggregate']) {
    assert.ok(names.has(name), `missing tier3 op: ${name}`);
  }
});

test('only align_warp has requiresMultiSelect in TIER_3_OPS', () => {
  for (const op of TIER_3_OPS) {
    if (op.op_name === 'align_warp') {
      assert.equal(op.requiresMultiSelect, true);
    } else {
      assert.ok(!op.requiresMultiSelect, `${op.op_name} should not have requiresMultiSelect`);
    }
  }
});
