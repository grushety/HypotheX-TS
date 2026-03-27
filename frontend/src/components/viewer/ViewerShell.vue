<script setup>
import SegmentationOverlay from "./SegmentationOverlay.vue";
import TimeSeriesChart from "./TimeSeriesChart.vue";

defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  sample: {
    type: Object,
    default: null,
  },
  statusItems: {
    type: Array,
    default: () => [],
  },
  sidebarItems: {
    type: Array,
    default: () => [],
  },
  selectedSegmentId: {
    type: String,
    default: null,
  },
  editFeedback: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["select-segment", "move-boundary"]);
</script>

<template>
  <section class="viewer-shell" aria-label="Benchmark viewer shell">
    <header class="viewer-header">
      <div>
        <p class="section-label">Dataset sample</p>
        <h2>{{ sample?.datasetName ?? "Loading benchmark sample" }}</h2>
      </div>

      <p class="viewer-meta">
        {{ loading ? "Preparing viewer state..." : `Sample ${sample?.sampleId ?? "not loaded"}` }}
      </p>
    </header>

    <div class="status-strip" aria-label="Viewer status">
      <article v-for="item in statusItems" :key="item.label" class="status-pill">
        <span class="status-pill-label">{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <div class="viewer-grid">
      <section class="surface chart-surface" aria-label="Chart area placeholder">
        <div class="surface-header">
          <div>
            <p class="section-label">Chart area</p>
            <h3>Time-series plot</h3>
          </div>
          <span class="surface-tag">{{ sample?.seriesLength ?? "--" }} points</span>
        </div>

        <div v-if="sample?.values?.length" class="chart-stack">
          <TimeSeriesChart :values="sample.values" :title="`${sample.datasetName} sample ${sample.sampleId}`" />
          <SegmentationOverlay
            v-if="sample?.segments?.length"
            :segments="sample.segments"
            :series-length="sample.seriesLength"
            :selected-segment-id="selectedSegmentId"
            @select-segment="emit('select-segment', $event)"
            @move-boundary="emit('move-boundary', $event)"
          />
        </div>
        <div v-else class="chart-empty-state">Preparing chart data...</div>

        <p v-if="editFeedback" class="drag-feedback">{{ editFeedback }}</p>
        <p class="surface-copy">
          Drag a boundary handle to update adjacent segments through the shared boundary logic.
        </p>
      </section>

      <section class="surface overlay-surface" aria-label="Overlay area placeholder">
        <div class="surface-header">
          <div>
            <p class="section-label">Overlay area</p>
            <h3>Segment map</h3>
          </div>
          <span class="surface-tag">{{ sample?.segments?.length ?? 0 }} segments</span>
        </div>

        <ul v-if="sample?.segments?.length" class="overlay-segment-list">
          <li
            v-for="segment in sample.segments"
            :key="segment.id"
            class="overlay-segment-item"
            :class="{ 'overlay-segment-item-active': segment.id === selectedSegmentId }"
          >
            <span class="segment-chip" :class="`segment-chip-${segment.label}`">{{ segment.label }}</span>
            <button class="segment-select-button" type="button" @click="emit('select-segment', segment.id)">
              {{ segment.start }}-{{ segment.end }}
            </button>
          </li>
        </ul>
        <div v-else class="overlay-placeholder">Preparing segments...</div>

        <p class="surface-copy">
          Segment spans and labels are now aligned to the loaded series and ready for selection work.
        </p>
      </section>

      <aside class="surface sidebar-surface" aria-label="Side panel placeholder">
        <div class="surface-header">
          <div>
            <p class="section-label">Side panel</p>
            <h3>Viewer context</h3>
          </div>
          <span class="surface-tag">{{ selectedSegmentId ? "Active segment" : "No selection" }}</span>
        </div>

        <ul class="sidebar-list">
          <li v-for="item in sidebarItems" :key="item.label" class="sidebar-item">
            <span class="sidebar-label">{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </li>
        </ul>
      </aside>
    </div>
  </section>
</template>
