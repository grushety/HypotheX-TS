<script setup>
import { computed, onBeforeUnmount, onMounted } from "vue";

import {
  exportShoeboxAsJson,
  exportShoeboxAsMarkdown,
} from "../../lib/shoebox/createShoeboxState.js";

const props = defineProps({
  state: { type: Object, required: true },
  open: { type: Boolean, default: false },
});

const emit = defineEmits([
  "close",
  "remove-pin",
  "reorder-pin",
  "update-note",
  "update-free-notes",
  "clear",
]);

const hasItems = computed(() => Array.isArray(props.state?.items) && props.state.items.length > 0);

function downloadBlob(content, filename, type) {
  if (typeof document === "undefined") return;
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function handleExportJson() {
  const payload = exportShoeboxAsJson(props.state);
  downloadBlob(
    JSON.stringify(payload, null, 2),
    `hypothex-shoebox-${timestamp()}.json`,
    "application/json",
  );
}

function handleExportMarkdown() {
  const md = exportShoeboxAsMarkdown(props.state);
  downloadBlob(md, `hypothex-shoebox-${timestamp()}.md`, "text/markdown");
}

function handleClose() {
  emit("close");
}

function handleEscape(event) {
  if (event.key === "Escape" && props.open) {
    handleClose();
  }
}

function handleBackdropClick(event) {
  if (event.target === event.currentTarget) {
    handleClose();
  }
}

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", handleEscape);
  }
});

onBeforeUnmount(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", handleEscape);
  }
});

function provenanceLines(provenance) {
  if (!provenance || typeof provenance !== "object") return [];
  return Object.entries(provenance)
    .filter(([, value]) => value != null)
    .map(([key, value]) => ({
      key,
      value: typeof value === "object" ? JSON.stringify(value) : String(value),
    }));
}
</script>

<template>
  <div
    v-if="open"
    class="shoebox-scrim"
    role="dialog"
    aria-modal="true"
    aria-labelledby="shoebox-title"
    @click="handleBackdropClick"
  >
    <section class="shoebox-modal">
      <header class="shoebox-head">
        <span class="mlabel">Shoebox</span>
        <h2 id="shoebox-title" class="shoebox-title">
          Evidence collection · {{ state.items.length }} pinned
        </h2>
        <button
          type="button"
          class="shoebox-close"
          aria-label="Close shoebox"
          @click="handleClose"
        >×</button>
      </header>

      <div class="shoebox-body">
        <div v-if="!hasItems" class="shoebox-empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M3 9l2-5h14l2 5" />
            <path d="M3 9v10a1 1 0 001 1h16a1 1 0 001-1V9" />
            <path d="M9 13h6" />
          </svg>
          <p>
            <b>Nothing pinned yet.</b><br />
            Use the pin button on a prediction, min-flip, plausibility snapshot, or
            cohort aggregate to start a paper-ready collection.
          </p>
        </div>

        <ol v-else class="shoebox-list">
          <li
            v-for="(item, index) in state.items"
            :key="item.id"
            class="shoebox-card"
          >
            <div class="shoebox-reorder">
              <button
                type="button"
                class="shoebox-reorder-btn"
                :disabled="index === 0"
                aria-label="Move up"
                @click="emit('reorder-pin', { id: item.id, direction: 'up' })"
              >▲</button>
              <button
                type="button"
                class="shoebox-reorder-btn"
                :disabled="index === state.items.length - 1"
                aria-label="Move down"
                @click="emit('reorder-pin', { id: item.id, direction: 'down' })"
              >▼</button>
            </div>

            <div class="shoebox-card-main">
              <header class="shoebox-card-head">
                <span class="shoebox-card-kind">{{ item.kind }}</span>
                <strong class="shoebox-card-title">{{ item.title }}</strong>
                <button
                  type="button"
                  class="shoebox-card-del"
                  aria-label="Remove pin"
                  title="Remove pin"
                  @click="emit('remove-pin', item.id)"
                >×</button>
              </header>

              <p v-if="item.summary" class="shoebox-card-summary">{{ item.summary }}</p>

              <ul v-if="provenanceLines(item.provenance).length" class="shoebox-card-prov">
                <li v-for="entry in provenanceLines(item.provenance)" :key="entry.key">
                  <span class="prov-key">{{ entry.key }}</span>
                  <span class="prov-value">{{ entry.value }}</span>
                </li>
              </ul>

              <textarea
                class="shoebox-card-note"
                :value="item.note"
                placeholder="add a note for the paper…"
                rows="2"
                @input="emit('update-note', { id: item.id, note: $event.target.value })"
              />

              <p class="shoebox-card-captured">captured {{ item.capturedAt }}</p>
            </div>
          </li>
        </ol>

        <section class="shoebox-free" aria-label="Free notes">
          <span class="mlabel">Free notes</span>
          <textarea
            class="shoebox-free-area"
            :value="state.freeNotes"
            placeholder="wrap-up thoughts, paper-narrative bullets, follow-ups…"
            rows="4"
            @input="emit('update-free-notes', $event.target.value)"
          />
        </section>
      </div>

      <footer class="shoebox-foot">
        <button
          type="button"
          class="shoebox-foot-btn"
          :disabled="!hasItems"
          @click="emit('clear')"
        >Clear all</button>
        <span class="spacer" />
        <button
          type="button"
          class="shoebox-foot-btn"
          :disabled="!hasItems"
          @click="handleExportJson"
        >Export JSON</button>
        <button
          type="button"
          class="shoebox-foot-btn primary"
          :disabled="!hasItems"
          @click="handleExportMarkdown"
        >Export Markdown</button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.shoebox-scrim {
  position: fixed;
  inset: 0;
  background: rgba(20, 27, 38, 0.42);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 24px;
}

.shoebox-modal {
  width: min(760px, 100%);
  max-height: 88vh;
  background: var(--bg-panel);
  border-radius: var(--r-lg);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-pop);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.shoebox-head {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 16px;
  border-bottom: 1px solid var(--line);
  background: var(--bg-bar);
}
.mlabel {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.shoebox-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.shoebox-close {
  margin-left: auto;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid var(--line-2);
  background: var(--bg-panel);
  color: var(--ink-3);
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}
.shoebox-close:hover { background: var(--bg-hover); color: var(--ink); }

.shoebox-body {
  flex: 1 1 auto;
  overflow: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.shoebox-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 11px;
  text-align: center;
  padding: 32px 12px;
  color: var(--ink-3);
  font-size: 12.5px;
  line-height: 1.55;
}
.shoebox-empty svg { width: 28px; height: 28px; color: var(--ink-4); }
.shoebox-empty b { color: var(--ink); }

.shoebox-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.shoebox-card {
  display: flex;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--bg-bar);
  padding: 11px 13px;
}
.shoebox-reorder {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: none;
  padding-top: 2px;
}
.shoebox-reorder-btn {
  width: 20px;
  height: 18px;
  border: 1px solid var(--line-2);
  background: var(--bg-panel);
  color: var(--ink-3);
  border-radius: 3px;
  font-size: 9px;
  cursor: pointer;
}
.shoebox-reorder-btn:hover:not(:disabled) { background: var(--bg-hover); color: var(--ink); }
.shoebox-reorder-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.shoebox-card-main { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.shoebox-card-head { display: flex; align-items: center; gap: 8px; }
.shoebox-card-kind {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-2);
  background: var(--bg-sunken);
  border-radius: 3px;
  padding: 2px 7px;
}
.shoebox-card-title { font-size: 13px; color: var(--ink); }
.shoebox-card-del {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--ink-4);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  padding: 0 4px;
  border-radius: 3px;
}
.shoebox-card-del:hover { background: var(--st-fail-bg); color: var(--st-fail); }

.shoebox-card-summary {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--ink-2);
}

.shoebox-card-prov {
  list-style: none;
  margin: 0;
  padding: 4px 7px;
  background: var(--bg-sunken);
  border-radius: var(--r-sm);
  display: flex;
  flex-wrap: wrap;
  gap: 4px 9px;
}
.shoebox-card-prov li {
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--ink-3);
}
.shoebox-card-prov .prov-key { color: var(--ink-4); margin-right: 3px; }
.shoebox-card-prov .prov-value { color: var(--ink-2); }

.shoebox-card-note {
  width: 100%;
  border: 1px solid var(--line-2);
  border-radius: var(--r-sm);
  padding: 6px 8px;
  font: inherit;
  font-size: 11.5px;
  resize: vertical;
  background: var(--bg-panel);
  color: var(--ink);
}
.shoebox-card-note:focus {
  outline: none;
  border-color: var(--ink-3);
  box-shadow: 0 0 0 3px rgba(122, 134, 152, 0.18);
}

.shoebox-card-captured {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--ink-4);
}

.shoebox-free { display: flex; flex-direction: column; gap: 5px; }
.shoebox-free-area {
  width: 100%;
  min-height: 70px;
  border: 1px solid var(--line-2);
  border-radius: var(--r-md);
  padding: 9px 11px;
  font: inherit;
  font-size: 12px;
  resize: vertical;
  background: var(--bg-panel);
  color: var(--ink);
}
.shoebox-free-area:focus {
  outline: none;
  border-color: var(--ink-3);
  box-shadow: 0 0 0 3px rgba(122, 134, 152, 0.18);
}

.shoebox-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 16px;
  border-top: 1px solid var(--line);
  background: var(--bg-bar);
}
.shoebox-foot .spacer { flex: 1; }
.shoebox-foot-btn {
  padding: 6px 13px;
  border: 1px solid var(--line-2);
  background: var(--bg-panel);
  color: var(--ink);
  border-radius: var(--r-sm);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.shoebox-foot-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.shoebox-foot-btn:hover:not(:disabled) { background: var(--bg-hover); border-color: var(--ink-3); }
.shoebox-foot-btn.primary {
  background: var(--ink);
  border-color: var(--ink);
  color: #fff;
}
.shoebox-foot-btn.primary:hover:not(:disabled) { background: #000; }

/* Mobile — bottom sheet */
@media (max-width: 900px) {
  .shoebox-scrim { align-items: flex-end; padding: 0; }
  .shoebox-modal {
    width: 100%;
    max-width: 100%;
    border-radius: var(--r-lg) var(--r-lg) 0 0;
    max-height: 86vh;
    animation: sheet-up 0.24s cubic-bezier(0.2, 0.8, 0.3, 1);
  }
  @keyframes sheet-up {
    from { transform: translateY(100%); }
  }
}
</style>
