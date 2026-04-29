/**
 * Pure state logic for the predicted new-label chip (UI-013).
 *
 * createLabelChipDisplayModel — converts a raw LabelChip event (from OP-041)
 * into a view-ready display model:
 *   - Formatted display text
 *   - Low-confidence RECLASSIFY detection → orange-border flag + auto-focus
 *   - Passes through ids needed for Accept / Undo
 *
 * tickTimer — pure function of elapsed time; returns the countdown fraction
 * and a `fired` flag. Vue component calls this on every interval tick.
 */

export const LOW_CONFIDENCE_THRESHOLD = 0.70;
export const DEFAULT_ACCEPT_TIMER_SECONDS = 5;
export const TIMER_TICK_MS = 50;

/**
 * @param {object} chip  LabelChip from OP-041
 *   { chip_id, segment_id, op_id, op_name, tier, old_shape,
 *     new_shape, confidence, rule_class, timestamp }
 * @returns {object} display model
 */
export function createLabelChipDisplayModel(chip) {
  if (!chip || typeof chip !== 'object') {
    return null;
  }

  const confidence = chip.confidence ?? 0;
  const confidencePct = Math.round(confidence * 100);
  const ruleClass = chip.rule_class ?? '';
  const isReclassify = ruleClass === 'RECLASSIFY_VIA_SEGMENTER';
  const isLowConfidence = confidence < LOW_CONFIDENCE_THRESHOLD;
  const isLowConfidenceReclassify = isReclassify && isLowConfidence;

  return {
    chipId: chip.chip_id ?? null,
    segmentId: chip.segment_id ?? null,
    opId: chip.op_id ?? null,
    opName: chip.op_name ?? null,
    tier: chip.tier ?? null,
    oldShape: chip.old_shape ?? null,
    newShape: chip.new_shape ?? null,
    confidencePct,
    ruleClass,
    displayText: `${chip.old_shape ?? '?'} → ${chip.new_shape ?? '?'}  (${confidencePct}%)  [${ruleClass}]`,
    isPreserved: ruleClass === 'PRESERVED',
    isDeterministic: ruleClass === 'DETERMINISTIC',
    isReclassify,
    isLowConfidenceReclassify,
    shouldAutoFocusOverride: isLowConfidenceReclassify,
    timestamp: chip.timestamp ?? null,
  };
}

/**
 * Pure timer tick: call on each interval to get countdown progress.
 *
 * @param {number} acceptTimerMs  Total timer duration in ms
 * @param {number} elapsedMs      Time elapsed since chip appeared
 * @returns {{ fraction: number, fired: boolean, remainingMs: number }}
 */
export function tickTimer(acceptTimerMs, elapsedMs) {
  if (acceptTimerMs <= 0) return { fraction: 1, fired: true, remainingMs: 0 };
  const bounded = Math.max(0, elapsedMs);
  const fraction = Math.min(bounded / acceptTimerMs, 1);
  const remainingMs = Math.max(0, acceptTimerMs - bounded);
  return { fraction, fired: bounded >= acceptTimerMs, remainingMs };
}
