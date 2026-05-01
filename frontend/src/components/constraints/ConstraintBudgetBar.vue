<script setup>
import { computed, ref, watch } from 'vue';

import { createConstraintBudgetState } from '../../lib/constraints/createConstraintBudgetState.js';
import ConstraintResidualBreakdown from './ConstraintResidualBreakdown.vue';

const props = defineProps({
  law: { type: String, required: true },
  compensationMode: { type: String, default: null },
  initialResidual: { type: Number, default: null },
  finalResidual: { type: Number, default: null },
  tolerance: { type: Number, default: null },
  units: { type: String, default: '' },
  components: { type: Object, default: () => ({}) },
  expanded: { type: Boolean, default: false },
});

const emit = defineEmits(['toggle-expanded']);

const internalExpanded = ref(props.expanded);

watch(
  () => props.expanded,
  (v) => {
    internalExpanded.value = v;
  },
);

const isExpanded = computed({
  get: () => internalExpanded.value,
  set: (v) => {
    internalExpanded.value = v;
  },
});

const state = computed(() =>
  createConstraintBudgetState({
    law: props.law,
    compensationMode: props.compensationMode,
    initialResidual: props.initialResidual,
    finalResidual: props.finalResidual,
    tolerance: props.tolerance,
    units: props.units,
  }),
);

const fillStyle = computed(() => ({
  width: `${Math.min(100, state.value.fillFraction * (100 / 1.5))}%`,
}));

const initialMarkerStyle = computed(() => ({
  left: `${Math.min(100, state.value.initialFillFraction * (100 / 1.5))}%`,
}));

const finalMarkerStyle = computed(() => ({
  left: `${Math.min(100, state.value.fillFraction * (100 / 1.5))}%`,
}));

const arrowSymbol = computed(() => {
  if (!state.value.showPrePost) return '';
  if (state.value.direction === 'improving') return '→';
  if (state.value.direction === 'worsening') return '⇒';
  return '·';
});

function toggle() {
  isExpanded.value = !isExpanded.value;
  emit('toggle-expanded', isExpanded.value);
}

function handleKeydown(event) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    toggle();
  }
}
</script>

<template>
  <div
    class="constraint-budget-bar"
    :class="`constraint-budget-bar--status-${state.status}`"
    :data-law="law"
  >
    <button
      type="button"
      class="constraint-budget-bar__toggle"
      :aria-expanded="isExpanded ? 'true' : 'false'"
      :aria-label="`Toggle ${law} residual breakdown`"
      :title="state.hoverText"
      @click="toggle"
      @keydown="handleKeydown"
    >
      <span class="constraint-budget-bar__law">{{ law }}</span>

      <div class="constraint-budget-bar__track" role="presentation">
        <div class="constraint-budget-bar__tolerance-marker" />
        <div class="constraint-budget-bar__fill" :style="fillStyle" />
        <div
          v-if="state.showPrePost"
          class="constraint-budget-bar__marker constraint-budget-bar__marker--initial"
          :style="initialMarkerStyle"
          aria-hidden="true"
        />
        <div
          v-if="state.showPrePost"
          class="constraint-budget-bar__marker constraint-budget-bar__marker--final"
          :style="finalMarkerStyle"
          aria-hidden="true"
        />
      </div>

      <span class="constraint-budget-bar__arrow" aria-hidden="true">{{ arrowSymbol }}</span>

      <span class="constraint-budget-bar__readout">{{ state.hoverText }}</span>
    </button>

    <div class="constraint-budget-bar__aria-text" aria-live="polite">
      {{ state.ariaText }}
    </div>

    <ConstraintResidualBreakdown
      v-if="isExpanded"
      class="constraint-budget-bar__breakdown"
      :law="law"
      :components="components"
      :units="units"
    />
  </div>
</template>

<style scoped>
.constraint-budget-bar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 8px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: var(--surface, #ffffff);
  font-size: 0.85em;
}

.constraint-budget-bar__toggle {
  display: grid;
  grid-template-columns: max-content 1fr max-content max-content;
  align-items: center;
  gap: 8px;
  padding: 4px;
  background: transparent;
  border: 0;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
}

.constraint-budget-bar__toggle:focus-visible {
  outline: 2px solid var(--focus-ring, #0a3d91);
  outline-offset: 2px;
  border-radius: 4px;
}

.constraint-budget-bar__law {
  font-variant: small-caps;
  letter-spacing: 0.04em;
  font-weight: 600;
}

.constraint-budget-bar__track {
  position: relative;
  height: 10px;
  border-radius: 5px;
  background: var(--track-bg, #eef2f5);
  overflow: hidden;
  min-width: 80px;
}

.constraint-budget-bar__tolerance-marker {
  position: absolute;
  top: 0;
  left: 66.6667%; /* fillFraction = 1.0 of 1.5 cap → 66.67% */
  width: 1px;
  height: 100%;
  background: rgba(0, 0, 0, 0.35);
}

.constraint-budget-bar__fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: currentColor;
  opacity: 0.7;
}

.constraint-budget-bar__marker {
  position: absolute;
  top: -2px;
  width: 2px;
  height: 14px;
  background: rgba(0, 0, 0, 0.55);
}

.constraint-budget-bar__marker--initial {
  background: rgba(0, 0, 0, 0.4);
}

.constraint-budget-bar__marker--final {
  background: #000000;
}

.constraint-budget-bar__arrow {
  font-weight: 700;
  font-size: 1em;
}

.constraint-budget-bar__readout {
  font-variant-numeric: tabular-nums;
  opacity: 0.85;
}

.constraint-budget-bar__aria-text {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Status colours — applied via currentColor so the fill bar inherits. */
.constraint-budget-bar--status-green {
  color: #1a7f37;
  background: #f0f8f1;
  border-color: #95d5a2;
}
.constraint-budget-bar--status-amber {
  color: #9a6700;
  background: #fff8c5;
  border-color: #d4a72c;
}
.constraint-budget-bar--status-red {
  color: #cf222e;
  background: #ffebe9;
  border-color: #ff8182;
}

.constraint-budget-bar__breakdown {
  margin-top: 4px;
}
</style>
