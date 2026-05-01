<script setup>
import { computed, ref, watch } from 'vue';

import {
  CUSTOM_OPTION_KEY,
  NONE_OPTION_KEY,
  PACK_KIND,
  createSemanticLayerState,
} from '../../lib/semantic/createSemanticLayerState.js';
import { formatYamlError } from '../../lib/semantic/formatYamlError.js';

const props = defineProps({
  builtInPacks: { type: Array, default: () => [] },
  activePackKey: { type: String, default: NONE_OPTION_KEY },
  activePack: { type: Object, default: null },
  labelResults: { type: Array, default: () => [] },
  customError: { type: Object, default: null },
  userOverrides: { type: Object, default: () => new Map() },
  customYamlText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
});

const emit = defineEmits(['select-pack', 'upload-custom-yaml', 'clear-custom']);

const state = computed(() =>
  createSemanticLayerState({
    builtInPacks: props.builtInPacks,
    activePackKey: props.activePackKey,
    activePack: props.activePack,
    labelResults: props.labelResults,
    customError: props.customError,
    userOverrides: props.userOverrides,
  }),
);

const yamlBuffer = ref(props.customYamlText);

watch(
  () => props.customYamlText,
  (value) => {
    yamlBuffer.value = value ?? '';
  },
);

const isCustom = computed(() => state.value.kind === PACK_KIND.CUSTOM);
const isNone = computed(() => state.value.kind === PACK_KIND.NONE);
const errorMessage = computed(() => formatYamlError(state.value.customError));

function handleSelectChange(event) {
  emit('select-pack', event.target.value);
}

function handleUpload() {
  emit('upload-custom-yaml', yamlBuffer.value);
}

function handleFileInput(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.addEventListener('load', () => {
    yamlBuffer.value = String(reader.result ?? '');
  });
  reader.readAsText(file);
}
</script>

<template>
  <section class="semantic-layer-panel" aria-label="Semantic layer panel">
    <header class="semantic-layer-header">
      <p class="section-label">Semantic layer</p>
      <h3>Domain pack</h3>
    </header>

    <label class="semantic-layer-field">
      <span class="sidebar-label">Active pack</span>
      <select
        class="semantic-layer-select"
        :value="state.selectedKey"
        :disabled="loading"
        aria-label="Select active semantic pack"
        @change="handleSelectChange"
      >
        <option
          v-for="option in state.options"
          :key="option.key"
          :value="option.key"
        >
          {{ option.label }}
          <template v-if="option.labelCount"> ({{ option.labelCount }})</template>
        </option>
      </select>
    </label>

    <p v-if="loading" class="semantic-layer-meta" aria-live="polite">
      Loading packs…
    </p>

    <p v-else-if="isNone" class="semantic-layer-meta">
      No semantic overlay. Shape primitives are shown without a domain label.
    </p>

    <div v-if="isCustom" class="semantic-layer-custom">
      <label class="semantic-layer-field">
        <span class="sidebar-label">Custom YAML</span>
        <textarea
          v-model="yamlBuffer"
          class="semantic-layer-yaml"
          rows="8"
          spellcheck="false"
          aria-label="Custom semantic-pack YAML"
        />
      </label>
      <div class="semantic-layer-custom-actions">
        <input
          type="file"
          accept=".yaml,.yml,text/yaml,application/x-yaml"
          aria-label="Upload semantic-pack YAML file"
          @change="handleFileInput"
        />
        <button
          type="button"
          class="semantic-layer-validate"
          :disabled="!yamlBuffer.trim() || loading"
          @click="handleUpload"
        >
          Validate &amp; activate
        </button>
        <button
          v-if="customYamlText"
          type="button"
          class="semantic-layer-clear"
          @click="emit('clear-custom')"
        >
          Clear
        </button>
      </div>
      <p
        v-if="errorMessage"
        class="semantic-layer-error"
        role="alert"
      >
        {{ errorMessage }}
      </p>
    </div>

    <section
      v-if="state.activePack && state.infoPanelRows.length"
      class="semantic-layer-info"
      aria-label="Semantic labels in active pack"
    >
      <p class="section-label">
        Labels in <strong>{{ state.activePack.name }}</strong>
        <span v-if="state.activePack.version" class="semantic-layer-version">
          v{{ state.activePack.version }}
        </span>
      </p>
      <ul class="semantic-layer-info-list">
        <li
          v-for="row in state.infoPanelRows"
          :key="row.name"
          class="semantic-layer-info-row"
          :class="{ 'semantic-layer-info-row-shadowed': row.shadowed }"
        >
          <span class="semantic-layer-info-name">{{ row.name }}</span>
          <span class="semantic-layer-info-shape">{{ row.shape }}</span>
          <span
            v-if="row.shadowed"
            class="semantic-layer-info-shadow-flag"
            :title="`Shadowed by ${row.shadowedBy ?? 'project override'}`"
            aria-label="Shadowed by user-defined label"
          >
            ★ user
          </span>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.semantic-layer-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 8px;
  background: var(--surface, #ffffff);
  font-size: 0.9rem;
}

.semantic-layer-header {
  margin: 0;
}

.semantic-layer-header h3 {
  margin: 0;
  font-size: 1rem;
}

.semantic-layer-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.semantic-layer-select,
.semantic-layer-yaml {
  width: 100%;
  font: inherit;
  padding: 6px 8px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: var(--surface, #ffffff);
  color: inherit;
}

.semantic-layer-yaml {
  font-family: var(--font-mono, ui-monospace, "SFMono-Regular", Consolas, monospace);
  font-size: 0.82rem;
  line-height: 1.4;
  resize: vertical;
}

.semantic-layer-meta {
  margin: 0;
  color: #6b6f8d;
  font-size: 0.85rem;
}

.semantic-layer-custom {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 10px;
  border: 1px dashed var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.02);
}

.semantic-layer-custom-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.semantic-layer-validate,
.semantic-layer-clear {
  font: inherit;
  padding: 6px 12px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: var(--surface, #ffffff);
  cursor: pointer;
}

.semantic-layer-validate:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.semantic-layer-error {
  margin: 0;
  padding: 6px 8px;
  border-radius: 6px;
  background: #ffebe9;
  border: 1px solid #ff8182;
  color: #cf222e;
  font-size: 0.82rem;
  white-space: pre-wrap;
}

.semantic-layer-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 4px;
  border-top: 1px solid var(--border-subtle, #d0d7de);
}

.semantic-layer-version {
  font-weight: 400;
  color: #6b6f8d;
  margin-left: 4px;
}

.semantic-layer-info-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: 1fr;
  gap: 2px;
}

.semantic-layer-info-row {
  display: grid;
  grid-template-columns: 1fr max-content max-content;
  align-items: baseline;
  gap: 8px;
  padding: 3px 6px;
  border-radius: 4px;
}

.semantic-layer-info-row-shadowed {
  background: rgba(154, 103, 0, 0.08);
}

.semantic-layer-info-name {
  font-weight: 600;
}

.semantic-layer-info-shape {
  font-family: var(--font-mono, ui-monospace, "SFMono-Regular", Consolas, monospace);
  font-size: 0.8rem;
  color: #6b6f8d;
}

.semantic-layer-info-shadow-flag {
  font-size: 0.72rem;
  font-weight: 700;
  color: #9a6700;
  letter-spacing: 0.05em;
}
</style>
