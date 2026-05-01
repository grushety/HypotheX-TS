/**
 * Feature flags for the plausibility-badge subsystem (UI-012).
 *
 * The manifold-distance signal needs a trained autoencoder wrapper that the
 * MVP does not yet ship; it is therefore disabled by default. Tests and any
 * future production toggle can read or override the flag here without
 * touching individual call sites.
 */

const DEFAULTS = Object.freeze({
  'plausibility.manifold_ae_enabled': false,
});

const overrides = new Map();

export function getFeatureFlag(name) {
  if (overrides.has(name)) return overrides.get(name);
  return DEFAULTS[name] ?? false;
}

export function setFeatureFlag(name, value) {
  overrides.set(name, value);
}

export function resetFeatureFlags() {
  overrides.clear();
}
