<script setup>
import { computed, onMounted, ref, watch } from "vue";

import ModelComparisonPanel from "../components/comparison/ModelComparisonPanel.vue";
import HistoryPanel from "../components/history/HistoryPanel.vue";
import OperationPalette from "../components/operations/OperationPalette.vue";
import TimelineViewer from "../components/viewer/TimelineViewer.vue";
import WarningPanel from "../components/warnings/WarningPanel.vue";
import { AVAILABLE_SEGMENT_LABELS } from "../lib/segments/updateSegmentLabel";
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
  <div class="research-viewport">
    <!-- Topbar: selectors + compatibility indicator + Run Prediction button -->
    <header class="research-topbar">
      <div class="topbar-selectors">
        <label class="topbar-field">
          <span class="topbar-label">Dataset</span>
          <select
            class="topbar-input"
            :value="selectorState.selectedDataset?.name ?? ''"
            :disabled="selectorState.loading || !selectorState.datasetOptions.length"
            @change="handleUpdateDataset($event.target.value)"
          >
            <option value="" disabled>Select dataset</option>
            <option v-for="option in selectorState.datasetOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="topbar-field">
          <span class="topbar-label">Model</span>
          <select
            class="topbar-input"
            :value="selectorState.selectedArtifact?.artifact_id ?? ''"
            :disabled="selectorState.loading || !selectorState.modelOptions.length"
            @change="handleUpdateArtifact($event.target.value)"
          >
            <option value="" disabled>Select model</option>
            <option
              v-for="option in selectorState.modelOptions"
              :key="option.value"
              :value="option.value"
              :disabled="option.disabled"
            >
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="topbar-field">
          <span class="topbar-label">Split</span>
          <select
            class="topbar-input"
            :value="selectorState.selectedSplit"
            :disabled="selectorState.loading || !selectorState.selectedDataset"
            @change="handleUpdateSplit($event.target.value)"
          >
            <option value="train">Train</option>
            <option value="test">Test</option>
          </select>
        </label>

        <label class="topbar-field">
          <span class="topbar-label">Sample</span>
          <input
            class="topbar-input topbar-input-number"
            type="number"
            min="0"
            :max="selectorState.maxSampleIndex"
            :value="selectorState.sampleIndex"
            :disabled="selectorState.loading || !selectorState.selectedDataset"
            @input="handleUpdateSampleIndex($event.target.value)"
          />
        </label>
      </div>

      <span
        class="topbar-compat"
        :class="{
          'topbar-compat-loading': selectorState.compatibilityTone === 'loading',
          'topbar-compat-ok': selectorState.compatibilityTone === 'ok',
          'topbar-compat-warn': selectorState.compatibilityTone === 'warn',
          'topbar-compat-error': selectorState.compatibilityTone === 'error',
        }"
      >
        {{ selectorState.compatibilityMessage }}
      </span>

      <button
        class="topbar-run-button"
        type="button"
        :disabled="predictionPanelState.buttonDisabled"
        @click="handleRequestPrediction"
      >
        ▶ {{ predictionPanelState.buttonLabel }}
      </button>
    </header>

    <p v-if="error || selectorState.error" class="banner-error topbar-error">
      {{ error || selectorState.error }}
    </p>

    <!-- Main content: left column (chart + segment list) + right column (controls) -->
    <div class="viewport-body">
      <section class="col-left" aria-label="Timeline and segments">
        <div class="chart-panel">
          <div class="chart-panel-header">
            <span class="section-label">
              {{ sample?.datasetName ?? (loading ? "Loading…" : "No sample") }}
              <span v-if="sample"> · Sample {{ sample.sampleId }}</span>
            </span>
            <span class="surface-tag">{{ sample?.seriesLength ?? "--" }} pts</span>
          </div>

          <TimelineViewer
            :sample="sample"
            :selected-segment-id="selectedSegmentId"
            @select-segment="handleSelectSegment"
            @move-boundary="handleMoveBoundary"
          />

          <p v-if="editFeedback" class="drag-feedback">{{ editFeedback }}</p>
        </div>

        <div class="segment-list-panel">
          <div class="segment-list-header">
            <span class="section-label">Segment index</span>
            <span class="surface-tag">{{ sample?.segments?.length ?? 0 }} segments</span>
          </div>

          <ul v-if="sample?.segments?.length" class="overlay-segment-list segment-list-scroll">
            <li
              v-for="segment in sample.segments"
              :key="segment.id"
              class="overlay-segment-item"
              :class="{ 'overlay-segment-item-active': segment.id === selectedSegmentId }"
            >
              <span class="segment-chip" :class="`segment-chip-${segment.label}`">{{ segment.label }}</span>
              <button class="segment-select-button" type="button" @click="handleSelectSegment(segment.id)">
                {{ segment.start }}-{{ segment.end }}
              </button>
            </li>
          </ul>
          <div v-else class="overlay-placeholder">
            {{ loading ? "Preparing segments…" : "No segments loaded." }}
          </div>
        </div>
      </section>

      <!-- Right column: label editor + operations + model comparison + session stats -->
      <aside class="col-right" aria-label="Controls and comparison">
        <div v-if="selectedSegment" class="label-editor">
          <label class="label-editor-field">
            <span class="sidebar-label">Segment label</span>
            <select
              class="label-editor-select"
              :value="selectedSegment.label"
              @change="handleUpdateSegmentLabel($event.target.value)"
            >
              <option v-for="label in AVAILABLE_SEGMENT_LABELS" :key="label" :value="label">
                {{ label }}
              </option>
            </select>
          </label>
        </div>

        <OperationPalette
          :state="operationPaletteState"
          @run-operation="handleRunOperation"
        />

        <ModelComparisonPanel
          :state="comparisonState"
          @request-suggestion="handleRequestSuggestion"
          @accept-suggestion="handleAcceptSuggestion"
          @override-suggestion="handleOverrideSuggestion"
        />

        <div class="session-stats-panel">
          <div class="session-stats-header">
            <span class="section-label">Session · {{ sessionPanelState.eventCount }} events</span>
          </div>
          <ul class="status-strip-inline">
            <li v-for="item in pageState.statusItems" :key="item.label" class="status-pill">
              <span class="status-pill-label">{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </li>
          </ul>
          <ul v-if="pageState.sidebarItems.length" class="sidebar-list sidebar-list-compact">
            <li v-for="item in pageState.sidebarItems" :key="item.label" class="sidebar-item">
              <span class="sidebar-label">{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </li>
          </ul>
        </div>
      </aside>
    </div>

    <!-- Bottom strip: warnings pill + audit log -->
    <footer class="bottom-strip">
      <details class="strip-item warnings-strip">
        <summary class="strip-summary">
          <span
            class="strip-pill"
            :class="warningDisplay ? 'strip-pill-warn' : 'strip-pill-ok'"
          >
            {{ warningDisplay ? `⚠ ${warningDisplay.status}` : "✓ No warnings" }}
          </span>
        </summary>
        <div class="strip-body">
          <WarningPanel :warning="warningDisplay" />
        </div>
      </details>

      <details class="strip-item history-strip">
        <summary class="strip-summary">
          <span class="strip-pill">
            {{ sessionPanelState.eventCount }} audit event{{ sessionPanelState.eventCount !== 1 ? "s" : "" }}
          </span>
        </summary>
        <div class="strip-body">
          <HistoryPanel
            :entries="historyEntries"
            :session="sessionPanelState"
            @export-log="handleExportLog"
          />
        </div>
      </details>
    </footer>
  </div>
</template>
