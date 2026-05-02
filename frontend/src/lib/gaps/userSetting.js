/**
 * User-setting persistence for ``gap.dense_ops_threshold_pct`` (UI-017).
 *
 * Stored in sessionStorage so the user's threshold survives page reloads
 * within a tab but doesn't leak across tabs / users.  The persisted value
 * is always clamped into the legal [0, 100] range on read so a manually-
 * tampered storage entry can't disable the gating subsystem entirely.
 */

import {
  DEFAULT_DENSE_OPS_THRESHOLD_PCT,
  clampThresholdPct,
} from './createGapGatingState.js';

const STORAGE_KEY = 'hypothex-ts.gap.dense_ops_threshold_pct.v1';

function getStorage() {
  if (typeof globalThis === 'undefined') return null;
  const storage = globalThis.sessionStorage;
  if (!storage) return null;
  try {
    storage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
  return storage;
}

export function loadGapThresholdPct() {
  const storage = getStorage();
  if (!storage) return DEFAULT_DENSE_OPS_THRESHOLD_PCT;
  const raw = storage.getItem(STORAGE_KEY);
  if (raw == null) return DEFAULT_DENSE_OPS_THRESHOLD_PCT;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return DEFAULT_DENSE_OPS_THRESHOLD_PCT;
  return clampThresholdPct(parsed);
}

export function saveGapThresholdPct(value) {
  const storage = getStorage();
  if (!storage) return;
  try {
    storage.setItem(STORAGE_KEY, String(clampThresholdPct(value)));
  } catch {
    // Best-effort: storage may be full or disabled.
  }
}

export function clearGapThresholdPct() {
  const storage = getStorage();
  if (!storage) return;
  try {
    storage.removeItem(STORAGE_KEY);
  } catch {
    // best-effort
  }
}

export const GAP_THRESHOLD_STORAGE_KEY = STORAGE_KEY;
