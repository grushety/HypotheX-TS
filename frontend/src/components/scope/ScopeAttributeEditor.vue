<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import {
  buildScopeUpdatePayload,
  createScopeEditorState,
  draftFromScope,
} from '../../lib/scope/createScopeEditorState.js';

const props = defineProps({
  segment: { type: Object, default: null },
  seriesLength: { type: Number, default: null },
  projectDomainHint: { type: String, default: null },
  open: { type: Boolean, default: true },
});

const emit = defineEmits(['scope-updated', 'close']);

const draft = ref(draftFromScope(props.segment?.scope ?? null, props.projectDomainHint));

watch(
  () => [props.segment?.id, props.segment?.scope, props.projectDomainHint],
  () => {
    draft.value = draftFromScope(props.segment?.scope ?? null, props.projectDomainHint);
  },
);

const state = computed(() =>
  createScopeEditorState({
    segment: props.segment,
    seriesLength: props.seriesLength,
    draft: draft.value,
    projectDomainHint: props.projectDomainHint,
  }),
);

function handleSave() {
  if (!state.value.canSave) return;
  const payload = buildScopeUpdatePayload({
    segmentId: state.value.segmentId,
    draft: draft.value,
    previousScope: state.value.previousScope,
    projectDomainHint: props.projectDomainHint,
  });
  emit('scope-updated', payload);
  emit('close');
}

function handleCancel() {
  emit('close');
}

function setMode(mode) {
  draft.value = { ...draft.value, mode };
}

function setDomainHint(key) {
  draft.value = { ...draft.value, domainHintKey: key };
}

function setWindowSize(value) {
  const n = Number(value);
  draft.value = {
    ...draft.value,
    windowSize: Number.isFinite(n) ? Math.round(n) : value,
  };
}

function setReference(value) {
  draft.value = { ...draft.value, reference: value || null };
}

function handleKeydown(event) {
  if (props.open && event.key === 'Escape') {
    event.preventDefault();
    handleCancel();
  }
}

onMounted(() => {
  if (typeof globalThis !== 'undefined') {
    globalThis.addEventListener?.('keydown', handleKeydown);
  }
});

onUnmounted(() => {
  if (typeof globalThis !== 'undefined') {
    globalThis.removeEventListener?.('keydown', handleKeydown);
  }
});
</script>

<template>
  <div
    v-if="open"
    class="scope-editor"
    role="dialog"
    aria-modal="true"
    aria-label="Edit scope attribute"
  >
    <div class="scope-editor__backdrop" @click="handleCancel"></div>
    <section class="scope-editor__panel">
      <header class="scope-editor__header">
        <p class="section-label">Scope attribute</p>
        <h3>{{ state.segmentId ?? 'No segment selected' }}</h3>
        <button
          type="button"
          class="scope-editor__close"
          aria-label="Close scope editor"
          @click="handleCancel"
        >
          ✕
        </button>
      </header>

      <label class="scope-editor__field">
        <span class="sidebar-label">Window size (samples)</span>
        <input
          type="number"
          class="scope-editor__input"
          min="1"
          step="1"
          :value="state.draft.windowSize"
          :aria-describedby="state.validation.errors.window_size ? 'scope-window-error' : null"
          :aria-invalid="!!state.validation.errors.window_size"
          @input="setWindowSize($event.target.value)"
        />
        <p
          v-if="state.validation.errors.window_size"
          id="scope-window-error"
          class="scope-editor__error"
          role="alert"
        >
          {{ state.validation.errors.window_size }}
        </p>
      </label>

      <fieldset class="scope-editor__field" aria-label="Scope mode">
        <legend class="sidebar-label">Mode</legend>
        <label
          v-for="m in state.scopeModes"
          :key="m"
          class="scope-editor__radio"
        >
          <input
            type="radio"
            name="scope-mode"
            :value="m"
            :checked="state.draft.mode === m"
            @change="setMode(m)"
          />
          <span>{{ m }}</span>
        </label>
        <p v-if="state.validation.errors.mode" class="scope-editor__error" role="alert">
          {{ state.validation.errors.mode }}
        </p>
      </fieldset>

      <label v-if="state.isFixedMode" class="scope-editor__field">
        <span class="sidebar-label">Reference time</span>
        <input
          type="datetime-local"
          class="scope-editor__input"
          step="1"
          :value="state.draft.reference ?? ''"
          :aria-describedby="state.validation.errors.reference ? 'scope-reference-error' : null"
          :aria-invalid="!!state.validation.errors.reference"
          @input="setReference($event.target.value)"
        />
        <p
          v-if="state.validation.errors.reference"
          id="scope-reference-error"
          class="scope-editor__error"
          role="alert"
        >
          {{ state.validation.errors.reference }}
        </p>
      </label>

      <label class="scope-editor__field">
        <span class="sidebar-label">Domain hint</span>
        <select
          class="scope-editor__select"
          :value="state.draft.domainHintKey"
          aria-label="Domain hint for this segment"
          @change="setDomainHint($event.target.value)"
        >
          <option v-for="opt in state.options" :key="opt.key" :value="opt.key">
            {{ opt.label }}
          </option>
        </select>
      </label>

      <p class="scope-editor__hint">
        Saving will trigger reclassification (OP-040
        <code>RECLASSIFY_VIA_SEGMENTER</code>).
      </p>

      <footer class="scope-editor__footer">
        <button
          type="button"
          class="scope-editor__cancel"
          @click="handleCancel"
        >
          Cancel
        </button>
        <button
          type="button"
          class="scope-editor__save"
          :disabled="!state.canSave"
          :title="state.canSave ? null : 'Fix the errors above to save.'"
          @click="handleSave"
        >
          Save &amp; reclassify
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.scope-editor {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.scope-editor__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
}
.scope-editor__panel {
  position: relative;
  width: min(420px, 92vw);
  max-height: 90vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 22px 14px;
  background: var(--surface, #ffffff);
  border-radius: 10px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.25);
  font-size: 0.9rem;
}
.scope-editor__header {
  position: relative;
  margin: 0;
}
.scope-editor__header h3 {
  margin: 0;
  font-size: 1rem;
  font-family: var(--font-mono, ui-monospace, "SFMono-Regular", Consolas, monospace);
}
.scope-editor__close {
  position: absolute;
  top: 0;
  right: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 1rem;
  color: #6b6f8d;
}
.scope-editor__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 0;
  padding: 0;
  margin: 0;
}
.scope-editor__input,
.scope-editor__select {
  font: inherit;
  padding: 6px 8px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: var(--surface, #ffffff);
  color: inherit;
}
.scope-editor__input[aria-invalid="true"],
.scope-editor__input:invalid {
  border-color: #cf222e;
}
.scope-editor__radio {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 8px;
  align-items: center;
}
.scope-editor__error {
  margin: 0;
  font-size: 0.78rem;
  color: #cf222e;
}
.scope-editor__hint {
  margin: 0;
  font-size: 0.78rem;
  color: #6b6f8d;
}
.scope-editor__footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding-top: 4px;
  border-top: 1px solid var(--border-subtle, #d0d7de);
}
.scope-editor__cancel,
.scope-editor__save {
  font: inherit;
  padding: 6px 14px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: var(--surface, #ffffff);
  cursor: pointer;
}
.scope-editor__save {
  background: #0a3d91;
  color: #fff;
  border-color: #0a3d91;
}
.scope-editor__save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
