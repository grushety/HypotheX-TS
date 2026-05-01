/**
 * Pure state for the compensation-mode selector (UI-011).
 *
 * The selector lets the user pick how OP-051 distributes the residual
 * after a conservation-affecting edit:
 *
 *   naive   — Report residual; do not adjust.
 *   local   — Adjust within this segment only.
 *   coupled — Adjust across all segments via conservation coupling.
 *
 * Defaults mirror the OP-051 backend's `default_compensation_mode_for_domain`
 * table.  In hydrology and seismo-geodesy domains the selector is
 * **required** for value-mutating Tier-2 ops (Plateau / Trend / Step /
 * Transient) — the parent op card must surface the selector and may not
 * let the user submit without confirming a choice.  Required ≠ "the
 * user must pick non-naive": all three modes are still valid; the user
 * just has to tick one rather than skip the affordance.
 */

export const COMPENSATION_MODES = Object.freeze(['naive', 'local', 'coupled']);

export const MODE_TOOLTIPS = Object.freeze({
  naive: 'Report residual; do not adjust',
  local: 'Adjust within this segment only',
  coupled: 'Adjust across all segments via conservation coupling',
});

export const MODE_LABELS = Object.freeze({
  naive: 'Naive',
  local: 'Local',
  coupled: 'Coupled',
});

const _DOMAIN_DEFAULTS = Object.freeze({
  hydrology: 'local',
  'seismo-geodesy': 'coupled',
  seismo_geodesy: 'coupled',
  geodesy: 'coupled',
  'remote-sensing': 'local',
  remote_sensing: 'local',
});

const _REQUIRED_DOMAINS = new Set([
  'hydrology', 'seismo-geodesy', 'seismo_geodesy', 'geodesy',
]);

const _REQUIRED_OP_CATEGORIES = new Set([
  'plateau', 'trend', 'step', 'transient',
]);

/**
 * Resolve the recommended compensation mode for a domain hint.
 *
 * Falls back to `'naive'` for unknown / null domains so the user can
 * still proceed; the selector is unrequired in that case so naive is a
 * sensible default.
 */
export function defaultModeForDomain(domainHint) {
  if (domainHint == null) return 'naive';
  const key = String(domainHint).toLowerCase();
  return _DOMAIN_DEFAULTS[key] ?? 'naive';
}

/**
 * Whether the parent op card MUST surface the selector and require an
 * explicit choice before submission.  True iff
 *   domain ∈ {hydrology, seismo-geodesy} AND op_category ∈ {plateau,
 *   trend, step, transient}.
 */
export function isCompensationRequired(domainHint, opCategory) {
  if (domainHint == null || opCategory == null) return false;
  const d = String(domainHint).toLowerCase();
  const o = String(opCategory).toLowerCase();
  return _REQUIRED_DOMAINS.has(d) && _REQUIRED_OP_CATEGORIES.has(o);
}

export function isValidMode(mode) {
  return COMPENSATION_MODES.includes(mode);
}

/**
 * Build the selector's view model.
 *
 * Inputs accept missing values gracefully — callers may not have a
 * domain hint yet, or may pre-fill `selectedMode` with an explicit user
 * choice.  When `selectedMode` is invalid (or omitted) the resolved
 * `mode` is the domain default.
 *
 * Returned shape:
 *   {
 *     mode:               the effective (resolved) selection
 *     defaultMode:        the per-domain recommendation
 *     isRequired:         the parent must enforce a choice before submit
 *     hasExplicitChoice:  the user has touched the selector
 *     canSubmit:          !isRequired || hasExplicitChoice
 *     choices: [{
 *       mode, label, tooltip, isSelected, isRecommended,
 *     }, ...]
 *   }
 */
export function createCompensationModeSelectorState({
  domainHint = null,
  opCategory = null,
  selectedMode = null,
  hasExplicitChoice = null,
} = {}) {
  const defaultMode = defaultModeForDomain(domainHint);
  const validSelected = isValidMode(selectedMode);
  const explicit =
    hasExplicitChoice != null ? Boolean(hasExplicitChoice) : validSelected;
  const mode = validSelected ? selectedMode : defaultMode;
  const isRequired = isCompensationRequired(domainHint, opCategory);
  const canSubmit = !isRequired || explicit;

  const choices = COMPENSATION_MODES.map((m) => ({
    mode: m,
    label: MODE_LABELS[m],
    tooltip: MODE_TOOLTIPS[m],
    isSelected: m === mode,
    isRecommended: m === defaultMode,
  }));

  return {
    mode,
    defaultMode,
    isRequired,
    hasExplicitChoice: explicit,
    canSubmit,
    choices,
  };
}

/**
 * Cycle the selection by one step in `direction` ∈ {-1, +1}.  Used by
 * the segmented control's ArrowLeft / ArrowRight handler so the user
 * can navigate the radio group from the keyboard.
 */
export function nextMode(currentMode, direction) {
  const idx = COMPENSATION_MODES.indexOf(currentMode);
  const start = idx >= 0 ? idx : 0;
  const dir = direction >= 0 ? 1 : -1;
  const n = COMPENSATION_MODES.length;
  const nextIdx = (start + dir + n) % n;
  return COMPENSATION_MODES[nextIdx];
}
