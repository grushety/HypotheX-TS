<script setup>
import { computed, onMounted, ref, watch } from "vue";

import ViewerShell from "../components/viewer/ViewerShell.vue";
import { loadBenchmarkSample } from "../lib/data/benchmarkSamples";
import { createViewerPageState } from "../lib/viewer/createViewerPageState";
import { getSelectedSegment, reconcileSelectedSegmentId } from "../lib/viewer/reconcileSelectedSegmentId";

const sample = ref(null);
const loading = ref(true);
const error = ref("");
const selectedSegmentId = ref(null);

const selectedSegment = computed(() =>
  getSelectedSegment(sample.value?.segments ?? [], selectedSegmentId.value),
);
const pageState = computed(() => createViewerPageState(sample.value, selectedSegment.value));

async function loadSample() {
  loading.value = true;
  error.value = "";

  try {
    sample.value = await loadBenchmarkSample();
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
        <p class="eyebrow">HTS-004</p>
        <h1>Benchmark viewer selection</h1>
        <p class="hero-copy">
          The viewer now keeps one explicit active segment in state so highlighting and side-panel
          metadata stay synchronized across rerenders.
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
      @select-segment="handleSelectSegment"
    />
  </main>
</template>
