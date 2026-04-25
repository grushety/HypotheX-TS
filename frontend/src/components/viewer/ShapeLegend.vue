<script setup>
import { SHAPE_COLORS } from "../../lib/viewer/shapeColors.js";

const shapes = Object.entries(SHAPE_COLORS);

defineProps({
  /** When a domain pack is active, pass semantic labels keyed by shape. */
  semanticLabels: {
    type: Object,
    default: () => ({}),
  },
});
</script>

<template>
  <div class="shape-legend" aria-label="Shape legend">
    <div
      v-for="[shape, color] in shapes"
      :key="shape"
      class="shape-legend-item"
    >
      <span
        class="shape-legend-swatch"
        :style="{ backgroundColor: color }"
        aria-hidden="true"
      />
      <span class="shape-legend-label">{{ shape }}</span>
      <span
        v-if="semanticLabels[shape]"
        class="shape-legend-semantic"
      >{{ semanticLabels[shape] }}</span>
    </div>
  </div>
</template>
