<script setup>
import { computed } from "vue";

import { getShapeColor } from "../../lib/viewer/shapeColors.js";
import GapIndicator from "../gaps/GapIndicator.vue";

const props = defineProps({
  segmentId: {
    type: String,
    required: true,
  },
  shape: {
    type: String,
    required: true,
  },
  confidence: {
    type: Number,
    default: null,
  },
  method: {
    type: String,
    default: null,
  },
  semanticLabel: {
    type: String,
    default: null,
  },
  selected: {
    type: Boolean,
    default: false,
  },
  isCloudGap: {
    type: Boolean,
    default: false,
  },
  isFilled: {
    type: Boolean,
    default: false,
  },
  fillStrategy: {
    type: String,
    default: null,
  },
  missingnessPct: {
    type: Number,
    default: 0,
  },
});

const emit = defineEmits(["segment-selected"]);

const chipColor = computed(() => getShapeColor(props.shape));

const showGap = computed(() => props.isCloudGap || props.missingnessPct > 0);

const tooltip = computed(() => {
  const parts = [props.shape];
  if (props.semanticLabel) parts.push(props.semanticLabel);
  if (props.confidence != null) parts.push(`${Math.round(props.confidence * 100)}%`);
  if (props.method) parts.push(props.method);
  if (showGap.value) {
    parts.push(`${props.missingnessPct}% missing${props.isFilled ? " (filled)" : ""}`);
  }
  return parts.join(" | ");
});

function select() {
  emit("segment-selected", props.segmentId);
}
</script>

<template>
  <div
    class="shape-chip"
    :class="{
      'shape-chip-selected': selected,
      'shape-chip-gap': showGap && !isFilled,
    }"
    :style="{ backgroundColor: chipColor }"
    :title="tooltip"
    role="button"
    tabindex="0"
    :aria-pressed="selected"
    @click="select"
    @keydown.enter.prevent="select"
    @keydown.space.prevent="select"
  >
    <span class="shape-chip-label">{{ shape }}</span>
    <span v-if="semanticLabel" class="shape-chip-semantic">{{ semanticLabel }}</span>
    <GapIndicator
      v-if="showGap || isFilled"
      :is-cloud-gap="isCloudGap"
      :is-filled="isFilled"
      :fill-strategy="fillStrategy"
      :missingness-pct="missingnessPct"
    />
  </div>
</template>

<style scoped>
.shape-chip-gap {
  background-image: repeating-linear-gradient(
    45deg,
    rgba(0, 0, 0, 0.18) 0,
    rgba(0, 0, 0, 0.18) 2px,
    transparent 2px,
    transparent 6px
  );
}
</style>
