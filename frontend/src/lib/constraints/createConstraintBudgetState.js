/**
 * Pure state for the constraint-budget bar (UI-010).
 *
 * Maps a CFResult / ConservationResult residual + tolerance + law name
 * into a view model the UI can render directly:
 *   - status:   'green' | 'amber' | 'red'
 *   - markers:  pre/post fill fractions when compensation_mode != 'naive'
 *   - text:     formatted residual + tolerance + aria-live announcement
 *   - direction: 'improving' | 'worsening' | 'unchanged'
 *
 * Hard / soft law classification mirrors the OP-032 backend:
 *   HARD_LAWS = {phase_closure, nnr_frame}
 *   SOFT_LAWS = {water_balance, moment_balance}
 *
 * Per-law per-component breakdowns are emitted by `buildBreakdown` for
 * the click-to-expand `ConstraintResidualBreakdown` panel.
 */

export const HARD_LAWS = new Set(['phase_closure', 'nnr_frame']);
export const SOFT_LAWS = new Set(['water_balance', 'moment_balance']);

export const DEFAULT_TOLERANCE = Object.freeze({
  water_balance: 1e-6,
  moment_balance: 1e-9,
  phase_closure: 0.1, // rad
  nnr_frame: 1e-9,
});

export const STATUS = Object.freeze({
  GREEN: 'green', // residual within tolerance
  AMBER: 'amber', // soft-law violated
  RED: 'red',     // hard-law violated
});

export const FILL_CAP = 1.5; // saturate the fill bar at 1.5× tolerance

/**
 * Classify a residual against tolerance and law-hardness.
 *
 *   |r| ≤ tolerance              → green
 *   |r| > tolerance, hard law    → red
 *   |r| > tolerance, soft / unknown law → amber
 */
export function classifyResidual(residual, tolerance, law) {
  const absR = Math.abs(Number(residual));
  const tol = Number(tolerance);
  if (!Number.isFinite(absR) || !Number.isFinite(tol)) return STATUS.AMBER;
  if (absR <= tol) return STATUS.GREEN;
  return HARD_LAWS.has(law) ? STATUS.RED : STATUS.AMBER;
}

/**
 * Format a residual for display: scientific notation when |r| < 1e-3,
 * fixed precision otherwise.  Preserves the sign so the user sees an
 * over-budget vs under-budget direction at a glance.
 */
export function formatResidual(residual, units = '') {
  if (residual == null || !Number.isFinite(Number(residual))) return '—';
  const r = Number(residual);
  const abs = Math.abs(r);
  const suffix = units ? ` ${units}` : '';
  if (abs === 0) return `0${suffix}`;
  if (abs >= 1) return `${r.toFixed(3)}${suffix}`;
  if (abs >= 0.001) return `${r.toFixed(4)}${suffix}`;
  return `${r.toExponential(2)}${suffix}`;
}

/**
 * Determine whether the residual got smaller (improving), larger (worsening),
 * or stayed the same after the projection.
 */
export function classifyDirection(initialResidual, finalResidual) {
  const i = Math.abs(Number(initialResidual));
  const f = Math.abs(Number(finalResidual));
  if (!Number.isFinite(i) || !Number.isFinite(f)) return 'unchanged';
  const eps = 1e-15;
  if (Math.abs(i - f) <= eps) return 'unchanged';
  return f < i ? 'improving' : 'worsening';
}

/**
 * Build the budget-bar view model.
 *
 * Inputs accept missing values gracefully — callers may not have a final
 * residual yet (still computing) or may not know the tolerance for an
 * unknown law.
 */
export function createConstraintBudgetState({
  law,
  compensationMode = null,
  initialResidual,
  finalResidual,
  tolerance,
  units = '',
} = {}) {
  const tol = Number(tolerance ?? DEFAULT_TOLERANCE[law] ?? 1e-6);
  const initial = initialResidual != null ? Number(initialResidual) : null;
  const final = finalResidual != null ? Number(finalResidual) : initial;

  const finalAbs = final != null ? Math.abs(final) : 0;
  const initialAbs = initial != null ? Math.abs(initial) : 0;

  const status = classifyResidual(final ?? 0, tol, law);
  const initialStatus = classifyResidual(initial ?? 0, tol, law);

  const showPrePost =
    compensationMode != null &&
    compensationMode !== 'naive' &&
    initial != null &&
    final != null;

  const direction =
    initial != null && final != null
      ? classifyDirection(initial, final)
      : 'unchanged';

  const fillFraction = Math.min(FILL_CAP, finalAbs / Math.max(tol, 1e-300));
  const initialFillFraction = Math.min(FILL_CAP, initialAbs / Math.max(tol, 1e-300));

  const formattedResidual = formatResidual(final, units);
  const formattedInitial = formatResidual(initial, units);
  const formattedTolerance = formatResidual(tol, units);

  const hoverText =
    final == null
      ? `tolerance ${formattedTolerance}`
      : `Δ = ${formattedResidual} (of ${formattedTolerance} tolerance)`;

  const ariaText = showPrePost
    ? `${law}: residual changed from ${formattedInitial} to ${formattedResidual}, ` +
      `tolerance ${formattedTolerance}, status ${status}, ${direction}.`
    : `${law}: residual ${formattedResidual}, tolerance ${formattedTolerance}, status ${status}.`;

  return {
    law,
    compensationMode,
    status,
    initialStatus,
    initial,
    final,
    tolerance: tol,
    fillFraction,
    initialFillFraction,
    showPrePost,
    direction,
    formattedResidual,
    formattedInitial,
    formattedTolerance,
    ariaText,
    hoverText,
    isHardLaw: HARD_LAWS.has(law),
    isSoftLaw: SOFT_LAWS.has(law),
  };
}

/**
 * Per-law component definitions for the breakdown panel.
 *
 * `signs` reflect how each component appears in the law's residual
 * equation (water balance: P − ET − Q − ΔS, so ET / Q / ΔS get −1).
 */
const LAW_BREAKDOWNS = Object.freeze({
  water_balance: {
    keys: ['P', 'ET', 'Q', 'dS'],
    labels: {
      P: 'P (precipitation)',
      ET: 'ET (evapotranspiration)',
      Q: 'Q (runoff)',
      dS: 'ΔS (storage change)',
    },
    signs: { P: +1, ET: -1, Q: -1, dS: -1 },
  },
  moment_balance: {
    keys: ['Mxx', 'Myy', 'Mzz'],
    labels: { Mxx: 'Mxx', Myy: 'Myy', Mzz: 'Mzz' },
    signs: { Mxx: +1, Myy: +1, Mzz: +1 },
  },
  phase_closure: {
    keys: ['phi_12', 'phi_23', 'phi_13'],
    labels: { phi_12: 'φ₁₂', phi_23: 'φ₂₃', phi_13: 'φ₁₃' },
    signs: { phi_12: +1, phi_23: +1, phi_13: -1 },
  },
  nnr_frame: {
    keys: ['omega_x', 'omega_y', 'omega_z'],
    labels: { omega_x: 'ωₓ', omega_y: 'ω_y', omega_z: 'ω_z' },
    signs: { omega_x: +1, omega_y: +1, omega_z: +1 },
  },
});

/**
 * Build the breakdown panel's view model from raw component values.
 *
 * Returns ``{ items, total, law, supported }`` where ``items`` is an
 * array of ``{ key, label, sign, value, signedValue, formatted }`` and
 * ``total`` is the sum of signed contributions (i.e. the residual
 * reconstructed from the components).  ``supported`` is ``false`` for
 * laws not in :data:`LAW_BREAKDOWNS`.
 */
export function buildBreakdown(law, components = {}, units = '') {
  const config = LAW_BREAKDOWNS[law];
  if (!config) {
    return { law, items: [], total: 0, supported: false };
  }

  const items = config.keys
    .filter((k) => components[k] != null && Number.isFinite(Number(components[k])))
    .map((k) => {
      const value = Number(components[k]);
      const sign = config.signs[k];
      const signedValue = sign * value;
      return {
        key: k,
        label: config.labels[k],
        sign,
        value,
        signedValue,
        formatted: formatResidual(value, units),
        formattedSigned: formatResidual(signedValue, units),
      };
    });

  const total = items.reduce((sum, item) => sum + item.signedValue, 0);

  return {
    law,
    items,
    total,
    formattedTotal: formatResidual(total, units),
    supported: true,
  };
}

/**
 * List of laws for which `buildBreakdown` returns a populated result.
 * Useful for the UI to gate the "expand for breakdown" affordance.
 */
export const SUPPORTED_BREAKDOWN_LAWS = Object.freeze(
  Object.keys(LAW_BREAKDOWNS),
);
