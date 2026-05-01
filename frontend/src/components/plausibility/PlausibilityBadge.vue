<script setup>
import { computed } from 'vue';

import { createPlausibilityBadgeState } from '../../lib/plausibility/createPlausibilityBadgeState.js';

const props = defineProps({
  range: { type: Object, default: null },
  residual: { type: Object, default: null },
  manifold: { type: Object, default: null },
  manifoldEnabled: { type: Boolean, default: false },
});

const state = computed(() =>
  createPlausibilityBadgeState({
    range: props.range,
    residual: props.residual,
    manifold: props.manifold,
    manifoldEnabled: props.manifoldEnabled,
  }),
);
</script>

<template>
  <span
    class="plausibility-badge"
    :class="`plausibility-badge--${state.status}`"
    role="img"
    :aria-label="state.ariaLabel"
    :title="state.hoverText"
    :data-status="state.status"
  >
    <span class="plausibility-badge__glyph" aria-hidden="true">{{ state.glyph }}</span>
  </span>
</template>

<style scoped>
.plausibility-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  border: 1px solid currentColor;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  font-family: var(--font-mono, ui-monospace, "SFMono-Regular", Consolas, monospace);
  cursor: help;
  white-space: nowrap;
  vertical-align: middle;
  flex-shrink: 0;
}

.plausibility-badge__glyph {
  pointer-events: none;
}

.plausibility-badge--green {
  color: #1a7f37;
  background: #e8f5ec;
  border-color: #95d5a2;
}

.plausibility-badge--amber {
  color: #9a6700;
  background: #fff8c5;
  border-color: #d4a72c;
}

.plausibility-badge--red {
  color: #cf222e;
  background: #ffebe9;
  border-color: #ff8182;
}
</style>
