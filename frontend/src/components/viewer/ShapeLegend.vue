<script setup>
import { SHAPE_COLORS, SHAPE_LABELS } from "../../lib/viewer/shapeColors.js";

const SHAPE_DISPLAY = {
  plateau: "Plateau",
  trend: "Trend",
  step: "Step",
  spike: "Spike",
  cycle: "Cycle",
  transient: "Transient",
  noise: "Noise",
};

defineProps({
  /** When a domain pack is active, pass semantic labels keyed by shape. */
  semanticLabels: {
    type: Object,
    default: () => ({}),
  },
});
</script>

<template>
  <div class="shape-legend" role="group" aria-label="Shape-atom vocabulary">
    <span class="lg-head">
      Shape atoms
      <span class="lg-head-sub">— the primitive each band's colour encodes</span>
    </span>
    <div class="lg-items">
      <span v-for="shape in SHAPE_LABELS" :key="shape" class="lg-item">
        <span
          class="lg-sw"
          :style="{ background: SHAPE_COLORS[shape] }"
          aria-hidden="true"
        />
        {{ SHAPE_DISPLAY[shape] }}
        <span
          v-if="semanticLabels[shape]"
          class="lg-dm"
        >· {{ semanticLabels[shape] }}</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.shape-legend {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
  padding: 8px 10px;
  background: var(--bg-sunken);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
}
.lg-head {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.lg-head-sub {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: normal;
  text-transform: none;
  color: var(--ink-3);
  margin-left: 4px;
}
.lg-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
}
.lg-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--ink-2);
}
.lg-sw {
  display: inline-block;
  width: 14px;
  height: 8px;
  border-radius: 2px;
  flex: none;
  box-shadow: inset 0 0 0 1px rgba(20, 27, 38, 0.10);
}
.lg-dm {
  color: var(--ink-3);
  font-size: 11px;
}
</style>
