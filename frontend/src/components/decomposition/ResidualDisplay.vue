<script setup>
import { computed } from 'vue';

const props = defineProps({
  componentKey: { type: String, required: true },
  componentValues: { type: Array, default: () => [] },
  fitMetadata: { type: Object, default: () => ({}) },
});

const W = 120;
const H = 32;

const stats = computed(() => {
  const vals = props.componentValues;
  if (!vals.length) return { mean: null, std: null };
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  const variance = vals.reduce((acc, v) => acc + (v - mean) ** 2, 0) / vals.length;
  return { mean, std: Math.sqrt(variance) };
});

function sparklinePath(values, width, height) {
  if (values.length < 2) return '';
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  });
  return `M ${pts.join(' L ')}`;
}
</script>

<template>
  <div class="decomp-residual-display" aria-label="Residual component (read-only)">
    <div class="decomp-residual-header">
      <span class="decomp-component-label">{{ componentKey }}</span>
      <span class="decomp-residual-tag">read-only</span>
    </div>
    <svg
      v-if="componentValues.length >= 2"
      class="decomp-sparkline"
      :viewBox="`0 0 ${W} ${H}`"
      :width="W"
      :height="H"
      aria-hidden="true"
    >
      <path
        class="decomp-sparkline-path"
        :d="sparklinePath(componentValues, W, H)"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      />
    </svg>
    <dl class="decomp-residual-stats">
      <div v-if="fitMetadata.rmse != null">
        <dt>RMSE</dt>
        <dd>{{ Number(fitMetadata.rmse).toFixed(4) }}</dd>
      </div>
      <div v-if="stats.mean != null">
        <dt>Mean</dt>
        <dd>{{ stats.mean.toFixed(4) }}</dd>
      </div>
      <div v-if="stats.std != null && componentValues.length > 1">
        <dt>Std</dt>
        <dd>{{ stats.std.toFixed(4) }}</dd>
      </div>
    </dl>
  </div>
</template>
