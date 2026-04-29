<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

import { labelChipBus } from '../../lib/audit/labelChipBus.js';
import {
  createLabelChipDisplayModel,
  DEFAULT_ACCEPT_TIMER_SECONDS,
  tickTimer,
  TIMER_TICK_MS,
} from '../../lib/relabel/createLabelChipState.js';
import ShapePicker from './ShapePicker.vue';

const props = defineProps({
  acceptTimerSeconds: {
    type: Number,
    default: DEFAULT_ACCEPT_TIMER_SECONDS,
  },
});

const emit = defineEmits(['accept', 'override', 'undo', 'dismiss']);

const activeChip = ref(null);
const elapsedMs = ref(0);
const showPicker = ref(false);
const overrideButtonEl = ref(null);

let unsubscribe = null;
let tickInterval = null;

const acceptTimerMs = computed(() => props.acceptTimerSeconds * 1000);

const model = computed(() =>
  activeChip.value ? createLabelChipDisplayModel(activeChip.value) : null,
);

const timerState = computed(() =>
  model.value ? tickTimer(acceptTimerMs.value, elapsedMs.value) : null,
);

const RING_R = 10;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_R;

const ringOffset = computed(() => {
  if (!timerState.value) return RING_CIRCUMFERENCE;
  return RING_CIRCUMFERENCE * (1 - timerState.value.fraction);
});

function startTimer() {
  clearInterval(tickInterval);
  elapsedMs.value = 0;
  tickInterval = setInterval(() => {
    elapsedMs.value += TIMER_TICK_MS;
    if (timerState.value?.fired) {
      handleAutoAccept();
    }
  }, TIMER_TICK_MS);
}

function stopTimer() {
  clearInterval(tickInterval);
  tickInterval = null;
}

function dismiss() {
  stopTimer();
  activeChip.value = null;
  showPicker.value = false;
  elapsedMs.value = 0;
  emit('dismiss');
}

function handleAutoAccept() {
  if (!model.value) return;
  const m = model.value;
  stopTimer();
  emit('accept', { chipId: m.chipId, segmentId: m.segmentId, newShape: m.newShape, opId: m.opId });
  dismiss();
}

function handleAccept() {
  if (!model.value) return;
  const m = model.value;
  stopTimer();
  emit('accept', { chipId: m.chipId, segmentId: m.segmentId, newShape: m.newShape, opId: m.opId });
  dismiss();
}

function handleOverrideOpen() {
  showPicker.value = true;
}

function handleShapeSelected(shape) {
  if (!model.value) return;
  const m = model.value;
  stopTimer();
  emit('override', { chipId: m.chipId, segmentId: m.segmentId, chosenShape: shape, opId: m.opId });
  dismiss();
}

function handleUndo() {
  if (!model.value) return;
  const m = model.value;
  stopTimer();
  emit('undo', { chipId: m.chipId, segmentId: m.segmentId, opId: m.opId });
  dismiss();
}

watch(model, async (newModel) => {
  if (newModel?.shouldAutoFocusOverride) {
    await nextTick();
    overrideButtonEl.value?.focus();
  }
});

onMounted(() => {
  unsubscribe = labelChipBus.subscribe((chip) => {
    stopTimer();
    activeChip.value = chip;
    showPicker.value = false;
    startTimer();
  });
});

onUnmounted(() => {
  stopTimer();
  if (unsubscribe) unsubscribe();
});
</script>

<template>
  <div
    v-if="model"
    class="label-chip"
    :class="{
      'label-chip-low-confidence': model.isLowConfidenceReclassify,
    }"
    role="status"
    aria-live="polite"
    :aria-label="`Label prediction: ${model.displayText}`"
  >
    <div class="label-chip-body">
      <svg
        class="label-chip-ring"
        :width="RING_R * 2 + 6"
        :height="RING_R * 2 + 6"
        aria-hidden="true"
      >
        <circle
          class="label-chip-ring-bg"
          :cx="RING_R + 3"
          :cy="RING_R + 3"
          :r="RING_R"
          fill="none"
          stroke-width="3"
        />
        <circle
          class="label-chip-ring-fg"
          :cx="RING_R + 3"
          :cy="RING_R + 3"
          :r="RING_R"
          fill="none"
          stroke-width="3"
          :stroke-dasharray="`${RING_CIRCUMFERENCE} ${RING_CIRCUMFERENCE}`"
          :stroke-dashoffset="ringOffset"
          transform="rotate(-90, 13, 13)"
        />
      </svg>

      <span class="label-chip-text">{{ model.displayText }}</span>
    </div>

    <div class="label-chip-actions">
      <button
        class="label-chip-btn label-chip-btn-accept"
        type="button"
        @click="handleAccept"
      >
        Accept
      </button>
      <button
        ref="overrideButtonEl"
        class="label-chip-btn label-chip-btn-override"
        type="button"
        @click="handleOverrideOpen"
      >
        Override
      </button>
      <button
        class="label-chip-btn label-chip-btn-undo"
        type="button"
        @click="handleUndo"
      >
        Undo
      </button>
    </div>

    <ShapePicker
      v-if="showPicker"
      @select="handleShapeSelected"
      @close="showPicker = false"
    />
  </div>
</template>
