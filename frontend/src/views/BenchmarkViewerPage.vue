<script setup>
import { computed, onMounted, ref, watch } from "vue";

import ViewerShell from "../components/viewer/ViewerShell.vue";
import { loadBenchmarkSample } from "../lib/data/benchmarkSamples";
import { executeOperationAction } from "../lib/operations/executeOperationAction";
import { moveSegmentBoundary } from "../lib/segments/moveSegmentBoundary";
import { updateSegmentLabel } from "../lib/segments/updateSegmentLabel";
import { createViewerPageState } from "../lib/viewer/createViewerPageState";
import { getSelectedSegment, reconcileSelectedSegmentId } from "../lib/viewer/reconcileSelectedSegmentId";

const sample = ref(null);
const loading = ref(true);
const error = ref("");
const selectedSegmentId = ref(null);
const editFeedback = ref("");
const operationFeedback = ref("");

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
    operationFeedback.value = "";
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
  operationFeedback.value = "";
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
  operationFeedback.value = "";
}

function handleUpdateSegmentLabel(nextLabel) {
  if (!sample.value?.segments?.length || !selectedSegmentId.value) {
    return;
  }

  const result = updateSegmentLabel(sample.value.segments, selectedSegmentId.value, nextLabel);

  if (!result.ok) {
    editFeedback.value = result.message;
    return;
  }

  sample.value = {
    ...sample.value,
    segments: result.segments,
  };
  editFeedback.value = "";
  operationFeedback.value = "";
}

function handleRunOperation(request) {
  const result = executeOperationAction(sample.value, selectedSegmentId.value, request);

  if (!result.ok) {
    operationFeedback.value = result.message;
    return;
  }

  sample.value = result.sample;
  selectedSegmentId.value = result.selectedSegmentId;
  operationFeedback.value = result.message;
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
        <p class="eyebrow">HTS-013</p>
        <h1>Benchmark viewer operations</h1>
        <p class="hero-copy">
          The viewer now exposes split, merge, and reclassify as explicit semantic operations while
          keeping the UI layer thin and delegating state changes to the domain contracts.
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
      :selected-segment="selectedSegment"
      :edit-feedback="editFeedback"
      :operation-feedback="operationFeedback"
      @select-segment="handleSelectSegment"
      @move-boundary="handleMoveBoundary"
      @update-segment-label="handleUpdateSegmentLabel"
      @run-operation="handleRunOperation"
    />
  </main>
</template>
