<script setup>
import { computed, onMounted, ref } from "vue";

import ViewerShell from "../components/viewer/ViewerShell.vue";
import { loadBenchmarkSample } from "../lib/data/benchmarkSamples";
import { createViewerPageState } from "../lib/viewer/createViewerPageState";

const sample = ref(null);
const loading = ref(true);
const error = ref("");

const pageState = computed(() => createViewerPageState(sample.value));

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

onMounted(() => {
  loadSample();
});
</script>

<template>
  <main class="app-shell">
    <section class="hero">
      <div>
        <p class="eyebrow">HTS-003</p>
        <h1>Benchmark viewer overlay</h1>
        <p class="hero-copy">
          The viewer now layers semantic segments and labels on top of the chart while keeping the
          chart drawing and overlay rendering as separate components.
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
    />
  </main>
</template>
