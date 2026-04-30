<script setup>
import { computed, ref } from 'vue';

import { createTieredPaletteState } from '../../lib/operations/createTieredPaletteState.js';
import { groupTier2Controls } from '../../lib/operations/sliderOps.js';
import AmplitudeSlider from './AmplitudeSlider.vue';
import MultiSegmentToolbar from './MultiSegmentToolbar.vue';
import OperationButton from './OperationButton.vue';

const props = defineProps({
  selectedSegmentIds: {
    type: Array,
    default: () => [],
  },
  selectedShapes: {
    type: Array,
    default: () => [],
  },
  pendingOp: {
    type: String,
    default: null,
  },
});

const emit = defineEmits(['op-invoked']);

const paletteState = computed(() =>
  createTieredPaletteState({
    selectedSegmentIds: props.selectedSegmentIds,
    selectedShapes: props.selectedShapes,
    pendingOp: props.pendingOp,
  }),
);

const tier2Controls = computed(() => groupTier2Controls(paletteState.value.tier2.buttons));

function handleSliderCommit(slider, payload) {
  emit('op-invoked', {
    tier: slider.tier,
    op_name: slider.commitOpName,
    params: { [slider.paramKey]: payload.alpha },
  });
}

const tier0Ref = ref(null);
const tier1Ref = ref(null);
const tier2Ref = ref(null);
const tier3Ref = ref(null);

function getRowEl(index) {
  const refs = [tier0Ref, tier1Ref, tier2Ref, tier3Ref];
  const r = refs[index]?.value;
  return r?.$el ?? r ?? null;
}

function focusTier(index) {
  const el = getRowEl(index);
  el?.querySelector('button:not([disabled])')?.focus();
}

function handleAltKey(event) {
  if (!event.altKey) return;
  const map = { '0': 0, '1': 1, '2': 2, '3': 3 };
  if (event.key in map) {
    event.preventDefault();
    focusTier(map[event.key]);
  }
}

function handleRowArrows(event, tierIndex) {
  if (!['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp'].includes(event.key)) return;
  const el = getRowEl(tierIndex);
  if (!el) return;
  event.preventDefault();
  const buttons = [...el.querySelectorAll('button:not([disabled])')];
  if (!buttons.length) return;
  const idx = buttons.indexOf(document.activeElement);
  const delta = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1;
  buttons[(idx + delta + buttons.length) % buttons.length]?.focus();
}
</script>

<template>
  <section
    class="operation-palette tiered-palette"
    aria-label="Tiered operation palette"
    @keydown="handleAltKey"
  >
    <div
      ref="tier0Ref"
      class="tier-row"
      role="toolbar"
      :aria-label="paletteState.tier0.label"
      @keydown="handleRowArrows($event, 0)"
    >
      <span class="tier-label">{{ paletteState.tier0.label }}</span>
      <div class="tier-buttons">
        <OperationButton
          v-for="btn in paletteState.tier0.buttons"
          :key="btn.op_name"
          :op="btn"
          :enabled="btn.enabled"
          :loading="btn.loading"
          @invoked="emit('op-invoked', $event)"
        />
      </div>
    </div>

    <div
      ref="tier1Ref"
      class="tier-row"
      role="toolbar"
      :aria-label="paletteState.tier1.label"
      @keydown="handleRowArrows($event, 1)"
    >
      <span class="tier-label">{{ paletteState.tier1.label }}</span>
      <div class="tier-buttons">
        <OperationButton
          v-for="btn in paletteState.tier1.buttons"
          :key="btn.op_name"
          :op="btn"
          :enabled="btn.enabled"
          :loading="btn.loading"
          @invoked="emit('op-invoked', $event)"
        />
      </div>
    </div>

    <div
      ref="tier2Ref"
      class="tier-row"
      role="toolbar"
      :aria-label="paletteState.tier2.label"
      :title="paletteState.tier2.intersectionTooltip ?? undefined"
      @keydown="handleRowArrows($event, 2)"
    >
      <span class="tier-label">{{ paletteState.tier2.label }}</span>
      <div class="tier-buttons">
        <template v-for="control in tier2Controls" :key="control.kind === 'slider' ? control.slider.groupId : control.button.op_name">
          <OperationButton
            v-if="control.kind === 'button'"
            :op="control.button"
            :enabled="control.button.enabled"
            :loading="control.button.loading"
            :disabled-tooltip="control.button.disabledTooltip ?? null"
            @invoked="emit('op-invoked', $event)"
          />
          <AmplitudeSlider
            v-else
            :label="control.slider.label"
            :mode="control.slider.mode"
            :disabled="!control.slider.enabled"
            :loading="control.slider.loading"
            :title="!control.slider.enabled && control.slider.disabledTooltip ? control.slider.disabledTooltip : undefined"
            @commit="handleSliderCommit(control.slider, $event)"
          />
        </template>
        <span
          v-if="!paletteState.tier2.buttons.length"
          class="tier-placeholder"
          aria-live="polite"
        >
          {{
            paletteState.tier2.disabled
              ? 'Multi-segment: shape-specific ops unavailable'
              : 'Select a segment to view shape-specific ops'
          }}
        </span>
      </div>
    </div>

    <MultiSegmentToolbar
      ref="tier3Ref"
      :tier="paletteState.tier3"
      @op-invoked="emit('op-invoked', $event)"
      @keydown="handleRowArrows($event, 3)"
    />
  </section>
</template>
