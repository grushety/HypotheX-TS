import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  BUILT_IN_PACK_OPTIONS,
  CUSTOM_OPTION_KEY,
  NONE_OPTION_KEY,
  PACK_KIND,
  applySemanticLabelsToSegments,
  buildInfoPanelRows,
  buildPackOptions,
  buildSegmentLabelMap,
  createSemanticLayerState,
} from './createSemanticLayerState.js';

describe('buildPackOptions', () => {
  it('adds None and Custom upload sentinels at the end', () => {
    const options = buildPackOptions([]);
    assert.equal(options.length, 2);
    assert.equal(options[0].key, NONE_OPTION_KEY);
    assert.equal(options[1].key, CUSTOM_OPTION_KEY);
  });

  it('maps known backend pack names to display labels', () => {
    const options = buildPackOptions([
      { name: 'hydrology', version: '1.0', labels: [{ name: 'baseflow' }] },
      { name: 'seismo_geodesy', version: '1.0', labels: [] },
      { name: 'remote_sensing', version: '1.0', labels: [] },
    ]);
    const keys = options.map((o) => o.key);
    assert.deepEqual(keys.slice(0, 3), ['hydrology', 'seismo_geodesy', 'remote_sensing']);
    const hydrology = options.find((o) => o.key === 'hydrology');
    assert.equal(hydrology.label, 'Hydrology');
    assert.equal(hydrology.kind, PACK_KIND.BUILT_IN);
    assert.equal(hydrology.labelCount, 1);
  });

  it('preserves an unknown backend pack name as the label', () => {
    const options = buildPackOptions([{ name: 'paleo-climate', version: '0.1', labels: [] }]);
    const custom = options.find((o) => o.key === 'paleo-climate');
    assert.ok(custom);
    assert.equal(custom.label, 'paleo-climate');
  });
});

describe('buildInfoPanelRows', () => {
  const pack = {
    name: 'hydrology',
    labels: [
      { name: 'baseflow', shape_primitive: 'plateau', detector: 'eckhardt_baseflow', context_predicate: '' },
      { name: 'peak_flow', shape_primitive: 'spike', detector: 'hampel_peak', context_predicate: 'peak_Q > 5' },
    ],
  };

  it('returns one row per label with shape and detector', () => {
    const rows = buildInfoPanelRows(pack);
    assert.equal(rows.length, 2);
    assert.equal(rows[0].name, 'baseflow');
    assert.equal(rows[0].shape, 'plateau');
    assert.equal(rows[0].detector, 'eckhardt_baseflow');
    assert.equal(rows[0].shadowed, false);
    assert.equal(rows[1].predicate, 'peak_Q > 5');
  });

  it('marks rows shadowed when a user override matches the label name', () => {
    const overrides = new Map([
      ['baseflow', { shape_primitive: 'plateau', source: 'project-override' }],
    ]);
    const rows = buildInfoPanelRows(pack, overrides);
    const baseflow = rows.find((r) => r.name === 'baseflow');
    assert.equal(baseflow.shadowed, true);
    assert.equal(baseflow.shadowedBy, 'project-override');
    const peak = rows.find((r) => r.name === 'peak_flow');
    assert.equal(peak.shadowed, false);
  });

  it('returns an empty array for null pack', () => {
    assert.deepEqual(buildInfoPanelRows(null), []);
  });
});

describe('buildSegmentLabelMap', () => {
  it('returns an empty map for empty input', () => {
    assert.equal(buildSegmentLabelMap([]).size, 0);
    assert.equal(buildSegmentLabelMap(null).size, 0);
  });

  it('drops null-label entries', () => {
    const m = buildSegmentLabelMap([
      { segment_id: 'a', label: 'baseflow', confidence: 0.9 },
      { segment_id: 'b', label: null, confidence: 0 },
    ]);
    assert.equal(m.size, 1);
    assert.equal(m.get('a').label, 'baseflow');
    assert.equal(m.get('a').confidence, 0.9);
    assert.equal(m.has('b'), false);
  });
});

describe('createSemanticLayerState', () => {
  const builtInPacks = [
    { name: 'hydrology', version: '1.0', labels: [{ name: 'baseflow', shape_primitive: 'plateau' }] },
  ];

  it('selects None by default and reports no overlay', () => {
    const state = createSemanticLayerState({ builtInPacks });
    assert.equal(state.selectedKey, NONE_OPTION_KEY);
    assert.equal(state.kind, PACK_KIND.NONE);
    assert.equal(state.hasOverlay, false);
    assert.equal(state.infoPanelRows.length, 0);
  });

  it('exposes info-panel rows for the active pack', () => {
    const state = createSemanticLayerState({
      builtInPacks,
      activePackKey: 'hydrology',
      activePack: builtInPacks[0],
    });
    assert.equal(state.kind, PACK_KIND.BUILT_IN);
    assert.equal(state.infoPanelRows.length, 1);
    assert.equal(state.infoPanelRows[0].name, 'baseflow');
  });

  it('reports hasOverlay=true when label results exist for the active pack', () => {
    const state = createSemanticLayerState({
      builtInPacks,
      activePackKey: 'hydrology',
      activePack: builtInPacks[0],
      labelResults: [{ segment_id: 's1', label: 'baseflow', confidence: 0.7 }],
    });
    assert.equal(state.hasOverlay, true);
    assert.equal(state.segmentLabelMap.get('s1').label, 'baseflow');
  });

  it('falls back to None when the activePackKey is unknown', () => {
    const state = createSemanticLayerState({
      builtInPacks,
      activePackKey: 'no-such',
    });
    assert.equal(state.selectedKey, NONE_OPTION_KEY);
  });

  it('forwards the customError', () => {
    const state = createSemanticLayerState({
      builtInPacks,
      activePackKey: CUSTOM_OPTION_KEY,
      customError: { message: 'bad', line: 4, kind: 'yaml' },
    });
    assert.equal(state.kind, PACK_KIND.CUSTOM);
    assert.equal(state.customError.line, 4);
  });
});

describe('applySemanticLabelsToSegments', () => {
  const segments = [
    { id: 's1', label: 'plateau', start: 0, end: 10 },
    { id: 's2', label: 'spike', start: 11, end: 12 },
  ];

  it('attaches semanticLabel from the map without mutating shape', () => {
    const map = new Map([
      ['s1', { label: 'baseflow', confidence: 0.8 }],
    ]);
    const out = applySemanticLabelsToSegments(segments, map);
    assert.equal(out[0].label, 'plateau');
    assert.equal(out[0].semanticLabel, 'baseflow');
    assert.equal(out[0].semanticConfidence, 0.8);
    assert.equal(out[1].semanticLabel, null);
  });

  it('sets semanticLabel to null when the map is empty', () => {
    const out = applySemanticLabelsToSegments(segments, new Map());
    assert.equal(out[0].semanticLabel, null);
    assert.equal(out[1].semanticLabel, null);
  });

  it('preserves original segment fields', () => {
    const map = new Map([['s1', { label: 'baseflow', confidence: 1 }]]);
    const out = applySemanticLabelsToSegments(segments, map);
    assert.equal(out[0].id, 's1');
    assert.equal(out[0].start, 0);
    assert.equal(out[0].end, 10);
  });
});

describe('module exports', () => {
  it('exposes the canonical built-in pack option list', () => {
    assert.equal(BUILT_IN_PACK_OPTIONS.length, 3);
    assert.deepEqual(
      BUILT_IN_PACK_OPTIONS.map((p) => p.key),
      ['hydrology', 'seismo_geodesy', 'remote_sensing'],
    );
  });
});
