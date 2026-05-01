/**
 * Format a backend custom-YAML validation error into a single user-readable
 * line for the upload UI (UI-014).
 *
 * Backend payload shape:
 *   { ok: false, error: { message, line?, kind } }
 *
 * The `kind` discriminates a parse error (PyYAML) from a schema error
 * (load_pack: unknown shape, unknown detector, duplicate label). Parse
 * errors include a 1-based line number; schema errors do not.
 */

export function formatYamlError(error) {
  if (!error || typeof error !== 'object') return '';
  const message = typeof error.message === 'string' ? error.message.trim() : '';
  const line = typeof error.line === 'number' && error.line > 0 ? error.line : null;
  const kind = error.kind === 'schema' ? 'Schema error' : 'YAML error';

  if (line != null) return `${kind} on line ${line}: ${message}`;
  return `${kind}: ${message}`;
}
