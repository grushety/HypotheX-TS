<script setup>
import { ref, watch } from 'vue';

import {
  DEFAULT_SUPPRESS_STRATEGY,
  SUPPRESS_STRATEGIES,
  SUPPRESS_STRATEGY_LABELS,
  buildSuppressPayload,
} from '../../lib/gaps/createGapGatingState.js';

const props = defineProps({
  segmentId: { type: String, default: null },
  missingnessPct: { type: Number, default: 0 },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(['op-invoked']);

const strategy = ref(DEFAULT_SUPPRESS_STRATEGY);

watch(
  () => props.segmentId,
  () => {
    strategy.value = DEFAULT_SUPPRESS_STRATEGY;
  },
);

function handleApply() {
  if (!props.segmentId || props.disabled) return;
  const payload = buildSuppressPayload({
    segmentId: props.segmentId,
    strategy: strategy.value,
  });
  emit('op-invoked', payload);
}
</script>

<template>
  <section class="gap-fill-picker" aria-label="Gap fill picker">
    <header class="gap-fill-picker__header">
      <p class="section-label">Fill missing data</p>
      <p v-if="missingnessPct > 0" class="gap-fill-picker__hint">
        Segment has {{ missingnessPct }}% missing observations.
      </p>
    </header>

    <fieldset class="gap-fill-picker__strategies" aria-label="Fill strategy">
      <legend class="sidebar-label">Strategy</legend>
      <label
        v-for="s in SUPPRESS_STRATEGIES"
        :key="s"
        class="gap-fill-picker__option"
      >
        <input
          type="radio"
          name="gap-strategy"
          :value="s"
          :checked="strategy === s"
          @change="strategy = s"
        />
        <span>{{ SUPPRESS_STRATEGY_LABELS[s] }}</span>
      </label>
    </fieldset>

    <footer class="gap-fill-picker__footer">
      <button
        type="button"
        class="gap-fill-picker__apply"
        :disabled="!segmentId || disabled"
        :title="!segmentId ? 'Pick a segment first.' : null"
        @click="handleApply"
      >
        Fill via suppress
      </button>
    </footer>
  </section>
</template>

<style scoped>
.gap-fill-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 8px;
  background: var(--surface, #ffffff);
  font-size: 0.85rem;
}
.gap-fill-picker__hint {
  margin: 0;
  font-size: 0.78rem;
  color: #6b6f8d;
}
.gap-fill-picker__strategies {
  border: 0;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.gap-fill-picker__option {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 8px;
  align-items: center;
}
.gap-fill-picker__footer {
  display: flex;
  justify-content: flex-end;
}
.gap-fill-picker__apply {
  font: inherit;
  padding: 5px 12px;
  border: 1px solid #0a3d91;
  border-radius: 6px;
  background: #0a3d91;
  color: #fff;
  cursor: pointer;
}
.gap-fill-picker__apply:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
