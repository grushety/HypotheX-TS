<script setup>
import { computed } from "vue";

import { createTimelineViewerModel } from "../../lib/viewer/createTimelineViewerModel";
import SegmentationOverlay from "./SegmentationOverlay.vue";
import TimeSeriesChart from "./TimeSeriesChart.vue";
import SaliencyOverlay from "./SaliencyOverlay.vue";

const props = defineProps({
  sample: {
    type: Object,
    default: null,
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
  ghostValues: {
    type: Array,
    default: null,
  },
  saliencyAttribution: {
    type: Array,
    default: null,
  },
  saliencyMethod: {
    type: String,
    default: "",
  },
  saliencyReference: {
    type: String,
    default: "",
  },
  saliencyLoading: {
    type: Boolean,
    default: false,
  },
  saliencyError: {
    type: String,
    default: null,
  },
  showAtoms: {
    type: Boolean,
    default: true,
  },
});

const emit = defineEmits(["select-segment", "move-boundary"]);

const timelineModel = computed(() =>
  createTimelineViewerModel(props.sample, props.selectedSegmentId),
);
</script>

<template>
  <section class="timeline-viewer" aria-label="Timeline viewer">
    <div class="timeline-header">
      <div>
        <p class="section-label">Timeline viewer</p>
        <h3>{{ timelineModel.title }}</h3>
      </div>
      <div class="timeline-summary">
        <span class="surface-tag">{{ timelineModel.pointCountLabel }}</span>
        <span class="surface-tag">{{ timelineModel.segmentCountLabel }}</span>
      </div>
    </div>

    <div v-if="sample?.values?.length" class="timeline-stage">
      <TimeSeriesChart
        :values="sample.values"
        :ghost-values="ghostValues"
        :title="timelineModel.title"
      />
      <SegmentationOverlay
        v-if="sample?.segments?.length"
        :segments="sample.segments"
        :series-length="sample.seriesLength"
        :selected-segment-id="selectedSegmentId"
        :segment-uncertainty="props.segmentUncertainty"
        :boundary-uncertainty="props.boundaryUncertainty"
        :show-atoms="showAtoms"
        @select-segment="emit('select-segment', $event)"
        @move-boundary="emit('move-boundary', $event)"
      />
      <SaliencyOverlay
        v-if="saliencyAttribution || saliencyLoading || saliencyError"
        :attribution="saliencyAttribution"
        :method="saliencyMethod"
        :reference="saliencyReference"
        :loading="saliencyLoading"
        :error="saliencyError"
      />
    </div>
    <div v-else class="chart-empty-state">Preparing chart data...</div>

    <div class="timeline-footer">
      <div class="timeline-focus-card">
        <span class="sidebar-label">Selection</span>
        <strong>{{ timelineModel.selectedSummary }}</strong>
        <p class="timeline-focus-copy">Range {{ timelineModel.selectedRangeLabel }}</p>
      </div>

      <div class="timeline-focus-card">
        <span class="sidebar-label">Overview</span>
        <strong>{{ timelineModel.overviewLabel }}</strong>
        <div class="timeline-minimap" aria-label="Timeline overview minimap">
          <div
            v-for="segment in timelineModel.minimapSpans"
            :key="segment.id"
            class="timeline-minimap-span"
            :class="[
              `segment-span-${segment.label}`,
              { 'timeline-minimap-span-active': segment.isSelected },
            ]"
            :style="{ left: segment.left, width: segment.width }"
            :title="`${segment.label} ${segment.rangeLabel}`"
          />
          <div
            v-if="sample?.segments?.length"
            class="timeline-minimap-window"
            :style="{
              left: timelineModel.overviewWindow.left,
              width: timelineModel.overviewWindow.width,
            }"
          />
        </div>
      </div>
    </div>
  </section>
</template>
