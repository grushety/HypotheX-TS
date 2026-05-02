<script setup>
import { computed, ref } from 'vue';

import Sparkline from './Sparkline.vue';

/**
 * Shared metric row. The five named row components (CoverageRow,
 * DiversityRow, ValidityRow, CherryPickingRow, ForkingPathsRow) each
 * render this with a different ``row`` payload.
 *
 * Lisnic 2025 design language:
 *   - traffic-light icon is decorative (aria-hidden); the row's
 *     ``aria-label`` carries the colour and value verbally.
 *   - the pulse animation is a 1 s border highlight, dismissable.
 *   - the citation is in a hover-revealed tooltip (a ``<details>``
 *     element keeps it keyboard-accessible without a custom popper).
 */
const props = defineProps({
  row: { type: Object, required: true },
  trafficLight: { type: String, default: 'idle' },
});

const emit = defineEmits(['dismiss-pulse']);

const expanded = ref(false);

const valueDisplay = computed(() => {
  if (props.row.value == null || Number.isNaN(props.row.value)) return '—';
  if (Number.isInteger(props.row.value)) return String(props.row.value);
  return Number(props.row.value).toFixed(3);
});

const ariaLabel = computed(() =>
  `${props.row.label}: ${valueDisplay.value} (${props.trafficLight})`,
);

function handleDismiss() {
  emit('dismiss-pulse', props.row.key);
}
</script>

<template>
  <article
    class="guardrails-row"
    :class="[
      `traffic-${trafficLight}`,
      { foreground: row.foreground, pulse: row.pulse, pending: row.pendingBackend },
    ]"
    :aria-label="ariaLabel"
  >
    <header class="row-header">
      <span class="traffic-dot" :class="`dot-${trafficLight}`" aria-hidden="true" />
      <span class="row-label">{{ row.label }}</span>
      <span class="row-value">{{ valueDisplay }}</span>
      <Sparkline :points="row.history" :width="60" :height="18" />
      <button
        v-if="row.pulse"
        type="button"
        class="pulse-dismiss"
        @click="handleDismiss"
        aria-label="Dismiss alert"
      >
        ✕
      </button>
    </header>
    <div v-if="row.tipShouldFire && row.recommendation" class="row-recommendation">
      {{ row.recommendation }}
    </div>
    <details class="row-details" @toggle="expanded = $event.target.open">
      <summary>About this metric</summary>
      <p class="row-citation">{{ row.citation }}</p>
      <p v-if="row.pendingBackend" class="row-pending">
        Backend metric not yet enabled — this row reserves the layout for a
        future ticket.
      </p>
    </details>
  </article>
</template>

<style scoped>
.guardrails-row {
  border: 1px solid var(--row-border, #e0e0e0);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
  background: var(--row-bg, #fafafa);
  transition: border-color 0.2s, background 0.2s;
}
.guardrails-row.foreground {
  border-color: var(--row-border-foreground, #d97706);
}
.guardrails-row.pulse {
  animation: guardrails-pulse 1s ease-out 1;
}
.guardrails-row.pending {
  opacity: 0.6;
}
@keyframes guardrails-pulse {
  0% { box-shadow: 0 0 0 0 rgba(217, 119, 6, 0.6); }
  100% { box-shadow: 0 0 0 8px rgba(217, 119, 6, 0); }
}
.row-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.row-label {
  flex: 1;
  font-size: 0.85rem;
  font-weight: 500;
}
.row-value {
  font-variant-numeric: tabular-nums;
  font-size: 0.85rem;
  color: var(--text-muted, #555);
}
.traffic-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot-green { background: #16a34a; }
.dot-amber { background: #d97706; }
.dot-red { background: #dc2626; }
.dot-idle { background: #9ca3af; }
.dot-disabled { background: transparent; border: 1px dashed #9ca3af; }
.row-recommendation {
  font-size: 0.8rem;
  color: var(--text-recommendation, #92400e);
  margin-top: 0.25rem;
}
.row-details {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--text-muted, #555);
}
.row-details summary {
  cursor: pointer;
}
.row-citation {
  margin: 0.25rem 0 0;
}
.row-pending {
  margin: 0.25rem 0 0;
  font-style: italic;
}
.pulse-dismiss {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--text-muted, #555);
  padding: 0 0.25rem;
}
</style>
