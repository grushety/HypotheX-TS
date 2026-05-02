<script setup>
import { computed, onBeforeUnmount, ref } from "vue";

import { createSegmentationOverlayModel } from "../../lib/segments/createSegmentationOverlayModel";
import { getBoundaryStartFromClientX } from "../../lib/segments/getBoundaryStartFromClientX";
import ShapeChip from "./ShapeChip.vue";
import ShapeLegend from "./ShapeLegend.vue";

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
      <ShapeChip
        v-for="(segment, spanIndex) in overlayModel.spans"
        :key="segment.id"
        :segment-id="segment.id"
        :shape="segment.shape || segment.label"
        :confidence="segment.confidence ?? null"
        :method="segment.method ?? null"
        :semantic-label="segment.semanticLabel ?? null"
        :is-cloud-gap="segment.semanticLabel === 'cloud_gap' || segment.semantic_label === 'cloud_gap'"
        :is-filled="!!(segment.metadata && segment.metadata.filled) || !!segment.filled"
        :fill-strategy="(segment.metadata && (segment.metadata.fill_strategy || segment.metadata.fillStrategy)) || segment.fillStrategy || null"
        :missingness-pct="Math.round(((segment.missingness_ratio ?? segment.missingnessRatio ?? 0)) * 100)"
        :selected="segment.id === selectedSegmentId"
        :style="{
          position: 'absolute',
          top: '12px',
          bottom: '12px',
          left: segment.left,
          width: segment.width,
          opacity: Math.max(0.35, 1 - (props.segmentUncertainty[spanIndex] ?? 0)),
        }"
        @segment-selected="emit('select-segment', $event)"
      />

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

    <ShapeLegend />
  </div>
</template>
