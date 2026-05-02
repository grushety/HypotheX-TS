/**
 * Pure state for the per-segment scope-attribute editor (UI-018).
 *
 * The ``scope`` attribute on a segment is a small dict carrying:
 *   - ``domain_hint``  — pack name; consulted by SEG-019's fitter dispatcher
 *                        and SEG-008 for domain-aware classification
 *   - ``window_size``  — positive integer (samples) framing the segment
 *                        for cycle-vs-transient disambiguation
 *   - ``mode``         — ``'fixed' | 'sliding'``
 *   - ``reference``    — anchor time for fixed mode (ISO-8601 string or
 *                        numeric sample index); ignored for sliding mode
 *
 * Editing scope is non-destructive on values — it triggers OP-040
 * ``RECLASSIFY_VIA_SEGMENTER`` on the segment and emits a ``scope-updated``
 * event that the parent forwards to the backend.
 *
 * Cross-references
 * ----------------
 * - Domain pack defaults match the SEG-021/22/23 conventions so that
 *   "inherit from project" produces sensible per-pack windows:
 *     hydrology      → sliding, 30 samples (≈ 1 month if daily)
 *     seismo-geodesy → fixed, no default reference (user picks)
 *     remote-sensing → sliding, 365 samples (≈ 1 year if daily)
 *     other / null   → sliding, 30 samples
 */

export const DOMAIN_HINTS = Object.freeze([
  'hydrology',
  'seismo-geodesy',
  'remote-sensing',
  'other',
]);

export const INHERIT_DOMAIN_KEY = 'inherit';

export const DOMAIN_HINT_OPTIONS = Object.freeze([
  { key: INHERIT_DOMAIN_KEY, label: 'Inherit from project' },
  { key: 'hydrology', label: 'Hydrology' },
  { key: 'seismo-geodesy', label: 'Seismo-geodesy' },
  { key: 'remote-sensing', label: 'Remote sensing' },
  { key: 'other', label: 'Other' },
]);

export const SCOPE_MODES = Object.freeze(['fixed', 'sliding']);
export const DEFAULT_SCOPE_MODE = 'sliding';
export const DEFAULT_WINDOW_SIZE = 30;

export const VALIDATION_ERRORS = Object.freeze({
  WINDOW_NON_POSITIVE: 'Window size must be a positive integer.',
  WINDOW_NOT_INTEGER: 'Window size must be a whole number of samples.',
  WINDOW_EXCEEDS_SERIES: 'Window size cannot exceed the series length.',
  REFERENCE_REQUIRED: 'Fixed scope mode requires a reference time.',
  MODE_UNKNOWN: 'Scope mode must be either "fixed" or "sliding".',
});

/**
 * Default scope for the given domain hint, used when "Inherit from project"
 * is the dropdown choice or when seeding a fresh editor.
 *
 * Returns a frozen plain object the caller can spread into a scope dict.
 */
export function defaultScopeForDomain(domainHint) {
  switch (domainHint) {
    case 'hydrology':
      return Object.freeze({
        domain_hint: 'hydrology',
        window_size: 30,
        mode: 'sliding',
        reference: null,
      });
    case 'seismo-geodesy':
      return Object.freeze({
        domain_hint: 'seismo-geodesy',
        window_size: DEFAULT_WINDOW_SIZE,
        mode: 'fixed',
        reference: null, // user picks origin time
      });
    case 'remote-sensing':
      return Object.freeze({
        domain_hint: 'remote-sensing',
        window_size: 365,
        mode: 'sliding',
        reference: null,
      });
    default:
      return Object.freeze({
        domain_hint: domainHint ?? null,
        window_size: DEFAULT_WINDOW_SIZE,
        mode: DEFAULT_SCOPE_MODE,
        reference: null,
      });
  }
}

/**
 * Validate a scope draft against the segment / series constraints.
 *
 * Returns ``{ok, errors}`` where ``errors`` is an object keyed by field
 * name (``window_size`` | ``mode`` | ``reference``) with the first failing
 * message per field; ``ok = true`` only when all fields validate.
 */
export function validateScope({
  windowSize,
  mode,
  reference,
  seriesLength = null,
} = {}) {
  const errors = {};

  if (windowSize == null || !Number.isFinite(Number(windowSize))) {
    errors.window_size = VALIDATION_ERRORS.WINDOW_NON_POSITIVE;
  } else {
    const n = Number(windowSize);
    if (!Number.isInteger(n)) {
      errors.window_size = VALIDATION_ERRORS.WINDOW_NOT_INTEGER;
    } else if (n <= 0) {
      errors.window_size = VALIDATION_ERRORS.WINDOW_NON_POSITIVE;
    } else if (
      seriesLength != null &&
      Number.isFinite(Number(seriesLength)) &&
      n > Number(seriesLength)
    ) {
      errors.window_size = VALIDATION_ERRORS.WINDOW_EXCEEDS_SERIES;
    }
  }

  if (mode == null || !SCOPE_MODES.includes(mode)) {
    errors.mode = VALIDATION_ERRORS.MODE_UNKNOWN;
  }

  if (mode === 'fixed' && (reference == null || reference === '')) {
    errors.reference = VALIDATION_ERRORS.REFERENCE_REQUIRED;
  }

  return { ok: Object.keys(errors).length === 0, errors };
}

/**
 * Resolve the "inherit" sentinel back to the project's domain hint.
 *
 * Used when serialising the dropdown selection into the scope dict — the
 * sentinel ``'inherit'`` is UI-only and never sent to the backend.
 */
export function resolveDomainHint(selectedKey, projectDomainHint = null) {
  if (selectedKey === INHERIT_DOMAIN_KEY) return projectDomainHint;
  if (DOMAIN_HINTS.includes(selectedKey)) return selectedKey;
  return null;
}

/**
 * Build the ``scope-updated`` event payload emitted on Save.
 *
 * Shape:
 *   {
 *     segmentId: string,
 *     scope: { domain_hint, window_size, mode, reference },
 *     previousScope: <whatever the segment had, or null>,
 *     triggerReclassify: true,   // OP-040 RECLASSIFY_VIA_SEGMENTER
 *   }
 *
 * The parent component is responsible for forwarding to the backend.
 */
export function buildScopeUpdatePayload({
  segmentId,
  draft,
  previousScope = null,
  projectDomainHint = null,
}) {
  if (!segmentId) {
    throw new Error('buildScopeUpdatePayload requires segmentId.');
  }
  const scope = {
    domain_hint: resolveDomainHint(draft.domainHintKey, projectDomainHint),
    window_size: Number(draft.windowSize),
    mode: draft.mode,
    reference: draft.mode === 'fixed' ? draft.reference ?? null : null,
  };
  return Object.freeze({
    segmentId,
    scope,
    previousScope,
    triggerReclassify: true,
  });
}

/**
 * Compose the editor view model from raw inputs.
 *
 * Inputs:
 *   segment            — { id, scope?: {...} }
 *   seriesLength       — for window-size upper-bound validation
 *   draft              — { windowSize, mode, reference, domainHintKey }
 *   projectDomainHint  — fallback used when "inherit" is selected
 *
 * Returns a frozen view model the dialog can render directly.
 */
export function createScopeEditorState({
  segment = null,
  seriesLength = null,
  draft = null,
  projectDomainHint = null,
} = {}) {
  const previousScope = segment?.scope ?? null;
  const draftSafe = draft ?? draftFromScope(previousScope, projectDomainHint);
  const validation = validateScope({
    windowSize: draftSafe.windowSize,
    mode: draftSafe.mode,
    reference: draftSafe.reference,
    seriesLength,
  });

  return Object.freeze({
    segmentId: segment?.id ?? null,
    options: DOMAIN_HINT_OPTIONS,
    scopeModes: SCOPE_MODES,
    draft: Object.freeze({ ...draftSafe }),
    previousScope,
    validation,
    canSave: validation.ok && segment?.id != null,
    isFixedMode: draftSafe.mode === 'fixed',
  });
}

/**
 * Seed the editor draft from an existing scope (or a domain default when
 * the segment has no scope yet).  Always emits a ``domainHintKey`` that
 * matches a dropdown option, including the ``inherit`` sentinel.
 */
export function draftFromScope(scope, projectDomainHint = null) {
  if (!scope) {
    const seed = defaultScopeForDomain(projectDomainHint ?? null);
    return {
      windowSize: seed.window_size,
      mode: seed.mode,
      reference: seed.reference,
      domainHintKey: INHERIT_DOMAIN_KEY,
    };
  }
  const hint = scope.domain_hint ?? null;
  const domainHintKey = DOMAIN_HINTS.includes(hint) ? hint : INHERIT_DOMAIN_KEY;
  return {
    windowSize: scope.window_size ?? DEFAULT_WINDOW_SIZE,
    mode: SCOPE_MODES.includes(scope.mode) ? scope.mode : DEFAULT_SCOPE_MODE,
    reference: scope.reference ?? null,
    domainHintKey,
  };
}
