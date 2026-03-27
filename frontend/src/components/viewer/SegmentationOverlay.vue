<script setup>
import { computed } from "vue";

import { createSegmentationOverlayModel, SEGMENT_LABEL_STYLES } from "../../lib/segments/createSegmentationOverlayModel";

const props = defineProps({
  segments: {
    type: Array,
    default: () => [],
  },
  seriesLength: {
    type: Number,
    default: 0,
  },
  selectedSegmentId: {
    type: String,
    default: null,
  },
});

const emit = defineEmits(["select-segment"]);

const overlayModel = computed(() =>
  createSegmentationOverlayModel(props.segments, props.seriesLength),
);
</script>

<template>
  <div class="segmentation-overlay" aria-label="Segmentation overlay">
    <div class="segmentation-track">
      <div
        v-for="segment in overlayModel.spans"
        :key="segment.id"
        class="segment-span"
        :class="[
          `segment-span-${segment.label}`,
          { 'segment-span-active': segment.id === selectedSegmentId },
        ]"
        :style="{ left: segment.left, width: segment.width }"
        role="button"
        tabindex="0"
        :aria-pressed="segment.id === selectedSegmentId"
        @click="emit('select-segment', segment.id)"
        @keydown.enter.prevent="emit('select-segment', segment.id)"
        @keydown.space.prevent="emit('select-segment', segment.id)"
      >
        <span class="segment-label-pill">{{ segment.label }}</span>
      </div>

      <div
        v-for="boundary in overlayModel.boundaries"
        :key="boundary.id"
        class="segment-boundary"
        :style="{ left: boundary.left }"
      />
    </div>

    <div class="segment-legend">
      <div v-for="style in SEGMENT_LABEL_STYLES" :key="style.label" class="segment-legend-item">
        <span class="segment-legend-swatch" :class="`segment-span-${style.label}`" />
        <span>{{ style.label }}</span>
      </div>
    </div>
  </div>
</template>
