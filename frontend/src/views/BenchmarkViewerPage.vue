<script setup>
import { computed, onMounted, ref, watch } from "vue";

import BenchmarkSelectorPanel from "../components/benchmarks/BenchmarkSelectorPanel.vue";
import ViewerShell from "../components/viewer/ViewerShell.vue";
import { appendAuditEvent, createEditAuditEvent, createOperationAuditEvent } from "../lib/audit/auditEvents";
import { createHistoryEntries } from "../lib/audit/createHistoryEntries";
import { createViewerSampleFromApi } from "../lib/benchmarks/createViewerSampleFromApi";
import { createBenchmarkSelectorState } from "../lib/benchmarks/createBenchmarkSelectorState";
import { reconcileBenchmarkSelection } from "../lib/benchmarks/reconcileBenchmarkSelection";
import { SOFT_CONSTRAINT_STATUS } from "../lib/constraints/evaluateSoftConstraints";
import {
  createInteractionLogExport,
  downloadInteractionLogExport,
} from "../lib/export/createInteractionLogExport";
import { executeOperationAction } from "../lib/operations/executeOperationAction";
import {
  executeMoveBoundaryAction,
  executeUpdateSegmentLabelAction,
} from "../lib/segments/executeSegmentEditAction";
import { createViewerWarningDisplay } from "../lib/viewer/createViewerWarningDisplay";
import { createViewerPageState } from "../lib/viewer/createViewerPageState";
import { getSelectedSegment, reconcileSelectedSegmentId } from "../lib/viewer/reconcileSelectedSegmentId";
import {
  fetchBenchmarkCompatibility,
  fetchBenchmarkDatasets,
  fetchBenchmarkModels,
  fetchBenchmarkSample,
} from "../services/api/benchmarkApi";

const sample = ref(null);
const loading = ref(true);
const error = ref("");
const benchmarkDatasets = ref([]);
const benchmarkArtifacts = ref([]);
const selectorLoading = ref(true);
const selectorError = ref("");
const compatibilityLoading = ref(false);
const compatibilityError = ref("");
const compatibilityResult = ref(null);
const selectedDatasetName = ref("");
const selectedArtifactId = ref("");
const selectedSplit = ref("train");
const selectedSampleIndex = ref(0);
const selectedSegmentId = ref(null);
const editFeedback = ref("");
const operationFeedback = ref("");
const editConstraintResult = ref(null);
const operationConstraintResult = ref(null);
const auditEvents = ref([]);
let compatibilityRequestId = 0;

const selectedSegment = computed(() =>
  getSelectedSegment(sample.value?.segments ?? [], selectedSegmentId.value),
);
const pageState = computed(() => createViewerPageState(sample.value, selectedSegment.value));
const historyEntries = computed(() => createHistoryEntries(auditEvents.value));
const warningDisplay = computed(() =>
  createViewerWarningDisplay({
    editConstraintResult: editConstraintResult.value,
    editFeedback: editFeedback.value,
    operationConstraintResult: operationConstraintResult.value,
    operationFeedback: operationFeedback.value,
  }),
);
const selectorState = computed(() =>
  createBenchmarkSelectorState({
    datasets: benchmarkDatasets.value,
    artifacts: benchmarkArtifacts.value,
    selectedDatasetName: selectedDatasetName.value,
    selectedArtifactId: selectedArtifactId.value,
    selectedSplit: selectedSplit.value,
    sampleIndex: selectedSampleIndex.value,
    loading: selectorLoading.value,
    error: selectorError.value,
    compatibility: compatibilityResult.value,
    compatibilityLoading: compatibilityLoading.value,
    compatibilityError: compatibilityError.value,
  }),
);

async function loadSample() {
  loading.value = true;
  error.value = "";

  try {
    const payload = await fetchBenchmarkSample(
      selectedDatasetName.value,
      selectedSplit.value,
      selectedSampleIndex.value,
    );
    sample.value = createViewerSampleFromApi(payload);
    editFeedback.value = "";
    operationFeedback.value = "";
    editConstraintResult.value = null;
    operationConstraintResult.value = null;
    auditEvents.value = [];
  } catch (loadError) {
    sample.value = null;
    error.value =
      loadError instanceof Error ? loadError.message : "Failed to load benchmark sample.";
  } finally {
    loading.value = false;
  }
}

function applySelection(nextSelection) {
  selectedDatasetName.value = nextSelection.selectedDatasetName;
  selectedArtifactId.value = nextSelection.selectedArtifactId;
  selectedSplit.value = nextSelection.selectedSplit;
  selectedSampleIndex.value = nextSelection.sampleIndex;
}

function reconcileSelectionState() {
  applySelection(
    reconcileBenchmarkSelection({
      datasets: benchmarkDatasets.value,
      artifacts: benchmarkArtifacts.value,
      selectedDatasetName: selectedDatasetName.value,
      selectedArtifactId: selectedArtifactId.value,
      selectedSplit: selectedSplit.value,
      sampleIndex: selectedSampleIndex.value,
    }),
  );
}

async function loadBenchmarkOptions() {
  selectorLoading.value = true;
  selectorError.value = "";

  try {
    const [datasets, modelPayload] = await Promise.all([
      fetchBenchmarkDatasets(),
      fetchBenchmarkModels(),
    ]);
    benchmarkDatasets.value = datasets;
    benchmarkArtifacts.value = modelPayload.artifacts;
    reconcileSelectionState();
  } catch (loadError) {
    benchmarkDatasets.value = [];
    benchmarkArtifacts.value = [];
    sample.value = null;
    loading.value = false;
    selectorError.value =
      loadError instanceof Error ? loadError.message : "Failed to load benchmark options.";
  } finally {
    selectorLoading.value = false;
  }
}

async function refreshCompatibility() {
  if (!selectedDatasetName.value || !selectedArtifactId.value || selectorError.value) {
    compatibilityResult.value = null;
    compatibilityError.value = "";
    compatibilityLoading.value = false;
    return;
  }

  const requestId = compatibilityRequestId + 1;
  compatibilityRequestId = requestId;
  compatibilityLoading.value = true;
  compatibilityError.value = "";

  try {
    const result = await fetchBenchmarkCompatibility(selectedDatasetName.value, selectedArtifactId.value);
    if (compatibilityRequestId !== requestId) {
      return;
    }
    compatibilityResult.value = result;
  } catch (requestError) {
    if (compatibilityRequestId !== requestId) {
      return;
    }
    compatibilityResult.value = null;
    compatibilityError.value =
      requestError instanceof Error ? requestError.message : "Failed to validate benchmark selection.";
  } finally {
    if (compatibilityRequestId === requestId) {
      compatibilityLoading.value = false;
    }
  }
}

function handleUpdateDataset(datasetName) {
  selectedDatasetName.value = datasetName;
  reconcileSelectionState();
}

function handleUpdateArtifact(artifactId) {
  selectedArtifactId.value = artifactId;
  reconcileSelectionState();
}

function handleUpdateSplit(split) {
  selectedSplit.value = split;
  reconcileSelectionState();
}

function handleUpdateSampleIndex(nextValue) {
  const parsedValue = Number.parseInt(nextValue, 10);
  selectedSampleIndex.value = Number.isNaN(parsedValue) ? 0 : parsedValue;
  reconcileSelectionState();
}

function handleSelectSegment(segmentId) {
  selectedSegmentId.value = segmentId;
  operationFeedback.value = "";
}

function handleMoveBoundary({ boundaryIndex, nextBoundaryStart }) {
  const request = {
    type: "move-boundary",
    boundaryIndex,
    nextBoundaryStart,
  };
  const result = executeMoveBoundaryAction(sample.value, {
    boundaryIndex,
    nextBoundaryStart,
  });

  auditEvents.value = appendAuditEvent(
    auditEvents.value,
    createEditAuditEvent(request, result, {
      sampleId: sample.value?.sampleId ?? null,
      selectedSegmentId: selectedSegmentId.value,
    }),
  );

  if (!result.ok) {
    editFeedback.value = result.message;
    editConstraintResult.value = null;
    operationConstraintResult.value = null;
    return;
  }

  sample.value = result.sample;
  editConstraintResult.value = result.constraintResult;
  editFeedback.value =
    result.constraintStatus === SOFT_CONSTRAINT_STATUS.WARN ? result.message : "";
  operationFeedback.value = "";
  operationConstraintResult.value = null;
}

function handleUpdateSegmentLabel(nextLabel) {
  const request = {
    type: "update-label",
    segmentId: selectedSegmentId.value,
    nextLabel,
  };
  const result = executeUpdateSegmentLabelAction(sample.value, selectedSegmentId.value, nextLabel);

  auditEvents.value = appendAuditEvent(
    auditEvents.value,
    createEditAuditEvent(request, result, {
      sampleId: sample.value?.sampleId ?? null,
      selectedSegmentId: selectedSegmentId.value,
    }),
  );

  if (!result.ok) {
    editFeedback.value = result.message;
    editConstraintResult.value = null;
    operationConstraintResult.value = null;
    return;
  }

  sample.value = result.sample;
  editConstraintResult.value = result.constraintResult;
  editFeedback.value =
    result.constraintStatus === SOFT_CONSTRAINT_STATUS.WARN ? result.message : "";
  operationFeedback.value = "";
  operationConstraintResult.value = null;
}

function handleRunOperation(request) {
  const result = executeOperationAction(sample.value, selectedSegmentId.value, request);

  auditEvents.value = appendAuditEvent(
    auditEvents.value,
    createOperationAuditEvent(request, result, {
      sampleId: sample.value?.sampleId ?? null,
      selectedSegmentId: selectedSegmentId.value,
    }),
  );

  if (!result.ok) {
    operationFeedback.value = result.message;
    operationConstraintResult.value = null;
    editConstraintResult.value = null;
    return;
  }

  sample.value = result.sample;
  selectedSegmentId.value = result.selectedSegmentId;
  operationFeedback.value = result.message;
  operationConstraintResult.value = result.constraintResult;
  editFeedback.value = "";
  editConstraintResult.value = null;
}

function handleExportLog() {
  if (!auditEvents.value.length) {
    return;
  }

  const exportArtifact = createInteractionLogExport(auditEvents.value, {
    sampleId: sample.value?.sampleId ?? null,
    datasetName: sample.value?.datasetName ?? null,
  });

  downloadInteractionLogExport(exportArtifact);
}

watch(
  () => sample.value?.segments,
  (segments) => {
    selectedSegmentId.value = reconcileSelectedSegmentId(segments ?? [], selectedSegmentId.value);
  },
  { immediate: true },
);

watch(
  [selectedDatasetName, selectedArtifactId],
  () => {
    refreshCompatibility();
  },
  { immediate: true },
);

watch(
  [selectedDatasetName, selectedSplit, selectedSampleIndex],
  ([datasetName]) => {
    if (!datasetName || selectorError.value) {
      return;
    }
    loadSample();
  },
  { immediate: false },
);

onMounted(() => {
  loadBenchmarkOptions();
});
</script>

<template>
  <main class="app-shell">
    <section class="hero">
      <div>
        <p class="eyebrow">HTS-022 MVP</p>
        <h1>Benchmark viewer workflow</h1>
        <p class="hero-copy">
          The MVP viewer supports segment editing, semantic operations, soft warnings, interaction
          history, and JSON log export on top of the benchmark sample workflow.
        </p>
      </div>

      <button class="ghost-button" type="button" @click="loadSample" :disabled="!selectedDatasetName">
        Reload selected sample
      </button>
    </section>

    <p v-if="error" class="banner-error">{{ error }}</p>

    <BenchmarkSelectorPanel
      :state="selectorState"
      @reload="loadBenchmarkOptions"
      @update-dataset="handleUpdateDataset"
      @update-artifact="handleUpdateArtifact"
      @update-split="handleUpdateSplit"
      @update-sample-index="handleUpdateSampleIndex"
    />

    <ViewerShell
      :sample="sample"
      :loading="loading"
      :status-items="pageState.statusItems"
      :sidebar-items="pageState.sidebarItems"
      :selected-segment-id="selectedSegmentId"
      :selected-segment="selectedSegment"
      :edit-feedback="editFeedback"
      :operation-feedback="operationFeedback"
      :warning-display="warningDisplay"
      :history-entries="historyEntries"
      @select-segment="handleSelectSegment"
      @move-boundary="handleMoveBoundary"
      @update-segment-label="handleUpdateSegmentLabel"
      @run-operation="handleRunOperation"
      @export-log="handleExportLog"
    />
  </main>
</template>
