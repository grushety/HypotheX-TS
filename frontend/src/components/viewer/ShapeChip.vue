<script setup>
import { computed } from "vue";

import { getShapeColor } from "../../lib/viewer/shapeColors.js";

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
});

const emit = defineEmits(["segment-selected"]);

const chipColor = computed(() => getShapeColor(props.shape));

const tooltip = computed(() => {
  const parts = [props.shape];
  if (props.semanticLabel) parts.push(props.semanticLabel);
  if (props.confidence != null) parts.push(`${Math.round(props.confidence * 100)}%`);
  if (props.method) parts.push(props.method);
  return parts.join(" | ");
});

function select() {
  emit("segment-selected", props.segmentId);
}
</script>

<template>
  <div
    class="shape-chip"
    :class="{ 'shape-chip-selected': selected }"
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
  </div>
</template>
