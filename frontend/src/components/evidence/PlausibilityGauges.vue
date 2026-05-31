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
      <slot name="pin" />
      <span
        v-if="state.offDistribution"
        class="plaus-offdist"
        role="status"
        :title="state.offDistributionReason"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" />
          <path d="M12 9v4" />
          <path d="M12 17h.01" />
        </svg>
        OFF-DISTRIBUTION
      </span>
    </header>

    <div class="plaus-grid" role="group" aria-label="Plausibility gauges">
      <div
        v-for="gauge in gauges"
        :key="gauge.key"
        class="plaus-card"
        :class="{
          inactive: gauge.value == null,
          'tone-warn': gauge.tone === 'uncertain',
        }"
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
          :aria-describedby="`gauge-tip-${gauge.key}`"
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
        <div :id="`gauge-tip-${gauge.key}`" class="plaus-tip" role="tooltip">
          <div class="plaus-tip-hint">{{ gauge.hint }}</div>
          <div class="plaus-tip-source">{{ gauge.source }}</div>
          <div v-if="gauge.reference" class="plaus-tip-ref">{{ gauge.reference }}</div>
        </div>
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
/* off-distribution badge in the header — fires only when yNN is below threshold */
.plaus-offdist {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--st-warn);
  background: var(--st-warn-bg);
  border: 1px solid #e8c98f;
  border-radius: 3px;
  padding: 2px 7px;
  animation: plaus-offdist-pulse 1.6s ease-in-out infinite;
}
.plaus-offdist svg { width: 12px; height: 12px; }
@keyframes plaus-offdist-pulse {
  50% { background: rgba(232, 135, 12, 0.18); }
}

/* warn-toned gauge card — only when its own tone is 'uncertain' */
.plaus-card.tone-warn {
  border-color: #e8c98f;
  box-shadow: inset 0 -2px 0 var(--st-warn);
}

/* anchored tooltip — appears on hover/focus of the card. Naming the metric
   + paper reference satisfies REWORK-06 AC. */
.plaus-card { position: relative; }
.plaus-tip {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 50%;
  transform: translateX(-50%);
  width: max-content;
  max-width: 240px;
  background: var(--ink);
  color: #fff;
  border-radius: var(--r-sm);
  padding: 7px 9px;
  font-size: 11px;
  line-height: 1.45;
  box-shadow: var(--shadow-pop);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s;
  z-index: 5;
}
.plaus-card:hover .plaus-tip,
.plaus-card:focus-within .plaus-tip { opacity: 1; }
.plaus-tip-hint { font-weight: 600; }
.plaus-tip-source {
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.78);
  margin-top: 4px;
}
.plaus-tip-ref {
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: rgba(255, 255, 255, 0.62);
  margin-top: 3px;
  font-style: italic;
}
</style>
