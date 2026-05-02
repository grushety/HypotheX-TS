import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import { DEFAULT_DENSE_OPS_THRESHOLD_PCT } from './createGapGatingState.js';
import {
  GAP_THRESHOLD_STORAGE_KEY,
  clearGapThresholdPct,
  loadGapThresholdPct,
  saveGapThresholdPct,
} from './userSetting.js';

class MemorySessionStorage {
  constructor() {
    this.store = new Map();
  }
  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null;
  }
  setItem(key, value) {
    this.store.set(key, String(value));
  }
  removeItem(key) {
    this.store.delete(key);
  }
}

beforeEach(() => {
  globalThis.sessionStorage = new MemorySessionStorage();
});

describe('gap threshold session storage', () => {
  it('returns the default when nothing is saved', () => {
    assert.equal(loadGapThresholdPct(), DEFAULT_DENSE_OPS_THRESHOLD_PCT);
  });

  it('round-trips a saved value', () => {
    saveGapThresholdPct(45);
    assert.equal(loadGapThresholdPct(), 45);
  });

  it('clamps stored values into [0, 100] on load', () => {
    globalThis.sessionStorage.setItem(GAP_THRESHOLD_STORAGE_KEY, '999');
    assert.equal(loadGapThresholdPct(), 100);
    globalThis.sessionStorage.setItem(GAP_THRESHOLD_STORAGE_KEY, '-50');
    assert.equal(loadGapThresholdPct(), 0);
  });

  it('falls back to the default for malformed storage entries', () => {
    globalThis.sessionStorage.setItem(GAP_THRESHOLD_STORAGE_KEY, 'not-a-number');
    assert.equal(loadGapThresholdPct(), DEFAULT_DENSE_OPS_THRESHOLD_PCT);
  });

  it('clearGapThresholdPct removes the entry', () => {
    saveGapThresholdPct(45);
    clearGapThresholdPct();
    assert.equal(loadGapThresholdPct(), DEFAULT_DENSE_OPS_THRESHOLD_PCT);
  });

  it('returns the default when sessionStorage is unavailable', () => {
    globalThis.sessionStorage = undefined;
    assert.equal(loadGapThresholdPct(), DEFAULT_DENSE_OPS_THRESHOLD_PCT);
  });
});
