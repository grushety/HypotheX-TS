/**
 * Pure state for the semantic-layer panel (UI-014).
 *
 * The panel lets the user choose an active domain pack
 * (hydrology / seismo-geodesy / remote-sensing) — plus the explicit
 * "None" sentinel that disables the overlay, and a "Custom upload"
 * sentinel that activates a YAML-upload UI.
 *
 * Pack switch is non-destructive: shape primitives stay as-is; only the
 * `semanticLabel` overlay text changes. User-defined labels (per-project
 * overrides) shadow pack labels with the same name — see
 * *Implementation Plan* §8.4.
 */

export const PACK_KIND = Object.freeze({
  NONE: 'none',
  BUILT_IN: 'built-in',
  CUSTOM: 'custom',
});

export const NONE_OPTION_KEY = '__none__';
export const CUSTOM_OPTION_KEY = '__custom__';

export const BUILT_IN_PACK_OPTIONS = Object.freeze([
  { key: 'hydrology', label: 'Hydrology', kind: PACK_KIND.BUILT_IN },
  { key: 'seismo_geodesy', label: 'Seismo-geodesy', kind: PACK_KIND.BUILT_IN },
  { key: 'remote_sensing', label: 'Remote sensing', kind: PACK_KIND.BUILT_IN },
]);

export const NONE_OPTION = Object.freeze({
  key: NONE_OPTION_KEY,
  label: 'None',
  kind: PACK_KIND.NONE,
});

export const CUSTOM_OPTION = Object.freeze({
  key: CUSTOM_OPTION_KEY,
  label: 'Custom upload',
  kind: PACK_KIND.CUSTOM,
});

/**
 * Build the dropdown option list. Built-in packs come from the backend
 * (their `name` field is the user-facing display name and may differ from
 * the file stem — e.g. "seismo-geodesy" vs `seismo_geodesy.yaml`).
 *
 * Returns ``[{ key, label, kind, version?, labelCount? }, ...]``, with
 * "None" and "Custom upload" sentinels appended.
 */
export function buildPackOptions(builtInPacks = []) {
  const fromBackend = builtInPacks.map((pack) => {
    const known = BUILT_IN_PACK_OPTIONS.find(
      (opt) => opt.key === pack.name || opt.key === pack.key,
    );
    return {
      key: known?.key ?? pack.name,
      label: known?.label ?? pack.name,
      kind: PACK_KIND.BUILT_IN,
      version: pack.version ?? null,
      labelCount: Array.isArray(pack.labels) ? pack.labels.length : 0,
    };
  });
  return [...fromBackend, NONE_OPTION, CUSTOM_OPTION];
}

/**
 * Build the info-panel rows: one entry per label declared in the active pack,
 * with shape primitive and a `shadowed` flag for user-overrides.
 *
 * `userOverrides` is a `Map<string, {shape_primitive, source}>` keyed by label
 * name. A label whose name matches a user-override key is marked shadowed.
 */
export function buildInfoPanelRows(activePack, userOverrides = new Map()) {
  if (!activePack || !Array.isArray(activePack.labels)) return [];
  const overrides = userOverrides instanceof Map ? userOverrides : new Map();
  return activePack.labels.map((label) => ({
    name: label.name,
    shape: label.shape_primitive,
    detector: label.detector,
    predicate: label.context_predicate ?? '',
    shadowed: overrides.has(label.name),
    shadowedBy: overrides.get(label.name)?.source ?? null,
  }));
}

/**
 * Map an array of `{segment_id, label, confidence}` results from the backend
 * into a `Map<segment_id, label>` for fast O(1) chip lookup.
 *
 * Null / empty labels are dropped so callers can use `map.has(id)` to
 * distinguish "no detector match" from "match found".
 */
export function buildSegmentLabelMap(labelResults = []) {
  const out = new Map();
  if (!Array.isArray(labelResults)) return out;
  for (const item of labelResults) {
    if (!item || !item.segment_id || !item.label) continue;
    out.set(item.segment_id, {
      label: item.label,
      confidence: Number(item.confidence ?? 0),
    });
  }
  return out;
}

/**
 * Compose the full panel view model.
 *
 * Inputs:
 *   builtInPacks       — backend `GET /api/semantic-packs` payload
 *   activePackKey      — currently selected option key
 *   activePack         — the loaded SemanticPack JSON for `activePackKey`
 *                        (`null` for `None` / unloaded `Custom upload`)
 *   labelResults       — `[{segment_id, label, confidence}, ...]` from
 *                        `POST /api/semantic-packs/label-segments`
 *   customError        — { message, line?, kind } | null  (last upload error)
 *   userOverrides      — Map of user-defined label-name → { shape_primitive, source }
 *
 * Returns:
 *   { options, selectedKey, kind, activePack, infoPanelRows, segmentLabelMap,
 *     hasOverlay, customError }
 */
export function createSemanticLayerState({
  builtInPacks = [],
  activePackKey = NONE_OPTION_KEY,
  activePack = null,
  labelResults = [],
  customError = null,
  userOverrides = new Map(),
} = {}) {
  const options = buildPackOptions(builtInPacks);
  const selectedOption = options.find((o) => o.key === activePackKey) ?? NONE_OPTION;
  const infoPanelRows = buildInfoPanelRows(activePack, userOverrides);
  const segmentLabelMap = buildSegmentLabelMap(labelResults);

  return {
    options,
    selectedKey: selectedOption.key,
    kind: selectedOption.kind,
    activePack,
    infoPanelRows,
    segmentLabelMap,
    hasOverlay: selectedOption.kind !== PACK_KIND.NONE && segmentLabelMap.size > 0,
    customError,
  };
}

/**
 * Annotate a segment array with `semanticLabel` derived from the label map.
 *
 * Non-destructive: shape / id / start / end are preserved, only the new
 * `semanticLabel` field is added (or set to `null` when no match).
 */
export function applySemanticLabelsToSegments(segments, segmentLabelMap) {
  if (!Array.isArray(segments)) return [];
  if (!(segmentLabelMap instanceof Map) || segmentLabelMap.size === 0) {
    return segments.map((seg) => ({ ...seg, semanticLabel: null }));
  }
  return segments.map((seg) => {
    const match = segmentLabelMap.get(seg.id);
    return {
      ...seg,
      semanticLabel: match ? match.label : null,
      semanticConfidence: match ? match.confidence : null,
    };
  });
}
