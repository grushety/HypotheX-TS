<script setup>
import { computed } from 'vue';

import { formatDistance } from '../../lib/donors/createDonorPickerState.js';

const props = defineProps({
  candidate: { type: Object, required: true },
  metricLabel: { type: String, default: 'distance' },
  selected: { type: Boolean, default: false },
});

const emit = defineEmits(['select', 'accept']);

const SPARKLINE_WIDTH = 120;
const SPARKLINE_HEIGHT = 32;

const sparklinePath = computed(() => {
  const values = props.candidate?.values ?? [];
  if (!Array.isArray(values) || values.length < 2) return '';
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (hi === lo) hi = lo + 1;
  const span = hi - lo;
  const n = values.length;
  const points = values.map((v, i) => {
    const x = (i / (n - 1)) * SPARKLINE_WIDTH;
    const y = SPARKLINE_HEIGHT - ((v - lo) / span) * SPARKLINE_HEIGHT;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return `M ${points.join(' L ')}`;
});

const distanceLabel = computed(() => formatDistance(props.candidate?.distance));

function handleSelect() {
  emit('select', props.candidate.donor_id);
}

function handleAccept(event) {
  event.stopPropagation();
  emit('accept', props.candidate.donor_id);
}
</script>

<template>
  <article
    class="donor-card"
    :class="{ 'donor-card--selected': selected }"
    role="button"
    tabindex="0"
    :aria-pressed="selected"
    :aria-label="`Donor candidate ${candidate.donor_id}, ${metricLabel} ${distanceLabel}`"
    @click="handleSelect"
    @keydown.enter.prevent="handleSelect"
    @keydown.space.prevent="handleSelect"
  >
    <svg
      class="donor-card__sparkline"
      :viewBox="`0 0 ${SPARKLINE_WIDTH} ${SPARKLINE_HEIGHT}`"
      :width="SPARKLINE_WIDTH"
      :height="SPARKLINE_HEIGHT"
      role="img"
      aria-hidden="true"
    >
      <path
        v-if="sparklinePath"
        :d="sparklinePath"
        fill="none"
        stroke="currentColor"
        stroke-width="1.4"
      />
    </svg>
    <div class="donor-card__info">
      <span class="donor-card__id">{{ candidate.donor_id }}</span>
      <span class="donor-card__metric">{{ metricLabel }}: {{ distanceLabel }}</span>
    </div>
    <button
      type="button"
      class="donor-card__accept"
      aria-label="Accept this donor"
      @click="handleAccept"
    >
      Accept
    </button>
  </article>
</template>

<style scoped>
.donor-card {
  display: grid;
  grid-template-columns: max-content 1fr max-content;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 6px;
  background: var(--surface, #ffffff);
  cursor: pointer;
  font-size: 0.85rem;
  color: inherit;
}
.donor-card:focus-visible {
  outline: 2px solid var(--focus-ring, #0a3d91);
  outline-offset: 2px;
}
.donor-card--selected {
  border-color: var(--focus-ring, #0a3d91);
  background: rgba(10, 61, 145, 0.05);
}
.donor-card__sparkline {
  color: #2b6f8d;
  flex-shrink: 0;
}
.donor-card__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.donor-card__id {
  font-weight: 600;
  font-family: var(--font-mono, ui-monospace, "SFMono-Regular", Consolas, monospace);
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.donor-card__metric {
  font-size: 0.78rem;
  color: #6b6f8d;
}
.donor-card__accept {
  font: inherit;
  padding: 4px 10px;
  border: 1px solid var(--border-subtle, #d0d7de);
  border-radius: 4px;
  background: var(--surface, #ffffff);
  cursor: pointer;
  font-size: 0.78rem;
}
.donor-card__accept:hover {
  background: rgba(10, 61, 145, 0.08);
}
</style>
