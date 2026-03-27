<script setup>
import { onMounted, ref } from "vue";

const backendStatus = ref("Checking backend...");
const backendDetails = ref(null);
const backendError = ref("");

async function loadHealth() {
  backendStatus.value = "Checking backend...";
  backendError.value = "";

  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      throw new Error(`Health check failed with status ${response.status}`);
    }

    const payload = await response.json();
    backendDetails.value = payload;
    backendStatus.value = payload.status === "ok" ? "Backend reachable" : "Backend unavailable";
  } catch (error) {
    backendDetails.value = null;
    backendStatus.value = "Backend unreachable";
    backendError.value = error instanceof Error ? error.message : "Unknown error";
  }
}

onMounted(() => {
  loadHealth();
});
</script>

<template>
  <main class="shell">
    <section class="panel">
      <p class="eyebrow">HypotheX-TS</p>
      <h1>Project scaffold is running.</h1>
      <p class="lede">
        This page verifies the initial Vue to Flask connection required by HTS-000.
      </p>

      <div class="status-card">
        <p class="status-label">Backend health</p>
        <p class="status-value">{{ backendStatus }}</p>
        <button class="refresh-button" type="button" @click="loadHealth">
          Retry health check
        </button>
      </div>

      <pre v-if="backendDetails" class="payload">{{ JSON.stringify(backendDetails, null, 2) }}</pre>
      <p v-if="backendError" class="error">{{ backendError }}</p>
    </section>
  </main>
</template>
