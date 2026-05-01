/**
 * Map an audit event / history entry to the per-signal data the
 * `PlausibilityBadge` consumes (UI-012).
 *
 * The MVP wiring covers what is reachable from the existing event shape:
 *   - residual: pulled from `event.constraintResidual` if it carries
 *     `{ residual, tolerance, law }` keys (OP-032 / UI-010 forward shape).
 *   - range and manifold: not yet emitted by any backend op as of UI-012;
 *     callers may inject them when available.
 *
 * Returns `{ range, residual, manifold }`, each either a plain-object
 * signal payload or `null` (the badge treats `null` as "not evaluated").
 */

export function extractSignalsFromEvent(event) {
  if (!event || typeof event !== 'object') {
    return { range: null, residual: null, manifold: null };
  }

  const cr = event.constraintResidual ?? event.constraint_residual ?? null;
  let residual = null;
  if (cr && typeof cr === 'object' && !Array.isArray(cr)) {
    if (cr.residual != null && Number.isFinite(Number(cr.residual))) {
      residual = {
        residual: Number(cr.residual),
        tolerance: cr.tolerance != null ? Number(cr.tolerance) : null,
        law: cr.law ?? null,
      };
    }
  }

  const range = event.plausibilityRange ?? null;
  const manifold = event.plausibilityManifold ?? null;

  return { range, residual, manifold };
}
