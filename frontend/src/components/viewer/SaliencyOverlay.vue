<script setup>
import { computed } from "vue";

import { createSaliencyOverlayModel } from "../../lib/saliency/createSaliencyOverlayModel.js";

const props = defineProps({
  attribution: { type: Array, default: null },
  method: { type: String, default: "" },
  reference: { type: String, default: "" },
  loading: { type: Boolean, default: false },
  error: { type: String, default: null },
});

const overlayModel = computed(() =>
  createSaliencyOverlayModel(props.attribution ?? [], {
    width: 720,
    bounds: { left: 52, right: 702 },
    height: 14,
  }),
);

const hasData = computed(() => Array.isArray(props.attribution) && props.attribution.length > 0);
</script>

<template>
  <div class="saliency-overlay" :aria-busy="loading">
    <div v-if="loading" class="saliency-state saliency-loading" role="status">
      <span class="spin" aria-hidden="true" />
      Computing saliency…
    </div>
    <div v-else-if="error" class="saliency-state saliency-error" role="alert">
      Saliency failed · {{ error }}
    </div>
    <template v-else-if="hasData">
      <svg
        class="saliency-svg"
        viewBox="0 0 720 14"
        preserveAspectRatio="none"
        role="img"
        :aria-label="`Saliency heatmap (${method})`"
      >
        <rect
          v-for="cell in overlayModel.cells"
          :key="cell.index"
          :x="cell.x"
          :y="0"
          :width="cell.width"
          :height="14"
          :fill="cell.fill"
          :fill-opacity="cell.opacity"
        />
      </svg>
      <div class="saliency-legend">
        <span class="saliency-name">Saliency</span>
        <span class="saliency-key">
          <span class="sw pos" aria-hidden="true" />
          informative
          <span class="sw neg" aria-hidden="true" />
          counter-evidence
        </span>
        <span class="saliency-method" :title="reference">{{ method }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.saliency-overlay {
  width: 100%;
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.saliency-svg {
  width: 100%;
  height: 14px;
  display: block;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.45);
  border: 1px solid var(--line);
}
.saliency-state {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11.5px;
  padding: 4px 9px;
  border-radius: var(--r-sm);
}
.saliency-loading {
  color: var(--ink-2);
  background: var(--bg-sunken);
  border: 1px solid var(--line);
}
.saliency-error {
  color: #b3650a;
  background: var(--st-warn-bg);
  border: 1px solid #e8c98f;
}
.spin {
  width: 12px;
  height: 12px;
  border: 2px solid var(--line-2);
  border-top-color: var(--ink-2);
  border-radius: 50%;
  animation: sal-spin 0.7s linear infinite;
}
@keyframes sal-spin { to { transform: rotate(360deg); } }

.saliency-legend {
  display: flex;
  align-items: center;
  gap: 11px;
  flex-wrap: wrap;
  font-size: 10.5px;
  color: var(--ink-3);
}
.saliency-name {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.saliency-key {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.saliency-key .sw {
  display: inline-block;
  width: 14px;
  height: 6px;
  border-radius: 2px;
}
.saliency-key .sw.pos { background: #e8870c; }
.saliency-key .sw.neg { background: #2b4ad6; }
.saliency-method {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-4);
  margin-left: auto;
  cursor: help;
}
</style>
