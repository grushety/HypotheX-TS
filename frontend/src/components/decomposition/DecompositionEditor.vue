<script setup>
import { computed, ref, watch } from 'vue';

import { createDecompositionEditorState, PREVIEW_DEBOUNCE_MS } from '../../lib/decomposition/createDecompositionEditorState.js';
import LinearComponentEditor from './LinearComponentEditor.vue';
import ResidualDisplay from './ResidualDisplay.vue';
import SeasonalComponentEditor from './SeasonalComponentEditor.vue';
import StepComponentEditor from './StepComponentEditor.vue';
import TransientComponentEditor from './TransientComponentEditor.vue';

const props = defineProps({
  blob: { type: Object, default: null },
  segmentId: { type: String, default: null },
});

const emit = defineEmits(['op-invoked']);

const localHandleValues = ref({});

const editorState = computed(() => createDecompositionEditorState(props.blob));

watch(
  () => props.blob,
  () => { localHandleValues.value = {}; },
);

function effectiveRows() {
  return editorState.value.rows.map((row) => ({
    ...row,
    handles: row.handles.map((h) => ({
      ...h,
      currentValue: localHandleValues.value[`${row.componentKey}::${h.name}`] ?? h.currentValue,
    })),
  }));
}

const rows = computed(effectiveRows);

let debounceTimer = null;

function onHandleChange({ componentKey, handleName, value }) {
  localHandleValues.value = {
    ...localHandleValues.value,
    [`${componentKey}::${handleName}`]: value,
  };

  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    const payload = editorState.value.getOpInvoked(componentKey, handleName, value, props.segmentId);
    if (payload) emit('op-invoked', payload);
  }, PREVIEW_DEBOUNCE_MS);
}

function onReset(componentKey) {
  const prefix = `${componentKey}::`;
  const next = { ...localHandleValues.value };
  for (const key of Object.keys(next)) {
    if (key.startsWith(prefix)) delete next[key];
  }
  localHandleValues.value = next;
}

const COMPONENT_MAP = {
  linear: LinearComponentEditor,
  seasonal: SeasonalComponentEditor,
  step: StepComponentEditor,
  transient: TransientComponentEditor,
};
</script>

<template>
  <section class="decomp-editor" aria-label="Decomposition editor">
    <div class="surface-header">
      <div>
        <p class="section-label">Decomposition editor</p>
        <h3>{{ blob ? blob.method : 'No segment selected' }}</h3>
      </div>
      <span v-if="segmentId" class="surface-tag">{{ segmentId }}</span>
    </div>

    <p v-if="!blob" class="decomp-empty-state">
      Select a segment with a fitted decomposition to edit its components.
    </p>

    <div v-else class="decomp-rows">
      <template v-for="row in rows" :key="row.componentKey">
        <component
          :is="COMPONENT_MAP[row.componentType]"
          v-if="!row.readOnly"
          :row="row"
          @handle-change="onHandleChange"
          @reset="onReset"
        />
        <ResidualDisplay
          v-else
          :component-key="row.componentKey"
          :component-values="row.componentValues"
          :fit-metadata="blob.fit_metadata ?? {}"
        />
      </template>
    </div>
  </section>
</template>
