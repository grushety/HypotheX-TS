<script setup>
import { computed } from 'vue';

import { SUPPRESS_STRATEGY_LABELS } from '../../lib/gaps/createGapGatingState.js';

const props = defineProps({
  isCloudGap: { type: Boolean, default: false },
  isFilled: { type: Boolean, default: false },
  fillStrategy: { type: String, default: null },
  missingnessPct: { type: Number, default: 0 },
});

const filledLabel = computed(() => {
  const strat = props.fillStrategy;
  if (!strat) return 'filled';
  return `filled (${SUPPRESS_STRATEGY_LABELS[strat] ?? strat})`;
});

const cloudGapLabel = computed(() =>
  props.missingnessPct > 0
    ? `cloud gap, ${props.missingnessPct}% missing`
    : 'cloud gap',
);
</script>

<template>
  <span class="gap-indicator" v-if="isCloudGap || isFilled">
    <span
      v-if="isCloudGap"
      class="gap-indicator__icon"
      role="img"
      :aria-label="cloudGapLabel"
      :title="cloudGapLabel"
    >
      ☁
    </span>
    <span
      v-if="isFilled"
      class="gap-indicator__filled"
      role="img"
      :aria-label="filledLabel"
      :title="filledLabel"
    >
      ✓ {{ fillStrategy ?? 'filled' }}
    </span>
  </span>
</template>

<style scoped>
.gap-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.72rem;
  vertical-align: middle;
}
.gap-indicator__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.06);
  color: #41526a;
  font-size: 10px;
  cursor: help;
}
.gap-indicator__filled {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px 5px;
  border-radius: 9px;
  background: rgba(26, 127, 55, 0.12);
  color: #1a7f37;
  font-weight: 600;
  font-size: 0.7rem;
  letter-spacing: 0.02em;
  cursor: help;
}
</style>
