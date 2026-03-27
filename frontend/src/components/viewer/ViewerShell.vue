<script setup>
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
});
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

        <TimeSeriesChart
          v-if="sample?.values?.length"
          :values="sample.values"
          :title="`${sample.datasetName} sample ${sample.sampleId}`"
        />
        <div v-else class="chart-empty-state">Preparing chart data...</div>

        <p class="surface-copy">
          This chart component is the base visualization layer for later overlay and editing work.
        </p>
      </section>

      <section class="surface overlay-surface" aria-label="Overlay area placeholder">
        <div class="surface-header">
          <div>
            <p class="section-label">Overlay area</p>
            <h3>Segmentation band placeholder</h3>
          </div>
          <span class="surface-tag">Future labels</span>
        </div>

        <div class="overlay-placeholder">
          <div class="segment-chip segment-chip-event">event</div>
          <div class="segment-chip segment-chip-trend">trend</div>
          <div class="segment-chip segment-chip-anomaly">anomaly</div>
          <div class="segment-chip segment-chip-other">other</div>
        </div>

        <p class="surface-copy">
          Ticket `HTS-003` will replace this scaffold with the rendered segmentation overlay.
        </p>
      </section>

      <aside class="surface sidebar-surface" aria-label="Side panel placeholder">
        <div class="surface-header">
          <div>
            <p class="section-label">Side panel</p>
            <h3>Viewer context</h3>
          </div>
          <span class="surface-tag">Read-only</span>
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
