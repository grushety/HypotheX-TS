<script setup>
import { computed } from 'vue';

/**
 * Tiny SVG sparkline. Pure presentational — no state, no events.
 * Renders nothing when ``points.length < 2`` (single value isn't a line).
 */
const props = defineProps({
  points: { type: Array, default: () => [] },
  width: { type: Number, default: 80 },
  height: { type: Number, default: 24 },
  stroke: { type: String, default: 'currentColor' },
});

const path = computed(() => {
  if (!props.points || props.points.length < 2) return '';
  const numeric = props.points.filter(p => Number.isFinite(p));
  if (numeric.length < 2) return '';
  const min = Math.min(...numeric);
  const max = Math.max(...numeric);
  const range = max - min || 1;
  const stepX = props.width / (numeric.length - 1);
  return numeric
    .map((v, i) => {
      const x = i * stepX;
      const y = props.height - ((v - min) / range) * props.height;
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
});
</script>

<template>
  <svg
    v-if="path"
    :width="width"
    :height="height"
    :viewBox="`0 0 ${width} ${height}`"
    role="img"
    :aria-label="`Sparkline of ${points.length} recent values`"
  >
    <path :d="path" :stroke="stroke" stroke-width="1.5" fill="none" />
  </svg>
  <span v-else class="sparkline-empty" aria-hidden="true">—</span>
</template>

<style scoped>
.sparkline-empty {
  color: var(--text-muted, #888);
  font-size: 0.75rem;
}
</style>
