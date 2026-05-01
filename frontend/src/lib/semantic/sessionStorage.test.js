import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import {
  SEMANTIC_LAYER_STORAGE_KEY,
  clearSemanticLayerSession,
  loadSemanticLayerSession,
  saveSemanticLayerSession,
} from './sessionStorage.js';

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

describe('semantic-layer session storage', () => {
  it('returns null when no entry has been saved', () => {
    assert.equal(loadSemanticLayerSession(), null);
  });

  it('round-trips activePackKey and customYamlText', () => {
    saveSemanticLayerSession({ activePackKey: 'hydrology', customYamlText: null });
    assert.deepEqual(loadSemanticLayerSession(), {
      activePackKey: 'hydrology',
      customYamlText: null,
    });
  });

  it('persists custom YAML text alongside the key', () => {
    saveSemanticLayerSession({
      activePackKey: '__custom__',
      customYamlText: 'name: my-pack',
    });
    const loaded = loadSemanticLayerSession();
    assert.equal(loaded.customYamlText, 'name: my-pack');
  });

  it('clearSemanticLayerSession removes the entry', () => {
    saveSemanticLayerSession({ activePackKey: 'hydrology' });
    clearSemanticLayerSession();
    assert.equal(loadSemanticLayerSession(), null);
  });

  it('returns null when the stored payload is malformed JSON', () => {
    globalThis.sessionStorage.setItem(SEMANTIC_LAYER_STORAGE_KEY, 'not-json');
    assert.equal(loadSemanticLayerSession(), null);
  });

  it('returns null when sessionStorage is unavailable', () => {
    globalThis.sessionStorage = undefined;
    assert.equal(loadSemanticLayerSession(), null);
  });
});
