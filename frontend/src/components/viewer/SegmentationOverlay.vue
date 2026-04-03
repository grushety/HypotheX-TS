<script setup>
import { computed, onBeforeUnmount, ref } from "vue";

import { createSegmentationOverlayModel, SEGMENT_LABEL_STYLES } from "../../lib/segments/createSegmentationOverlayModel";
import { getBoundaryStartFromClientX } from "../../lib/segments/getBoundaryStartFromClientX";

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
  segmentUncertainty: {
    type: Array,
    default: () => [],
  },
  boundaryUncertainty: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["select-segment", "move-boundary"]);

const overlayModel = computed(() =>
  createSegmentationOverlayModel(props.segments, props.seriesLength),
);
const trackRef = ref(null);
const draggingBoundaryIndex = ref(null);

function stopDrag() {
  draggingBoundaryIndex.value = null;
  window.removeEventListener("pointermove", handlePointerMove);
  window.removeEventListener("pointerup", stopDrag);
}

function handlePointerMove(event) {
  if (draggingBoundaryIndex.value === null || !trackRef.value) {
    return;
  }

  const nextBoundaryStart = getBoundaryStartFromClientX(
    event.clientX,
    trackRef.value.getBoundingClientRect(),
    props.seriesLength,
  );

  emit("move-boundary", {
    boundaryIndex: draggingBoundaryIndex.value,
    nextBoundaryStart,
  });
}

function startDrag(boundaryIndex, event) {
  draggingBoundaryIndex.value = boundaryIndex;
  handlePointerMove(event);
  window.addEventListener("pointermove", handlePointerMove);
  window.addEventListener("pointerup", stopDrag);
}

onBeforeUnmount(() => {
  stopDrag();
});
</script>

<template>
  <div class="segmentation-overlay" aria-label="Segmentation overlay">
    <div ref="trackRef" class="segmentation-track">
      <div
        v-for="(segment, spanIndex) in overlayModel.spans"
        :key="segment.id"
        class="segment-span"
        :class="[
          `segment-span-${segment.label}`,
          { 'segment-span-active': segment.id === selectedSegmentId },
        ]"
        :style="{
          left: segment.left,
          width: segment.width,
          opacity: Math.max(0.35, 1 - (props.segmentUncertainty[spanIndex] ?? 0)),
        }"
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
        :class="{ 'segment-boundary-dragging': draggingBoundaryIndex === boundary.boundaryIndex }"
        :style="{ left: boundary.left }"
      >
        <button
          class="segment-boundary-handle"
          type="button"
          :aria-label="`Drag boundary ${boundary.boundaryIndex + 1}`"
          @pointerdown.prevent="startDrag(boundary.boundaryIndex, $event)"
        />
        <div
          v-if="props.boundaryUncertainty[boundary.boundaryIndex] != null"
          class="segment-boundary-uncertainty"
          :style="{
            width: `${Math.round((props.boundaryUncertainty[boundary.boundaryIndex] ?? 0) * 8)}px`,
          }"
          aria-hidden="true"
        />
      </div>
    </div>

    <div class="segment-legend">
      <div v-for="style in SEGMENT_LABEL_STYLES" :key="style.label" class="segment-legend-item">
        <span class="segment-legend-swatch" :class="`segment-span-${style.label}`" />
        <span>{{ style.label }}</span>
      </div>
    </div>
  </div>
</template>
