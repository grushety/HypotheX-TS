<script setup>
import { computed, ref } from 'vue';

import {
  MIN_ALPHA,
  MAX_ALPHA,
  IDENTITY,
  AMPLIFY_ONLY_MIN,
  positionToAlpha,
  alphaToPosition,
  snapToCommon,
  classify,
  formatMultiplier,
  stepAlpha,
  isIdentity,
} from '../../lib/operations/amplitudeSlider.js';

const props = defineProps({
  label: {
    type: String,
    default: 'Amplitude',
  },
  mode: {
    type: String,
    default: 'bidirectional', // 'bidirectional' | 'amplify-only'
    validator: (v) => v === 'bidirectional' || v === 'amplify-only',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['commit']);

const alpha = ref(IDENTITY);
const trackResolution = 1000;

const minAlpha = computed(() =>
  props.mode === 'amplify-only' ? AMPLIFY_ONLY_MIN : MIN_ALPHA,
);

const minPosition = computed(() => alphaToPosition(minAlpha.value));

function alphaToTrackInt(a) {
  return Math.round(alphaToPosition(a) * trackResolution);
}

function trackIntToAlpha(t) {
  return positionToAlpha(t / trackResolution);
}

const sliderValue = computed({
  get: () => alphaToTrackInt(alpha.value),
  set: (raw) => {
    let next = trackIntToAlpha(Number(raw));
    if (next < minAlpha.value) next = minAlpha.value;
    next = snapToCommon(next);
    alpha.value = next;
  },
});

const zone = computed(() => classify(alpha.value));
const multiplierLabel = computed(() => formatMultiplier(alpha.value));
const linearLabel = computed(() => alpha.value.toFixed(3));

function commit() {
  if (props.disabled || props.loading) return;
  if (isIdentity(alpha.value)) return;
  emit('commit', { alpha: alpha.value });
}

function resetToIdentity() {
  alpha.value = IDENTITY;
}

function applyKeyboardStep(direction) {
  let next = stepAlpha(alpha.value, direction);
  if (next < minAlpha.value) next = minAlpha.value;
  alpha.value = next;
}

function handleKeydown(event) {
  if (props.disabled || props.loading) return;
  switch (event.key) {
    case 'ArrowRight':
    case 'ArrowUp':
      event.preventDefault();
      applyKeyboardStep(+1);
      commit();
      break;
    case 'ArrowLeft':
    case 'ArrowDown':
      event.preventDefault();
      applyKeyboardStep(-1);
      commit();
      break;
    case 'Home':
      event.preventDefault();
      alpha.value = minAlpha.value;
      commit();
      break;
    case 'End':
      event.preventDefault();
      alpha.value = MAX_ALPHA;
      commit();
      break;
    case '1':
      event.preventDefault();
      resetToIdentity();
      break;
    case 'Enter':
      event.preventDefault();
      commit();
      break;
    default:
      break;
  }
}
</script>

<template>
  <div
    class="amplitude-slider"
    :class="[`amplitude-slider--zone-${zone}`, { 'amplitude-slider--disabled': disabled }]"
    role="group"
    :aria-label="label"
  >
    <div class="amplitude-slider__header">
      <span class="amplitude-slider__label">{{ label }}</span>
      <span class="amplitude-slider__zone-badge" aria-live="polite">
        {{ zone === 'identity' ? 'identity' : zone }}
      </span>
    </div>

    <div class="amplitude-slider__track-row">
      <span class="amplitude-slider__zone-text amplitude-slider__zone-text--left">dampen</span>
      <input
        v-model.number="sliderValue"
        class="amplitude-slider__track"
        type="range"
        :min="Math.round(minPosition * trackResolution)"
        :max="trackResolution"
        :step="1"
        :disabled="disabled || loading"
        :aria-valuetext="multiplierLabel"
        @change="commit"
        @keydown="handleKeydown"
      />
      <span class="amplitude-slider__zone-text amplitude-slider__zone-text--right">amplify</span>
    </div>

    <div class="amplitude-slider__readout">
      <span class="amplitude-slider__readout-mult">{{ multiplierLabel }}</span>
      <span class="amplitude-slider__readout-linear">α={{ linearLabel }}</span>
      <button
        type="button"
        class="amplitude-slider__reset"
        :disabled="disabled || loading || isIdentity(alpha)"
        title="Reset to identity (×1.00)"
        @click="resetToIdentity"
      >
        reset
      </button>
    </div>
  </div>
</template>

<style scoped>
.amplitude-slider {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 10px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: var(--surface-subtle, #f6f8fa);
  min-width: 240px;
}
.amplitude-slider--disabled {
  opacity: 0.55;
}
.amplitude-slider__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 0.85em;
}
.amplitude-slider__label {
  font-weight: 600;
}
.amplitude-slider__zone-badge {
  font-variant: small-caps;
  letter-spacing: 0.04em;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--badge-bg, #eaeef2);
}
.amplitude-slider--zone-dampen .amplitude-slider__zone-badge {
  background: #cfe3ff;
  color: #0a3d91;
}
.amplitude-slider--zone-amplify .amplitude-slider__zone-badge {
  background: #ffd6d3;
  color: #8a1f1f;
}
.amplitude-slider__track-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.amplitude-slider__zone-text {
  font-size: 0.7em;
  text-transform: lowercase;
  opacity: 0.7;
  min-width: 3.5em;
}
.amplitude-slider__zone-text--left { text-align: right; color: #0a3d91; }
.amplitude-slider__zone-text--right { text-align: left; color: #8a1f1f; }
.amplitude-slider__track {
  flex: 1;
  background: linear-gradient(
    to right,
    #cfe3ff 0%,
    #cfe3ff 50%,
    #ffd6d3 50%,
    #ffd6d3 100%
  );
  border-radius: 4px;
  appearance: none;
  height: 6px;
}
.amplitude-slider__track:focus-visible {
  outline: 2px solid var(--focus-ring, #0a3d91);
  outline-offset: 2px;
}
.amplitude-slider__readout {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 0.8em;
}
.amplitude-slider__readout-mult {
  font-weight: 700;
}
.amplitude-slider__readout-linear {
  opacity: 0.7;
  font-variant-numeric: tabular-nums;
}
.amplitude-slider__reset {
  margin-left: auto;
  font-size: 0.85em;
  padding: 2px 8px;
  background: transparent;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 4px;
  cursor: pointer;
}
.amplitude-slider__reset:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
