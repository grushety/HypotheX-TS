/**
 * Session-storage persistence for the semantic-layer panel (UI-014).
 *
 * Stores the user's active pack across page reloads within one tab. We
 * persist *only the selector key* (e.g. "hydrology" or `__none__`) and the
 * raw text of an uploaded custom pack — never the parsed pack object,
 * since the backend re-parses on every detector call.
 */

const STORAGE_KEY = 'hypothex-ts.semantic-layer.v1';

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

export function loadSemanticLayerSession() {
  const storage = getStorage();
  if (!storage) return null;
  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) return null;
    return {
      activePackKey: typeof parsed.activePackKey === 'string' ? parsed.activePackKey : null,
      customYamlText: typeof parsed.customYamlText === 'string' ? parsed.customYamlText : null,
    };
  } catch {
    return null;
  }
}

export function saveSemanticLayerSession({ activePackKey = null, customYamlText = null } = {}) {
  const storage = getStorage();
  if (!storage) return;
  try {
    storage.setItem(
      STORAGE_KEY,
      JSON.stringify({ activePackKey, customYamlText }),
    );
  } catch {
    // Storage may be full or disabled; treat as best-effort.
  }
}

export function clearSemanticLayerSession() {
  const storage = getStorage();
  if (!storage) return;
  try {
    storage.removeItem(STORAGE_KEY);
  } catch {
    // best-effort
  }
}

export const SEMANTIC_LAYER_STORAGE_KEY = STORAGE_KEY;
