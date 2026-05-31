/**
 * createShoeboxState — pure helpers for the REWORK-11 evidence shoebox.
 *
 * The shoebox is a latent fourth zone: a collection of pinned items
 * (prediction snapshot, min-flip result, plausibility snapshot, cohort
 * aggregate, etc.) plus a free-notes area, exportable for the paper
 * pipeline.
 *
 * State shape:
 *
 *   {
 *     items: [
 *       {
 *         id: string,         // stable across reorders + edits
 *         kind: string,       // 'prediction' | 'min-flip' | 'plausibility' | 'cohort' | ...
 *         title: string,
 *         summary: string,    // short one-liner for the card body
 *         capturedAt: ISO,
 *         provenance: object, // session-state snapshot at capture time
 *         payload: object,    // kind-specific data (predicted_label, distance, ...)
 *         note: string,       // user-editable
 *       },
 *       ...
 *     ],
 *     freeNotes: string,
 *   }
 *
 * Persistence: this lib has no I/O. The caller serializes via
 * `toPersistedJson` and rehydrates via `fromPersistedJson`. Today the
 * caller writes to `localStorage`; the lib is unchanged when a future
 * ticket promotes that to backend session storage.
 */

const STORAGE_KEY = "hypothex.shoebox.v1";
const SCHEMA_VERSION = 1;

function generateId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `pin-${Date.now()}-${Math.floor(Math.random() * 1e9).toString(36)}`;
}

function sanitizeString(value, fallback = "") {
  if (typeof value !== "string") return fallback;
  return value;
}

/**
 * Build a pin from a caller-supplied descriptor. The caller is responsible
 * for assembling the `provenance` object from real session state — this
 * lib does no fabrication.
 */
export function buildPin({ kind, title, summary, provenance, payload, note = "" }) {
  return {
    id: generateId(),
    kind: sanitizeString(kind, "unknown"),
    title: sanitizeString(title, "Pinned item"),
    summary: sanitizeString(summary, ""),
    capturedAt: new Date().toISOString(),
    provenance: provenance && typeof provenance === "object" ? provenance : {},
    payload: payload && typeof payload === "object" ? payload : {},
    note: sanitizeString(note, ""),
  };
}

export function emptyShoebox() {
  return { items: [], freeNotes: "" };
}

export function addPin(state, pin) {
  if (!pin || typeof pin.id !== "string") return state;
  return {
    ...state,
    items: [...state.items, pin],
  };
}

export function removePin(state, id) {
  return {
    ...state,
    items: state.items.filter((item) => item.id !== id),
  };
}

export function reorderPin(state, id, direction) {
  const index = state.items.findIndex((item) => item.id === id);
  if (index < 0) return state;
  const next = [...state.items];
  if (direction === "up" && index > 0) {
    [next[index - 1], next[index]] = [next[index], next[index - 1]];
    return { ...state, items: next };
  }
  if (direction === "down" && index < next.length - 1) {
    [next[index], next[index + 1]] = [next[index + 1], next[index]];
    return { ...state, items: next };
  }
  return state;
}

export function setNote(state, id, note) {
  return {
    ...state,
    items: state.items.map((item) =>
      item.id === id ? { ...item, note: sanitizeString(note, "") } : item,
    ),
  };
}

export function setFreeNotes(state, freeNotes) {
  return { ...state, freeNotes: sanitizeString(freeNotes, "") };
}

export function clearShoebox() {
  return emptyShoebox();
}

// ---- export -----------------------------------------------------------

function escapeMarkdown(value) {
  if (typeof value !== "string") return "";
  return value.replace(/[*_`]/g, "\\$&");
}

/**
 * Build a paper-ready Markdown report. One section per pin, footer with
 * free notes if non-empty. Each pin lists its title, kind, capturedAt,
 * one-line summary, and the most useful provenance keys flattened to a
 * key: value list.
 */
export function exportShoeboxAsMarkdown(state, { generatedAt = null } = {}) {
  const stamp = generatedAt instanceof Date ? generatedAt : new Date();
  const items = Array.isArray(state?.items) ? state.items : [];
  const freeNotes = sanitizeString(state?.freeNotes, "");
  const lines = [];
  lines.push("# HypotheX-TS shoebox export");
  lines.push("");
  lines.push(`_Generated: ${stamp.toISOString()} · ${items.length} pinned items_`);
  lines.push("");
  if (items.length === 0) {
    lines.push("_(no items pinned — nothing to report)_");
  } else {
    items.forEach((item, index) => {
      lines.push(`## ${index + 1}. ${escapeMarkdown(item.title)}`);
      lines.push("");
      lines.push(`- **Kind:** ${escapeMarkdown(item.kind)}`);
      lines.push(`- **Captured:** ${escapeMarkdown(item.capturedAt)}`);
      if (item.summary) {
        lines.push(`- **Summary:** ${escapeMarkdown(item.summary)}`);
      }
      const provEntries = Object.entries(item.provenance ?? {});
      if (provEntries.length > 0) {
        lines.push("- **Provenance:**");
        for (const [key, value] of provEntries) {
          if (value == null) continue;
          const rendered = typeof value === "object" ? JSON.stringify(value) : String(value);
          lines.push(`  - ${key}: ${escapeMarkdown(rendered)}`);
        }
      }
      if (item.note) {
        lines.push(`- **Note:** ${escapeMarkdown(item.note)}`);
      }
      lines.push("");
    });
  }
  if (freeNotes) {
    lines.push("## Free notes");
    lines.push("");
    lines.push(freeNotes);
    lines.push("");
  }
  return lines.join("\n");
}

/**
 * JSON export — full pin objects including payload + provenance, wrapped
 * in a top-level meta envelope (schema version + generation timestamp +
 * item count) so the consuming pipeline can validate the shape.
 */
export function exportShoeboxAsJson(state, { generatedAt = null } = {}) {
  const stamp = generatedAt instanceof Date ? generatedAt : new Date();
  return {
    schema: "hypothex.shoebox",
    version: SCHEMA_VERSION,
    generatedAt: stamp.toISOString(),
    itemCount: Array.isArray(state?.items) ? state.items.length : 0,
    items: Array.isArray(state?.items) ? state.items : [],
    freeNotes: sanitizeString(state?.freeNotes, ""),
  };
}

// ---- persistence ------------------------------------------------------

export function toPersistedJson(state) {
  return JSON.stringify({
    version: SCHEMA_VERSION,
    items: Array.isArray(state?.items) ? state.items : [],
    freeNotes: sanitizeString(state?.freeNotes, ""),
  });
}

export function fromPersistedJson(raw) {
  if (typeof raw !== "string" || raw.length === 0) return emptyShoebox();
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return emptyShoebox();
  }
  if (!parsed || typeof parsed !== "object") return emptyShoebox();
  if (parsed.version !== SCHEMA_VERSION) return emptyShoebox();
  const items = Array.isArray(parsed.items)
    ? parsed.items
        .filter((entry) => entry && typeof entry.id === "string")
        .map((entry) => ({
          id: entry.id,
          kind: sanitizeString(entry.kind, "unknown"),
          title: sanitizeString(entry.title, "Pinned item"),
          summary: sanitizeString(entry.summary, ""),
          capturedAt: sanitizeString(entry.capturedAt, new Date().toISOString()),
          provenance: entry.provenance && typeof entry.provenance === "object" ? entry.provenance : {},
          payload: entry.payload && typeof entry.payload === "object" ? entry.payload : {},
          note: sanitizeString(entry.note, ""),
        }))
    : [];
  return {
    items,
    freeNotes: sanitizeString(parsed.freeNotes, ""),
  };
}

export const SHOEBOX_STORAGE_KEY = STORAGE_KEY;
export const SHOEBOX_SCHEMA_VERSION = SCHEMA_VERSION;
