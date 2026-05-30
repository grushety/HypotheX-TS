<script setup>
import { computed } from "vue";

import { GAUGE_TONES } from "../../lib/evidence/createPlausibilityGaugesState.js";

const props = defineProps({
  state: { type: Object, required: true },
});

// Geometry of the radial gauge: a centered SVG arc whose stroke-dashoffset
// represents the gauge value. Calibrated so a full ring (1.0) covers the
// full 270° sweep from the bottom-left back around to the bottom-right.
const GAUGE_SIZE = 64;
const RADIUS = 26;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const SWEEP_FRACTION = 0.75; // 270° arc
const ARC_LENGTH = CIRCUMFERENCE * SWEEP_FRACTION;

const gauges = computed(() => props.state?.gauges ?? []);

function dashOffsetFor(value) {
  if (!Number.isFinite(value)) return ARC_LENGTH;
  const clamped = Math.max(0, Math.min(1, value));
  return ARC_LENGTH * (1 - clamped);
}

function toneColorVar(tone) {
  if (tone === GAUGE_TONES.CONFIDENT) return "var(--st-pass)";
  if (tone === GAUGE_TONES.MODERATE) return "var(--ink-2)";
  if (tone === GAUGE_TONES.UNCERTAIN) return "var(--st-warn)";
  return "var(--ink-4)";
}
</script>

<template>
  <section class="plaus-gauges" aria-label="Edit quality">
    <header class="plaus-header">
      <span class="mlabel">Edit quality</span>
      <span v-if="!state.hasEdit" class="plaus-empty-hint">apply an edit to score</span>
    </header>

    <div class="plaus-grid" role="group" aria-label="Plausibility gauges">
      <div
        v-for="gauge in gauges"
        :key="gauge.key"
        class="plaus-card"
        :class="{ inactive: gauge.value == null }"
        :title="gauge.hint"
      >
        <svg
          :width="GAUGE_SIZE"
          :height="GAUGE_SIZE"
          :viewBox="`0 0 ${GAUGE_SIZE} ${GAUGE_SIZE}`"
          class="plaus-ring"
          role="meter"
          :aria-label="`${gauge.label} gauge`"
          :aria-valuetext="gauge.displayValue"
          :aria-valuemin="0"
          :aria-valuemax="100"
          :aria-valuenow="gauge.value == null ? undefined : Math.round(gauge.value * 100)"
        >
          <circle
            class="plaus-ring-track"
            :cx="GAUGE_SIZE / 2"
            :cy="GAUGE_SIZE / 2"
            :r="RADIUS"
            fill="none"
            :stroke-dasharray="`${ARC_LENGTH} ${CIRCUMFERENCE}`"
            :transform="`rotate(135 ${GAUGE_SIZE / 2} ${GAUGE_SIZE / 2})`"
          />
          <circle
            v-if="gauge.value != null"
            class="plaus-ring-fill"
            :cx="GAUGE_SIZE / 2"
            :cy="GAUGE_SIZE / 2"
            :r="RADIUS"
            fill="none"
            :stroke="toneColorVar(gauge.tone)"
            :stroke-dasharray="`${ARC_LENGTH} ${CIRCUMFERENCE}`"
            :stroke-dashoffset="dashOffsetFor(gauge.value)"
            :transform="`rotate(135 ${GAUGE_SIZE / 2} ${GAUGE_SIZE / 2})`"
          />
          <text
            class="plaus-ring-value"
            :x="GAUGE_SIZE / 2"
            :y="GAUGE_SIZE / 2 + 4"
            text-anchor="middle"
          >{{ gauge.displayValue }}</text>
        </svg>
        <div class="plaus-name">{{ gauge.label }}</div>
        <div class="plaus-source mlabel-sub">{{ gauge.source }}</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.plaus-gauges {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.plaus-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.mlabel {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.plaus-empty-hint {
  font-size: 11px;
  color: var(--ink-4);
}
.plaus-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
}
.plaus-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 4px 6px;
  background: var(--bg-panel);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  text-align: center;
  cursor: default;
}
.plaus-card.inactive { background: var(--bg-bar); }
.plaus-ring-track {
  stroke: var(--line);
  stroke-width: 5;
  stroke-linecap: round;
}
.plaus-ring-fill {
  stroke-width: 5;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.5s cubic-bezier(0.2, 0.8, 0.3, 1),
              stroke 0.3s;
}
.plaus-ring-value {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  fill: var(--ink);
  font-variant-numeric: tabular-nums;
}
.plaus-card.inactive .plaus-ring-value { fill: var(--ink-4); }
.plaus-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-2);
}
.plaus-source {
  font-family: var(--font-mono);
  font-size: 8.5px;
  letter-spacing: 0.03em;
  color: var(--ink-4);
  line-height: 1.2;
}
</style>
