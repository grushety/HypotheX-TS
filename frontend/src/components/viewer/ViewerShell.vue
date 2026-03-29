<script setup>
import ModelComparisonPanel from "../comparison/ModelComparisonPanel.vue";
import HistoryPanel from "../history/HistoryPanel.vue";
import OperationPalette from "../operations/OperationPalette.vue";
import WarningPanel from "../warnings/WarningPanel.vue";
import TimelineViewer from "./TimelineViewer.vue";
import { AVAILABLE_SEGMENT_LABELS } from "../../lib/segments/updateSegmentLabel";

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
  operationFeedback: {
    type: String,
    default: "",
  },
  selectedSegment: {
    type: Object,
    default: null,
  },
  warningDisplay: {
    type: Object,
    default: null,
  },
  historyEntries: {
    type: Array,
    default: () => [],
  },
  operationPaletteState: {
    type: Object,
    default: () => ({}),
  },
  comparisonState: {
    type: Object,
    default: () => ({
      rows: [],
      message: "",
      heading: "Model comparison",
      artifactLabel: "No model selected",
    }),
  },
});

const emit = defineEmits([
  "select-segment",
  "move-boundary",
  "update-segment-label",
  "run-operation",
  "export-log",
]);
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

    <WarningPanel :warning="warningDisplay" />

    <div class="viewer-grid">
      <section class="surface chart-surface" aria-label="Chart area placeholder">
        <div class="surface-header">
          <div>
            <p class="section-label">Chart area</p>
            <h3>Time-series timeline</h3>
          </div>
          <span class="surface-tag">{{ sample?.seriesLength ?? "--" }} points</span>
        </div>

        <TimelineViewer
          :sample="sample"
          :selected-segment-id="selectedSegmentId"
          @select-segment="emit('select-segment', $event)"
          @move-boundary="emit('move-boundary', $event)"
        />

        <p v-if="editFeedback" class="drag-feedback">{{ editFeedback }}</p>
        <p class="surface-copy">
          The timeline keeps segment spans, boundaries, and current selection aligned on one surface.
        </p>
      </section>

      <section class="surface overlay-surface" aria-label="Overlay area placeholder">
        <div class="surface-header">
          <div>
            <p class="section-label">Segment index</p>
            <h3>Overlay map</h3>
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
          Use the list for precise segment selection while the timeline keeps global context visible.
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

        <div v-if="selectedSegment" class="label-editor">
          <label class="label-editor-field">
            <span class="sidebar-label">Segment label</span>
            <select
              class="label-editor-select"
              :value="selectedSegment.label"
              @change="emit('update-segment-label', $event.target.value)"
            >
              <option v-for="label in AVAILABLE_SEGMENT_LABELS" :key="label" :value="label">
                {{ label }}
              </option>
            </select>
          </label>
        </div>

        <OperationPalette
          :state="operationPaletteState"
          @run-operation="emit('run-operation', $event)"
        />

        <ul class="sidebar-list">
          <li v-for="item in sidebarItems" :key="item.label" class="sidebar-item">
            <span class="sidebar-label">{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </li>
        </ul>
      </aside>

      <ModelComparisonPanel :state="comparisonState" />

      <HistoryPanel :entries="historyEntries" @export-log="emit('export-log')" />
    </div>
  </section>
</template>
