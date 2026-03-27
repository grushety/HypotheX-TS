<script setup>
import { computed, onMounted, ref, watch } from "vue";

import ViewerShell from "../components/viewer/ViewerShell.vue";
import { loadBenchmarkSample } from "../lib/data/benchmarkSamples";
import { moveSegmentBoundary } from "../lib/segments/moveSegmentBoundary";
import { createViewerPageState } from "../lib/viewer/createViewerPageState";
import { getSelectedSegment, reconcileSelectedSegmentId } from "../lib/viewer/reconcileSelectedSegmentId";

const sample = ref(null);
const loading = ref(true);
const error = ref("");
const selectedSegmentId = ref(null);
const editFeedback = ref("");

const selectedSegment = computed(() =>
  getSelectedSegment(sample.value?.segments ?? [], selectedSegmentId.value),
);
const pageState = computed(() => createViewerPageState(sample.value, selectedSegment.value));

async function loadSample() {
  loading.value = true;
  error.value = "";

  try {
    sample.value = await loadBenchmarkSample();
    editFeedback.value = "";
  } catch (loadError) {
    sample.value = null;
    error.value =
      loadError instanceof Error ? loadError.message : "Failed to load benchmark sample.";
  } finally {
    loading.value = false;
  }
}

function handleSelectSegment(segmentId) {
  selectedSegmentId.value = segmentId;
}

function handleMoveBoundary({ boundaryIndex, nextBoundaryStart }) {
  if (!sample.value?.segments?.length) {
    return;
  }

  const result = moveSegmentBoundary(sample.value.segments, boundaryIndex, nextBoundaryStart);

  if (!result.ok) {
    editFeedback.value = result.message;
    return;
  }

  sample.value = {
    ...sample.value,
    segments: result.segments,
  };
  editFeedback.value = "";
}

watch(
  () => sample.value?.segments,
  (segments) => {
    selectedSegmentId.value = reconcileSelectedSegmentId(segments ?? [], selectedSegmentId.value);
  },
  { immediate: true },
);

onMounted(() => {
  loadSample();
});
</script>

<template>
  <main class="app-shell">
    <section class="hero">
      <div>
        <p class="eyebrow">HTS-006</p>
        <h1>Benchmark viewer boundary drag</h1>
        <p class="hero-copy">
          The viewer now connects draggable shared boundaries to the pure boundary-edit logic so
          valid edits update immediately and invalid moves surface clean feedback.
        </p>
      </div>

      <button class="ghost-button" type="button" @click="loadSample">
        Reload sample
      </button>
    </section>

    <p v-if="error" class="banner-error">{{ error }}</p>

    <ViewerShell
      :sample="sample"
      :loading="loading"
      :status-items="pageState.statusItems"
      :sidebar-items="pageState.sidebarItems"
      :selected-segment-id="selectedSegmentId"
      :edit-feedback="editFeedback"
      @select-segment="handleSelectSegment"
      @move-boundary="handleMoveBoundary"
    />
  </main>
</template>
