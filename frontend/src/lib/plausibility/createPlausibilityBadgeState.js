/**
 * Pure state for the per-op plausibility traffic-light badge (UI-012).
 *
 * Three signals:
 *   1. Range clipping  — did the edit push values outside the domain's physical range?
 *   2. Residual        — from OP-032 / UI-010 constraint-budget bar.
 *   3. Manifold (AE)   — feature-flagged distance-to-training-manifold (off by default).
 *
 * Combine rule:
 *   red   if any signal red
 *   amber if any signal amber (or unknown) and no red
 *   green if every contributing signal is green
 *
 * Unknown / not-evaluated signals contribute 'amber' so that the badge
 * never claims more confidence than it has. A 'disabled' signal (currently
 * only the manifold one when the feature flag is off) is excluded from
 * combination entirely.
 */

import { classifyResidual, formatResidual, DEFAULT_TOLERANCE } from '../constraints/createConstraintBudgetState.js';

export const STATUS = Object.freeze({
  GREEN: 'green',
  AMBER: 'amber',
  RED: 'red',
  DISABLED: 'disabled',
});

export const FEATURE_FLAG_MANIFOLD_AE = 'plausibility.manifold_ae_enabled';

export const MANIFOLD_AMBER_SIGMA = 1;
export const MANIFOLD_RED_SIGMA = 3;

const PRECEDENCE = { green: 0, amber: 1, red: 2 };

function formatNumber(value) {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  const n = Number(value);
  const abs = Math.abs(n);
  if (abs === 0) return '0';
  if (Number.isInteger(n)) return String(n);
  if (abs >= 1) return n.toFixed(2).replace(/\.?0+$/, '');
  if (abs >= 0.001) return n.toFixed(3).replace(/\.?0+$/, '');
  return n.toExponential(2);
}

/**
 * Evaluate the in-domain range signal.
 *
 * Inputs:
 *   range: { min, max, observedMin, observedMax } | null
 *
 * Status:
 *   green   — observed values lie within [min, max]
 *   red     — any observed value lies outside [min, max]
 *   amber   — range bounds or observed values missing
 */
export function evaluateRangeSignal(range) {
  if (!range || range.min == null || range.max == null) {
    return { status: STATUS.AMBER, text: 'Range: not evaluated' };
  }
  const min = Number(range.min);
  const max = Number(range.max);
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return { status: STATUS.AMBER, text: 'Range: not evaluated' };
  }

  const obsMin = range.observedMin != null ? Number(range.observedMin) : null;
  const obsMax = range.observedMax != null ? Number(range.observedMax) : null;
  if (
    obsMin == null ||
    obsMax == null ||
    !Number.isFinite(obsMin) ||
    !Number.isFinite(obsMax)
  ) {
    return {
      status: STATUS.AMBER,
      text: `Range: bounds [${formatNumber(min)}, ${formatNumber(max)}], observation unknown`,
    };
  }

  const minBounds = `[${formatNumber(min)}, ${formatNumber(max)}]`;
  if (obsMin >= min && obsMax <= max) {
    return { status: STATUS.GREEN, text: `Range: within ${minBounds}` };
  }

  const overUnder = [];
  if (obsMax > max) overUnder.push(`exceeds max by ${formatNumber(obsMax - max)}`);
  if (obsMin < min) overUnder.push(`below min by ${formatNumber(min - obsMin)}`);
  return {
    status: STATUS.RED,
    text: `Range: ${overUnder.join(', ')} (bounds ${minBounds})`,
  };
}

/**
 * Evaluate the conservation-residual signal (UI-010 / OP-032).
 *
 * Inputs:
 *   residual: { residual, tolerance, law } | null
 *
 * Reuses the budget-bar's classifier — green if |r| ≤ tolerance, otherwise
 * red for hard laws / amber for soft or unknown laws.
 */
export function evaluateResidualSignal(residual) {
  if (!residual || residual.residual == null) {
    return { status: STATUS.AMBER, text: 'Residual: not evaluated' };
  }
  const r = Number(residual.residual);
  if (!Number.isFinite(r)) {
    return { status: STATUS.AMBER, text: 'Residual: not evaluated' };
  }
  const tol = Number(
    residual.tolerance ?? DEFAULT_TOLERANCE[residual.law] ?? 1e-6,
  );
  const status = classifyResidual(r, tol, residual.law);
  return {
    status,
    text: `Residual: ${formatResidual(r)} / tolerance ${formatResidual(tol)}`,
  };
}

/**
 * Evaluate the AE-manifold-distance signal.
 *
 * Inputs:
 *   manifold:        { sigma } | null
 *   manifoldEnabled: bool (feature flag `plausibility.manifold_ae_enabled`)
 *
 * Distance-to-manifold is reported in σ units (z-score against the training
 * distribution): ≤1σ green, ≤3σ amber, >3σ red. Disabled = excluded from
 * the combine rule.
 */
export function evaluateManifoldSignal(manifold, manifoldEnabled = false) {
  if (!manifoldEnabled) {
    return { status: STATUS.DISABLED, text: 'Manifold: disabled' };
  }
  if (!manifold || manifold.sigma == null || !Number.isFinite(Number(manifold.sigma))) {
    return { status: STATUS.AMBER, text: 'Manifold: not evaluated' };
  }
  const sigma = Number(manifold.sigma);
  const text = `Manifold: ${sigma.toFixed(1)}σ`;
  if (Math.abs(sigma) <= MANIFOLD_AMBER_SIGMA) return { status: STATUS.GREEN, text };
  if (Math.abs(sigma) <= MANIFOLD_RED_SIGMA) return { status: STATUS.AMBER, text };
  return { status: STATUS.RED, text };
}

/**
 * Combine per-signal statuses into a single badge status.
 *
 * Disabled signals are excluded. Among remaining signals: red wins, then
 * amber, then green. If no signals remain (all disabled), the badge is
 * green — there's nothing to flag.
 */
export function combineSignals(signals) {
  let worst = STATUS.GREEN;
  let contributing = 0;
  for (const sig of signals) {
    if (!sig || sig.status === STATUS.DISABLED) continue;
    contributing += 1;
    if (PRECEDENCE[sig.status] > PRECEDENCE[worst]) worst = sig.status;
  }
  return contributing === 0 ? STATUS.GREEN : worst;
}

/**
 * Build the badge view model from raw per-signal data.
 *
 * Returns:
 *   {
 *     status,                 // 'green' | 'amber' | 'red'
 *     signals: { range, residual, manifold }, each { status, text }
 *     ariaLabel,              // accessibility label for the badge
 *     hoverText,              // multi-line per-signal breakdown
 *     glyph,                  // ✓ / ! / ✗ — non-colour state cue
 *   }
 */
export function createPlausibilityBadgeState({
  range = null,
  residual = null,
  manifold = null,
  manifoldEnabled = false,
} = {}) {
  const rangeSig = evaluateRangeSignal(range);
  const residualSig = evaluateResidualSignal(residual);
  const manifoldSig = evaluateManifoldSignal(manifold, manifoldEnabled);

  const status = combineSignals([rangeSig, residualSig, manifoldSig]);

  const hoverText = [rangeSig.text, residualSig.text, manifoldSig.text].join('\n');

  const ariaLabel = `Plausibility ${status}. ${rangeSig.text}. ${residualSig.text}. ${manifoldSig.text}.`;

  const glyph = status === STATUS.GREEN ? '✓' : status === STATUS.RED ? '✗' : '!';

  return {
    status,
    signals: { range: rangeSig, residual: residualSig, manifold: manifoldSig },
    ariaLabel,
    hoverText,
    glyph,
  };
}
