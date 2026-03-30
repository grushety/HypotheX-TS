<script setup>
import { computed, onMounted, ref, watch } from "vue";

import BenchmarkSelectorPanel from "../components/benchmarks/BenchmarkSelectorPanel.vue";
import PredictionPanel from "../components/benchmarks/PredictionPanel.vue";
import ViewerShell from "../components/viewer/ViewerShell.vue";
import {
  appendAuditEvent,
  createEditAuditEvent,
  createOperationAuditEvent,
  createSuggestionAuditEvent,
} from "../lib/audit/auditEvents";
import { createHistoryEntries } from "../lib/audit/createHistoryEntries";
import { createSessionPanelState } from "../lib/audit/createSessionPanelState";
import { createPredictionPanelState } from "../lib/benchmarks/createPredictionPanelState";
import { createViewerSampleFromApi } from "../lib/benchmarks/createViewerSampleFromApi";
import { createBenchmarkSelectorState } from "../lib/benchmarks/createBenchmarkSelectorState";
import { reconcileBenchmarkSelection } from "../lib/benchmarks/reconcileBenchmarkSelection";
import { SOFT_CONSTRAINT_STATUS } from "../lib/constraints/evaluateSoftConstraints";
import {
  createInteractionLogExport,
  downloadInteractionLogExport,
} from "../lib/export/createInteractionLogExport";
import { createOperationPaletteState } from "../lib/operations/createOperationPaletteState";
import { executeOperationAction } from "../lib/operations/executeOperationAction";
import {
  executeMoveBoundaryAction,
  executeUpdateSegmentLabelAction,
} from "../lib/segments/executeSegmentEditAction";
import { createModelComparisonState } from "../lib/viewer/createModelComparisonState";
import { createProposalSegments } from "../lib/viewer/createProposalSegments";
import { createViewerWarningDisplay } from "../lib/viewer/createViewerWarningDisplay";
import { createViewerPageState } from "../lib/viewer/createViewerPageState";
import { getSelectedSegment, reconcileSelectedSegmentId } from "../lib/viewer/reconcileSelectedSegmentId";
import {
  fetchBenchmarkCompatibility,
  fetchBenchmarkDatasets,
  fetchBenchmarkModels,
  fetchBenchmarkOperationRegistry,
  fetchBenchmarkPrediction,
  fetchBenchmarkSample,
  fetchBenchmarkSuggestion,
  submitSuggestionDecision,
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
const predictionLoading = ref(false);
const predictionError = ref("");
const predictionResult = ref(null);
const operationRegistry = ref(null);
const proposalSegments = ref([]);
const suggestionPayload = ref(null);
const suggestionLoading = ref(false);
const suggestionError = ref("");
const suggestionStatus = ref("idle");
let compatibilityRequestId = 0;

const selectedSegment = computed(() =>
  getSelectedSegment(sample.value?.segments ?? [], selectedSegmentId.value),
);
const pageState = computed(() => createViewerPageState(sample.value, selectedSegment.value));
const historyEntries = computed(() => createHistoryEntries(auditEvents.value));
const sessionPanelState = computed(() => createSessionPanelState(auditEvents.value, sample.value));
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
const predictionPanelState = computed(() =>
  createPredictionPanelState({
    prediction: predictionResult.value,
    loading: predictionLoading.value,
    error: predictionError.value,
    sample: sample.value,
    selectedArtifact: selectorState.value.selectedArtifact,
    compatibility: compatibilityResult.value,
    compatibilityLoading: compatibilityLoading.value,
    selectorError: selectorError.value,
  }),
);
const operationPaletteState = computed(() =>
  createOperationPaletteState({
    segments: sample.value?.segments ?? [],
    selectedSegment: selectedSegment.value,
    operationRegistry: operationRegistry.value,
    feedback: operationFeedback.value,
  }),
);
const comparisonState = computed(() =>
  createModelComparisonState({
    currentSegments: sample.value?.segments ?? [],
    proposalSegments: proposalSegments.value,
    selectedArtifact: selectorState.value.selectedArtifact ?? null,
    suggestionStatus: suggestionStatus.value,
    suggestionLoading: suggestionLoading.value,
    suggestionError: suggestionError.value,
  }),
);

function clearPredictionState() {
  predictionLoading.value = false;
  predictionError.value = "";
  predictionResult.value = null;
}

function clearSuggestionState() {
  suggestionPayload.value = null;
  suggestionLoading.value = false;
  suggestionError.value = "";
  suggestionStatus.value = "idle";
  proposalSegments.value = [];
}

async function loadSample() {
  loading.value = true;
  error.value = "";
  clearPredictionState();

  try {
    const payload = await fetchBenchmarkSample(
      selectedDatasetName.value,
      selectedSplit.value,
      selectedSampleIndex.value,
    );
    sample.value = createViewerSampleFromApi(payload);
    clearSuggestionState();
    editFeedback.value = "";
    operationFeedback.value = "";
    editConstraintResult.value = null;
    operationConstraintResult.value = null;
    auditEvents.value = [];
  } catch (loadError) {
    sample.value = null;
    clearSuggestionState();
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
    const [datasets, modelPayload, operationCatalog] = await Promise.all([
      fetchBenchmarkDatasets(),
      fetchBenchmarkModels(),
      fetchBenchmarkOperationRegistry(),
    ]);
    benchmarkDatasets.value = datasets;
    benchmarkArtifacts.value = modelPayload.artifacts;
    operationRegistry.value = operationCatalog;
    reconcileSelectionState();
  } catch (loadError) {
    benchmarkDatasets.value = [];
    benchmarkArtifacts.value = [];
    operationRegistry.value = null;
    sample.value = null;
    clearSuggestionState();
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

function createSuggestionDecisionPayload(decision, reason) {
  return {
    seriesId: sessionPanelState.value.seriesId,
    segmentationId: sessionPanelState.value.segmentationId,
    suggestionId: suggestionPayload.value?.suggestionId ?? null,
    decision,
    targetSegmentIds: proposalSegments.value.map((segment) => segment.id),
    timestamp: new Date().toISOString(),
    metadata: {
      reason,
      artifactId: selectorState.value.selectedArtifact?.artifact_id ?? null,
      datasetName: sample.value?.datasetName ?? null,
    },
  };
}

async function persistSuggestionDecision(decision, reason) {
  const payload = createSuggestionDecisionPayload(decision, reason);
  if (!payload.suggestionId) {
    return;
  }

  try {
    await submitSuggestionDecision(sessionPanelState.value.sessionId, payload);
  } catch (requestError) {
    operationFeedback.value =
      requestError instanceof Error ? requestError.message : "Failed to persist suggestion decision.";
  }
}

async function markSuggestionDecision(decision, reason) {
  if (!suggestionPayload.value || suggestionStatus.value !== "pending") {
    return;
  }

  const payload = createSuggestionDecisionPayload(decision, reason);
  auditEvents.value = appendAuditEvent(
    auditEvents.value,
    createSuggestionAuditEvent(decision, suggestionPayload.value, {
      sampleId: sample.value?.sampleId ?? null,
      selectedSegmentId: selectedSegmentId.value,
      targetSegmentIds: payload.targetSegmentIds,
    }),
  );
  suggestionStatus.value = decision;
  await persistSuggestionDecision(decision, reason);
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

async function handleRequestPrediction() {
  if (!predictionPanelState.value.canRequest || !selectorState.value.selectedArtifact || !sample.value) {
    return;
  }

  predictionLoading.value = true;
  predictionError.value = "";

  try {
    predictionResult.value = await fetchBenchmarkPrediction(
      selectedDatasetName.value,
      selectorState.value.selectedArtifact.artifact_id,
      selectedSplit.value,
      selectedSampleIndex.value,
    );
  } catch (requestError) {
    predictionResult.value = null;
    predictionError.value =
      requestError instanceof Error ? requestError.message : "Failed to fetch benchmark prediction.";
  } finally {
    predictionLoading.value = false;
  }
}

async function handleRequestSuggestion() {
  if (!selectedDatasetName.value || !sample.value) {
    return;
  }

  suggestionLoading.value = true;
  suggestionError.value = "";

  try {
    const payload = await fetchBenchmarkSuggestion(
      selectedDatasetName.value,
      selectedSplit.value,
      selectedSampleIndex.value,
    );
    suggestionPayload.value = payload;
    proposalSegments.value = createProposalSegments(payload);
    suggestionStatus.value = "pending";
  } catch (requestError) {
    suggestionPayload.value = null;
    proposalSegments.value = [];
    suggestionStatus.value = "idle";
    suggestionError.value =
      requestError instanceof Error ? requestError.message : "Failed to load model suggestion.";
  } finally {
    suggestionLoading.value = false;
  }
}

async function handleAcceptSuggestion() {
  if (!sample.value || !proposalSegments.value.length || suggestionStatus.value !== "pending") {
    return;
  }

  sample.value = {
    ...sample.value,
    segments: proposalSegments.value.map((segment) => ({
      id: segment.id,
      start: segment.start,
      end: segment.end,
      label: segment.label,
    })),
  };
  selectedSegmentId.value = proposalSegments.value[0]?.id ?? null;
  await markSuggestionDecision("accepted", "user_accepted_model_suggestion");
}

async function handleOverrideSuggestion() {
  await markSuggestionDecision("overridden", "user_explicitly_overrode_model_suggestion");
}

function handleSelectSegment(segmentId) {
  selectedSegmentId.value = segmentId;
  editFeedback.value = "";
  operationFeedback.value = "";
}

async function handleMoveBoundary({ boundaryIndex, nextBoundaryStart }) {
  await markSuggestionDecision("overridden", "manual_boundary_edit_after_suggestion_review");
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

async function handleUpdateSegmentLabel(nextLabel) {
  await markSuggestionDecision("overridden", "manual_label_edit_after_suggestion_review");
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

async function handleRunOperation(request) {
  await markSuggestionDecision("overridden", "manual_operation_after_suggestion_review");
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
    sessionId: sessionPanelState.value.sessionId,
    seriesId: sessionPanelState.value.seriesId,
    segmentationId: sessionPanelState.value.segmentationId,
    startedAt: sessionPanelState.value.startedAt,
    endedAt: sessionPanelState.value.endedAt,
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
    clearPredictionState();
    refreshCompatibility();
  },
  { immediate: true },
);

watch(
  [selectedDatasetName, selectedSplit, selectedSampleIndex],
  ([datasetName]) => {
    if (!datasetName || selectorError.value) {
      clearPredictionState();
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
        <p class="eyebrow">HTS-503 suggestion workflow</p>
        <h1>Model suggestion workflow</h1>
        <p class="hero-copy">
          Load a model suggestion, compare it with the current segmentation, and accept or override
          it explicitly while keeping manual editing authoritative.
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

    <PredictionPanel :state="predictionPanelState" @request-prediction="handleRequestPrediction" />

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
      :session-panel-state="sessionPanelState"
      :operation-palette-state="operationPaletteState"
      :comparison-state="comparisonState"
      @select-segment="handleSelectSegment"
      @move-boundary="handleMoveBoundary"
      @update-segment-label="handleUpdateSegmentLabel"
      @run-operation="handleRunOperation"
      @export-log="handleExportLog"
      @request-suggestion="handleRequestSuggestion"
      @accept-suggestion="handleAcceptSuggestion"
      @override-suggestion="handleOverrideSuggestion"
    />
  </main>
</template>
