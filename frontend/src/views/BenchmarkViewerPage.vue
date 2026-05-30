<script setup>
import { computed, onMounted, ref, watch } from "vue";

import ModelComparisonPanel from "../components/comparison/ModelComparisonPanel.vue";
import OutputPanel from "../components/output/OutputPanel.vue";
import MinFlipStrip from "../components/output/MinFlipStrip.vue";
import EvidenceZone from "../components/evidence/EvidenceZone.vue";
import FidelityStrip from "../components/evidence/FidelityStrip.vue";
import OperationPalette from "../components/palette/OperationPalette.vue";
import SemanticLayerPanel from "../components/semantic/SemanticLayerPanel.vue";
import TimelineViewer from "../components/viewer/TimelineViewer.vue";
import CompensationModeSelector from "../components/constraints/CompensationModeSelector.vue";
import PredictedLabelChip from "../components/relabel/PredictedLabelChip.vue";
import DonorPicker from "../components/donors/DonorPicker.vue";
import AlignWarpPanel from "../components/alignment/AlignWarpPanel.vue";
import DecompositionEditor from "../components/decomposition/DecompositionEditor.vue";
import GapFillPicker from "../components/gaps/GapFillPicker.vue";
import ScopeAttributeEditor from "../components/scope/ScopeAttributeEditor.vue";
import GuardrailsSidebar from "../components/guardrails/GuardrailsSidebar.vue";
import { createOutputPanelState } from "../lib/output/createOutputPanelState";
import { createPlausibilityGaugesState } from "../lib/evidence/createPlausibilityGaugesState";
import { createFidelityStripState } from "../lib/fidelity/createFidelityStripState";
import { updateSegmentScope } from "../services/api/segmentsApi";
import { validationBus } from "../lib/audit/validationBus";
import {
  isCompensationRequired as isCompensationModeRequired,
} from "../lib/constraints/createCompensationModeSelectorState";
import { AVAILABLE_SEGMENT_LABELS } from "../lib/segments/updateSegmentLabel";
import {
  appendAuditEvent,
  createEditAuditEvent,
  createOperationAuditEvent,
  createSuggestionAuditEvent,
} from "../lib/audit/auditEvents";
import { createSessionPanelState } from "../lib/audit/createSessionPanelState";
import { createPredictionPanelState } from "../lib/benchmarks/createPredictionPanelState";
import { createViewerSampleFromApi } from "../lib/benchmarks/createViewerSampleFromApi";
import { createBenchmarkSelectorState } from "../lib/benchmarks/createBenchmarkSelectorState";
import { reconcileBenchmarkSelection } from "../lib/benchmarks/reconcileBenchmarkSelection";
import { SOFT_CONSTRAINT_STATUS } from "../lib/constraints/evaluateSoftConstraints";
import { createOperationPaletteState } from "../lib/operations/createOperationPaletteState";
import { createTieredPaletteState } from "../lib/operations/createTieredPaletteState";
import { executeOperationAction } from "../lib/operations/executeOperationAction";
import { buildInvokeRequest, UnknownOpError } from "../lib/operations/buildInvokeRequest";
import { findMinimalFlip, invokeOperation } from "../services/api/operationsApi";
import { labelChipBus } from "../lib/audit/labelChipBus";
import { classifyGap } from "../lib/gaps/createGapGatingState";
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
  adaptModel,
  fetchBenchmarkCompatibility,
  fetchBenchmarkDatasets,
  fetchBenchmarkModels,
  fetchBenchmarkOperationRegistry,
  fetchBenchmarkPrediction,
  fetchBenchmarkSample,
  fetchBenchmarkSuggestion,
  fetchBenchmarkUncertainty,
  fetchEvidencePlausibility,
  predictBenchmarkValues,
  submitSuggestionDecision,
} from "../services/api/benchmarkApi";
import {
  fetchSemanticPacks,
  labelSemanticSegments,
  validateSemanticPackYaml,
} from "../services/api/semanticPackApi";
import {
  CUSTOM_OPTION_KEY,
  NONE_OPTION_KEY,
  applySemanticLabelsToSegments,
  buildSegmentLabelMap,
} from "../lib/semantic/createSemanticLayerState";
import {
  loadSemanticLayerSession,
  saveSemanticLayerSession,
} from "../lib/semantic/sessionStorage";

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
const baselinePrediction = ref(null);
const currentPrediction = ref(null);
const seriesVersion = ref(0);
const currentPredictionVersion = ref(null);
const baselineValues = ref(null);
const plausibilityResult = ref(null);
const plausibilityVersion = ref(null);
const plausibilityError = ref(null);
let plausibilityRequestId = 0;
// REWORK-06: per-rerun validity log. Each entry is `{version, flipped}` —
// "flipped" iff the rerun's predicted_label differs from the locked baseline.
// VAL-012's session-cumulative rate is `flipped / total` over this list.
const validityRuns = ref([]);
// REWORK-07: min-flip probe state.
const minFlipResult = ref(null);
const minFlipError = ref(null);
let minFlipRequestId = 0;
const probeFlags = ref({ saliency: false, deltaSources: false, minFlipSearching: false });
const operationRegistry = ref(null);
const proposalSegments = ref([]);
const suggestionPayload = ref(null);
const suggestionLoading = ref(false);
const suggestionError = ref("");
const suggestionStatus = ref("idle");
const uncertaintyPayload = ref(null);
const adaptLoading = ref(false);
const adaptError = ref("");
const adaptVersionId = ref(null);
const selectedLabeler = ref("prototype");
const pendingOpName = ref(null);
const aggregateResult = ref(null);
const selectedCompensationMode = ref(null);
const compensationModeTouched = ref(false);
const undoStack = ref([]);
const UNDO_STACK_LIMIT = 10;
const donorPickerOpen = ref(false);
const alignWarpPanelOpen = ref(false);
const decompositionEditorOpen = ref(false);
const decompositionBlob = ref(null);
const gapFillPickerOpen = ref(false);
const scopeEditorOpen = ref(false);
const scopeEditorSegment = ref(null);
const scopeEditorError = ref(null);
const segmentContextMenu = ref(null);
let compatibilityRequestId = 0;

const semanticPacks = ref([]);
const semanticPacksLoading = ref(false);
const semanticActivePackKey = ref(NONE_OPTION_KEY);
const semanticActivePack = ref(null);
const semanticLabelResults = ref([]);
const semanticCustomError = ref(null);
const semanticCustomYamlText = ref("");
let semanticRequestId = 0;

const selectedSegment = computed(() =>
  getSelectedSegment(sample.value?.segments ?? [], selectedSegmentId.value),
);

const semanticSegmentLabelMap = computed(() =>
  buildSegmentLabelMap(semanticLabelResults.value),
);
const semanticAnnotatedSegments = computed(() => {
  if (!sample.value?.segments) return [];
  if (semanticActivePackKey.value === NONE_OPTION_KEY) return sample.value.segments;
  return applySemanticLabelsToSegments(sample.value.segments, semanticSegmentLabelMap.value);
});
const enrichedSample = computed(() => {
  if (!sample.value) return null;
  if (semanticActivePackKey.value === NONE_OPTION_KEY) return sample.value;
  return { ...sample.value, segments: semanticAnnotatedSegments.value };
});
const pageState = computed(() => createViewerPageState(sample.value, selectedSegment.value));
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
const tieredPaletteSelectedIds = computed(() =>
  selectedSegmentId.value ? [selectedSegmentId.value] : [],
);
const tieredPaletteSelectedShapes = computed(() => {
  const shape = selectedSegment.value?.shape ?? selectedSegment.value?.label ?? null;
  return shape ? [shape] : [];
});
const selectedSegmentGapInfo = computed(() => {
  const seg = selectedSegment.value;
  const values = sample.value?.values;
  if (!seg || !Array.isArray(values)) return null;
  const segmentValues = values.slice(seg.start, seg.end + 1);
  return classifyGap({ segment: seg, segmentValues });
});
const activeDomainHint = computed(() => {
  const segDomain = selectedSegment.value?.scope?.domainHintKey;
  if (segDomain) return segDomain;
  return sample.value?.domainHint ?? sample.value?.metadata?.domainHint ?? null;
});
const selectedSegmentOpCategory = computed(() => {
  return selectedSegment.value?.shape ?? selectedSegment.value?.label ?? null;
});
const compensationSelectorVisible = computed(() =>
  isCompensationModeRequired(activeDomainHint.value, selectedSegmentOpCategory.value),
);
const lastConstraintLaw = computed(() => operationConstraintResult.value?.law ?? null);
const donorPickerTargetClass = computed(() => {
  const candidates = sample.value?.classes ?? sample.value?.metadata?.classes ?? null;
  const currentLabel = sample.value?.label ?? null;
  if (Array.isArray(candidates)) {
    const other = candidates.find((c) => c && c !== currentLabel);
    if (other) return other;
    if (candidates[0]) return candidates[0];
  }
  return currentLabel ?? 'class-1';
});
const comparisonState = computed(() =>
  createModelComparisonState({
    currentSegments: sample.value?.segments ?? [],
    proposalSegments: proposalSegments.value,
    selectedArtifact: selectorState.value.selectedArtifact ?? null,
    suggestionStatus: suggestionStatus.value,
    suggestionLoading: suggestionLoading.value,
    suggestionError: suggestionError.value,
    auditEvents: auditEvents.value,
    adaptLoading: adaptLoading.value,
    adaptError: adaptError.value,
    adaptVersionId: adaptVersionId.value,
    selectedLabeler: selectedLabeler.value,
    suggestionLabeler: suggestionPayload.value?.labeler ?? null,
  }),
);

function clearPredictionState() {
  predictionLoading.value = false;
  predictionError.value = "";
  predictionResult.value = null;
  baselinePrediction.value = null;
  currentPrediction.value = null;
  seriesVersion.value = 0;
  currentPredictionVersion.value = null;
  baselineValues.value = null;
  plausibilityResult.value = null;
  plausibilityVersion.value = null;
  plausibilityError.value = null;
  validityRuns.value = [];
  minFlipResult.value = null;
  minFlipError.value = null;
  probeFlags.value = { saliency: false, deltaSources: false, minFlipSearching: false };
}

function bumpSeriesVersion() {
  seriesVersion.value += 1;
}

const outputPanelState = computed(() =>
  createOutputPanelState({
    baseline: baselinePrediction.value,
    current: currentPrediction.value,
    loading: predictionLoading.value,
    error: predictionError.value || null,
    seriesVersion: seriesVersion.value,
    currentVersion: currentPredictionVersion.value,
  }),
);

const outputPanelArtifactLabel = computed(() => {
  const artifact = selectorState.value?.selectedArtifact;
  if (!artifact) return "";
  return artifact.display_name ?? artifact.artifact_id ?? "";
});

const plausibilityGaugesState = computed(() =>
  createPlausibilityGaugesState({
    validityRuns: validityRuns.value,
    plausibility: plausibilityResult.value,
    hasEdit: seriesVersion.value > 0,
  }),
);

const fidelityStripState = computed(() =>
  createFidelityStripState({
    // Prefer the most recent current prediction — when the user has scored an
    // edited series, that response carries the transforms actually applied to
    // their values. Fall back to baseline before any edit lands.
    prediction: currentPrediction.value ?? baselinePrediction.value,
    compatibility: compatibilityResult.value,
    rawInputLength: Array.isArray(sample.value?.values) ? sample.value.values.length : null,
  }),
);

async function refreshPlausibilityGauges() {
  // Only run when there is a baseline series locked AND the user has touched
  // the series at least once. seriesVersion === 0 is the "before any edit"
  // state — no edit means nothing to compare, no point calling the backend.
  if (
    !sample.value ||
    !Array.isArray(sample.value.values) ||
    seriesVersion.value === 0 ||
    !baselineValues.value
  ) {
    plausibilityResult.value = null;
    plausibilityVersion.value = null;
    return;
  }
  const datasetName = selectedDatasetName.value;
  if (!datasetName) return;

  const targetClass =
    baselinePrediction.value?.predicted_label ??
    sample.value?.label ??
    sample.value?.classes?.[0] ??
    null;
  if (targetClass == null) return;

  if (baselineValues.value.length !== sample.value.values.length) {
    // Skip when shapes diverge — could happen mid-operation; the next stable
    // version will retry.
    return;
  }

  const requestId = ++plausibilityRequestId;
  const scoredVersion = seriesVersion.value;
  try {
    const payload = await fetchEvidencePlausibility({
      datasetName,
      baselineValues: baselineValues.value,
      currentValues: sample.value.values,
      targetClass,
    });
    if (requestId === plausibilityRequestId) {
      plausibilityResult.value = payload;
      plausibilityVersion.value = scoredVersion;
    }
  } catch (requestError) {
    if (requestId === plausibilityRequestId) {
      // Surface no fabricated numbers — keep last good result and record the
      // error on a dedicated ref so it does not appear in the operation
      // feedback strip (the operation itself succeeded; only the diagnostic
      // refresh failed).
      plausibilityError.value =
        requestError instanceof Error
          ? requestError.message
          : "Failed to refresh plausibility gauges.";
    }
  }
}

function handleToggleSaliency() {
  probeFlags.value = { ...probeFlags.value, saliency: !probeFlags.value.saliency };
}

function handleToggleDeltaSources() {
  probeFlags.value = {
    ...probeFlags.value,
    deltaSources: !probeFlags.value.deltaSources,
  };
}

async function handleProbeMinFlip() {
  if (probeFlags.value.minFlipSearching) return;
  const artifact = selectorState.value?.selectedArtifact;
  // The probe asks "what is the smallest edit *from the baseline* that flips
  // the model?" — so we always seed from the locked baseline snapshot, never
  // the user's mid-edit series. baselineValues is captured at sample-load
  // (REWORK-02); if it is missing (no sample yet), there is nothing to probe.
  const seed = Array.isArray(baselineValues.value)
    ? baselineValues.value
    : Array.isArray(sample.value?.values)
      ? sample.value.values
      : null;
  if (!artifact || !seed) {
    minFlipError.value = "Load a sample and pick a model before probing for a minimal flip.";
    return;
  }
  const requestId = ++minFlipRequestId;
  probeFlags.value = { ...probeFlags.value, minFlipSearching: true };
  minFlipError.value = null;
  try {
    const result = await findMinimalFlip({
      artifactId: artifact.artifact_id,
      baselineValues: seed,
    });
    if (requestId !== minFlipRequestId) return;
    minFlipResult.value = result;
  } catch (requestError) {
    if (requestId !== minFlipRequestId) return;
    minFlipResult.value = null;
    minFlipError.value =
      requestError instanceof Error ? requestError.message : "Min-flip probe failed.";
  } finally {
    if (requestId === minFlipRequestId) {
      probeFlags.value = { ...probeFlags.value, minFlipSearching: false };
    }
  }
}

function handleApplyMinFlip() {
  const result = minFlipResult.value;
  const edit = result?.edit_values;
  if (!Array.isArray(edit) || edit.length === 0 || !sample.value) return;
  if (!Array.isArray(sample.value.values) || sample.value.values.length !== edit.length) return;
  // Mutating the series via the same channel as applyInvokeResponse keeps the
  // downstream state machine (OUTPUT staleness, EVIDENCE refresh) honest.
  sample.value = { ...sample.value, values: [...edit] };
  bumpSeriesVersion();
  // CLAUDE.md: every user operation produces an AuditEvent. Apply-min-flip
  // mutates the series, so it must be logged with the probe's provenance
  // (method + paper reference + distance + flipped class).
  auditEvents.value = appendAuditEvent(
    auditEvents.value,
    createOperationAuditEvent(
      {
        type: 'min-flip-apply',
        method: result.method,
        reference: result.reference,
        distance: result.distance,
        baseline_class: result.baseline_class,
        flipped_class: result.flipped_class,
        points_touched: edit.length,
      },
      {
        ok: true,
        constraintStatus: SOFT_CONSTRAINT_STATUS.PASS,
        warnings: [],
        operationResult: { affectedSegmentIds: [] },
        message: `Applied min-flip edit · ${result.baseline_class} → ${result.flipped_class}`,
        selectedSegmentId: selectedSegmentId.value,
      },
      { sampleId: sample.value?.sampleId ?? null, selectedSegmentId: selectedSegmentId.value },
    ),
  );
  // Dismiss the strip + ghost — the edit is now the user's current series.
  minFlipResult.value = null;
  minFlipError.value = null;
}

function handleClearMinFlip() {
  minFlipResult.value = null;
  minFlipError.value = null;
}

const minFlipGhostValues = computed(() => {
  const edit = minFlipResult.value?.edit_values;
  return Array.isArray(edit) && edit.length > 0 ? edit : null;
});

function clearSuggestionState() {
  suggestionPayload.value = null;
  suggestionLoading.value = false;
  suggestionError.value = "";
  suggestionStatus.value = "idle";
  proposalSegments.value = [];
  uncertaintyPayload.value = null;
  adaptLoading.value = false;
  adaptError.value = "";
  adaptVersionId.value = null;
  selectedLabeler.value = "prototype";
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
    baselineValues.value = Array.isArray(sample.value?.values)
      ? [...sample.value.values]
      : null;
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
    const result = await fetchBenchmarkPrediction(
      selectedDatasetName.value,
      selectorState.value.selectedArtifact.artifact_id,
      selectedSplit.value,
      selectedSampleIndex.value,
    );
    predictionResult.value = result;
    // Baseline is locked at the moment the user first scores this sample; the same
    // result also seeds Current so the OUTPUT zone has something to render until
    // an edit makes the series diverge.
    baselinePrediction.value = result;
    currentPrediction.value = result;
    currentPredictionVersion.value = seriesVersion.value;
  } catch (requestError) {
    predictionResult.value = null;
    predictionError.value =
      requestError instanceof Error ? requestError.message : "Failed to fetch benchmark prediction.";
  } finally {
    predictionLoading.value = false;
  }
}

async function handleRerunPrediction() {
  // Empty-state path: no baseline yet → behave like Request prediction.
  if (!baselinePrediction.value) {
    await handleRequestPrediction();
    return;
  }
  const artifact = selectorState.value?.selectedArtifact;
  if (!artifact || !Array.isArray(sample.value?.values)) {
    return;
  }
  const scoredVersion = seriesVersion.value;
  predictionLoading.value = true;
  predictionError.value = "";
  try {
    const result = await predictBenchmarkValues(artifact.artifact_id, sample.value.values);
    currentPrediction.value = result;
    currentPredictionVersion.value = scoredVersion;
    // REWORK-06: record VAL-012 validity outcome for this rerun. The edit is
    // "valid" iff the rerun's prediction differs from the locked baseline.
    // Same out-of-order-response window as currentPrediction itself — entries
    // carry `version` so the list is reconstructable in arrival order if a
    // future ticket adds a request-id guard.
    const baselineLabel = baselinePrediction.value?.predicted_label ?? null;
    const flipped = baselineLabel != null && result?.predicted_label !== baselineLabel;
    validityRuns.value = [
      ...validityRuns.value,
      { version: scoredVersion, flipped: Boolean(flipped) },
    ];
  } catch (requestError) {
    predictionError.value =
      requestError instanceof Error ? requestError.message : "Failed to re-score the current series.";
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
      selectedLabeler.value,
    );
    suggestionPayload.value = payload;
    proposalSegments.value = createProposalSegments(payload);
    suggestionStatus.value = "pending";

    // Fetch uncertainty non-blockingly; failure does not affect suggestion display.
    fetchBenchmarkUncertainty(
      selectedDatasetName.value,
      selectedSplit.value,
      selectedSampleIndex.value,
    )
      .then((u) => {
        uncertaintyPayload.value = u;
      })
      .catch(() => {
        uncertaintyPayload.value = null;
      });
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

async function handleOpInvoked({ tier, op_name, params = {} }) {
  if (tier === 1 && op_name === 'replace_from_library') {
    if (!sample.value || !selectedSegment.value) {
      operationFeedback.value = 'replace_from_library: select a segment first.';
      return;
    }
    closeAllPanels();
    donorPickerOpen.value = true;
    return;
  }

  if (tier === 1 && op_name === 'suppress'
      && selectedSegmentGapInfo.value?.exceedsThreshold
      && !selectedSegmentGapInfo.value?.isFilled) {
    if (!sample.value || !selectedSegment.value) {
      operationFeedback.value = 'suppress: select a segment first.';
      return;
    }
    closeAllPanels();
    gapFillPickerOpen.value = true;
    return;
  }

  if (tier === 3 && op_name === 'align_warp') {
    if (!sample.value || tieredPaletteSelectedIds.value.length < 2) {
      operationFeedback.value = 'align_warp: select 2+ segments first.';
      return;
    }
    closeAllPanels();
    alignWarpPanelOpen.value = true;
    return;
  }

  if (tier === 3 && op_name === 'decompose') {
    if (!sample.value || !selectedSegment.value) {
      operationFeedback.value = 'decompose: select a segment first.';
      return;
    }
    closeAllPanels();
    await dispatchDecomposeAndOpenEditor();
    return;
  }

  if (tier === 0) {
    pendingOpName.value = op_name;
    try {
      if (op_name === 'split') {
        const splitIndex = operationPaletteState.value.suggestedSplitIndex;
        if (splitIndex != null) {
          await handleRunOperation({ type: 'split', segmentId: selectedSegmentId.value, splitIndex });
        } else {
          operationFeedback.value = 'Split: no valid split point for this segment.';
        }
      } else if (op_name === 'merge') {
        const left = operationPaletteState.value.leftMergeTarget;
        const right = operationPaletteState.value.rightMergeTarget;
        if (left) {
          await handleRunOperation({ type: 'merge', leftSegmentId: left.id, rightSegmentId: selectedSegmentId.value });
        } else if (right) {
          await handleRunOperation({ type: 'merge', leftSegmentId: selectedSegmentId.value, rightSegmentId: right.id });
        } else {
          operationFeedback.value = 'Merge: no adjacent segment available.';
        }
      } else {
        operationFeedback.value = `${op_name}: not yet wired to backend.`;
      }
    } finally {
      pendingOpName.value = null;
    }
    return;
  }

  await dispatchTier123Op({ tier, op_name, params });
}

async function dispatchTier123Op({ tier, op_name, params, bypassPickerCheck = false }) {
  if (!sample.value || !selectedSegment.value) {
    operationFeedback.value = `${op_name}: select a segment first.`;
    return;
  }

  if (compensationSelectorVisible.value && !compensationModeTouched.value) {
    operationFeedback.value = 'Choose a compensation mode to confirm this op.';
    return;
  }

  let plan;
  try {
    plan = buildInvokeRequest({
      tier,
      op_name,
      params,
      sample: sample.value,
      selectedSegment: selectedSegment.value,
      gapInfo: selectedSegmentGapInfo.value,
      domain_hint: activeDomainHint.value,
      compensation_mode: compensationSelectorVisible.value ? selectedCompensationMode.value : null,
      bypassPickerCheck,
    });
  } catch (buildError) {
    operationFeedback.value =
      buildError instanceof UnknownOpError
        ? `${op_name}: unknown op.`
        : (buildError.message ?? `${op_name}: failed to build request.`);
    return;
  }

  if (plan.kind === 'picker-pending') {
    operationFeedback.value = plan.message;
    return;
  }

  pendingOpName.value = op_name;
  try {
    const snapshot = sample.value
      ? { values: [...(sample.value.values ?? [])], segments: (sample.value.segments ?? []).map((s) => ({ ...s })) }
      : null;
    const response = await invokeOperation(plan.body);
    if (snapshot) pushUndoSnapshot(snapshot);
    applyInvokeResponse({ tier, op_name, params, response });
  } catch (requestError) {
    operationFeedback.value =
      requestError instanceof Error ? requestError.message : `${op_name}: request failed.`;
  } finally {
    pendingOpName.value = null;
  }
}

function pushUndoSnapshot(snapshot) {
  const next = [...undoStack.value, snapshot];
  if (next.length > UNDO_STACK_LIMIT) next.shift();
  undoStack.value = next;
}

function popUndoSnapshot() {
  if (undoStack.value.length === 0) return null;
  const next = [...undoStack.value];
  const top = next.pop();
  undoStack.value = next;
  return top;
}

function handleCompensationModeChange(mode) {
  selectedCompensationMode.value = mode;
  compensationModeTouched.value = true;
}

watch(selectedSegmentId, () => {
  selectedCompensationMode.value = null;
  compensationModeTouched.value = false;
});

function handleGlobalEscape(event) {
  if (event.key !== 'Escape') return;
  if (segmentContextMenu.value) {
    segmentContextMenu.value = null;
  } else if (gapFillPickerOpen.value) {
    handleGapFillClose();
  } else if (alignWarpPanelOpen.value) {
    handleAlignPanelClose();
  } else if (decompositionEditorOpen.value) {
    handleDecompositionEditorClose();
  }
}

onMounted(() => {
  if (typeof window !== 'undefined') window.addEventListener('keydown', handleGlobalEscape);
});

function handleChipAccept({ chipId, segmentId, newShape, opId }) {
  if (!sample.value || !segmentId || !newShape) return;
  const segs = (sample.value.segments ?? []).map((seg) =>
    seg.id === segmentId ? { ...seg, label: newShape, shape: newShape } : seg,
  );
  sample.value = { ...sample.value, segments: segs };
  auditEvents.value = appendAuditEvent(
    auditEvents.value,
    createOperationAuditEvent(
      { type: 'chip-accept', chipId, segmentId, newShape, opId },
      {
        ok: true,
        constraintStatus: SOFT_CONSTRAINT_STATUS.PASS,
        warnings: [],
        operationResult: { affectedSegmentIds: [segmentId] },
        message: `Accepted predicted label "${newShape}".`,
        selectedSegmentId: segmentId,
      },
      { sampleId: sample.value?.sampleId ?? null, selectedSegmentId: segmentId },
    ),
  );
}

function handleChipOverride({ chipId, segmentId, chosenShape, opId }) {
  if (!sample.value || !segmentId || !chosenShape) return;
  const segs = (sample.value.segments ?? []).map((seg) =>
    seg.id === segmentId ? { ...seg, label: chosenShape, shape: chosenShape } : seg,
  );
  sample.value = { ...sample.value, segments: segs };
  auditEvents.value = appendAuditEvent(
    auditEvents.value,
    createOperationAuditEvent(
      { type: 'chip-override', chipId, segmentId, chosenShape, opId },
      {
        ok: true,
        constraintStatus: SOFT_CONSTRAINT_STATUS.PASS,
        warnings: [],
        operationResult: { affectedSegmentIds: [segmentId] },
        message: `Overrode predicted label to "${chosenShape}".`,
        selectedSegmentId: segmentId,
      },
      { sampleId: sample.value?.sampleId ?? null, selectedSegmentId: segmentId },
    ),
  );
}

function closeAllPanels() {
  donorPickerOpen.value = false;
  alignWarpPanelOpen.value = false;
  decompositionEditorOpen.value = false;
  gapFillPickerOpen.value = false;
  scopeEditorOpen.value = false;
  segmentContextMenu.value = null;
}

function handleDonorAccepted({ tier, op_name, params }) {
  donorPickerOpen.value = false;
  if (!params || !Array.isArray(params.donor_values) || params.donor_values.length === 0) {
    operationFeedback.value = 'replace_from_library: picker did not provide donor values.';
    return;
  }
  dispatchTier123Op({ tier, op_name, params, bypassPickerCheck: true });
}

function handleDonorPickerClose() {
  donorPickerOpen.value = false;
}

function handleAlignApplied({ tier, op_name, params }) {
  alignWarpPanelOpen.value = false;
  dispatchTier123Op({ tier, op_name, params, bypassPickerCheck: true });
}

function handleAlignPanelClose() {
  alignWarpPanelOpen.value = false;
}

async function dispatchDecomposeAndOpenEditor() {
  if (!sample.value || !selectedSegment.value) return;

  let plan;
  try {
    plan = buildInvokeRequest({
      tier: 3,
      op_name: 'decompose',
      params: {},
      sample: sample.value,
      selectedSegment: selectedSegment.value,
      gapInfo: selectedSegmentGapInfo.value,
      domain_hint: activeDomainHint.value,
      bypassPickerCheck: true,
    });
  } catch (buildError) {
    operationFeedback.value = buildError.message ?? 'decompose: failed to build request.';
    return;
  }
  if (plan.kind !== 'request') {
    operationFeedback.value = plan.message ?? 'decompose: cannot dispatch.';
    return;
  }

  pendingOpName.value = 'decompose';
  try {
    const response = await invokeOperation(plan.body);
    decompositionBlob.value = response.extra?.decomposition ?? null;
    if (!decompositionBlob.value) {
      operationFeedback.value = 'decompose: response did not include a decomposition blob.';
      return;
    }
    decompositionEditorOpen.value = true;
    operationFeedback.value = 'decompose: blob loaded; edit components below.';
    auditEvents.value = appendAuditEvent(
      auditEvents.value,
      createOperationAuditEvent(
        { type: 'decompose', tier: 3, op_name: 'decompose', params: {} },
        {
          ok: true,
          constraintStatus: SOFT_CONSTRAINT_STATUS.PASS,
          warnings: [],
          operationResult: { affectedSegmentIds: [selectedSegmentId.value].filter(Boolean) },
          message: 'decompose: blob loaded.',
          selectedSegmentId: selectedSegmentId.value,
        },
        { sampleId: sample.value?.sampleId ?? null, selectedSegmentId: selectedSegmentId.value },
      ),
    );
  } catch (requestError) {
    operationFeedback.value =
      requestError instanceof Error ? requestError.message : 'decompose: request failed.';
  } finally {
    pendingOpName.value = null;
  }
}

function handleDecompositionEditorOp({ op_name, params, segmentId }) {
  if (!op_name || !params) return;
  dispatchTier123Op({ tier: 2, op_name, params });
}

function handleDecompositionEditorClose() {
  decompositionEditorOpen.value = false;
  decompositionBlob.value = null;
}

function handleGapFillApplied({ tier, op_name, params }) {
  gapFillPickerOpen.value = false;
  dispatchTier123Op({ tier, op_name, params, bypassPickerCheck: true });
}

function handleGapFillClose() {
  gapFillPickerOpen.value = false;
}

function handleSegmentContextMenu(event, segment) {
  if (!segment) return;
  event.preventDefault();
  closeAllPanels();
  segmentContextMenu.value = {
    segmentId: segment.id,
    x: event.clientX ?? 0,
    y: event.clientY ?? 0,
  };
}

function handleContextMenuEditScope() {
  const ctx = segmentContextMenu.value;
  if (!ctx) return;
  const seg = (sample.value?.segments ?? []).find((s) => s.id === ctx.segmentId);
  segmentContextMenu.value = null;
  if (!seg) return;
  scopeEditorSegment.value = seg;
  scopeEditorError.value = null;
  scopeEditorOpen.value = true;
}

function handleScopeEditorClose() {
  scopeEditorOpen.value = false;
  scopeEditorError.value = null;
}

async function handleScopeUpdated(payload) {
  if (!payload || !payload.segmentId || !payload.scope) return;
  scopeEditorError.value = null;
  pendingOpName.value = 'scope_updated';
  try {
    const response = await updateSegmentScope(payload);
    const segs = (sample.value?.segments ?? []).map((seg) =>
      seg.id === payload.segmentId
        ? { ...seg, scope: { ...response.scope, domainHintKey: response.scope.domain_hint ?? null } }
        : seg,
    );
    sample.value = { ...sample.value, segments: segs };
    auditEvents.value = appendAuditEvent(
      auditEvents.value,
      createOperationAuditEvent(
        { type: 'scope_updated', segmentId: payload.segmentId, previousScope: payload.previousScope, nextScope: response.scope, triggerReclassify: payload.triggerReclassify },
        {
          ok: true,
          constraintStatus: SOFT_CONSTRAINT_STATUS.PASS,
          warnings: [],
          operationResult: { affectedSegmentIds: [payload.segmentId] },
          message: `scope_updated on ${payload.segmentId}.`,
          selectedSegmentId: payload.segmentId,
        },
        { sampleId: sample.value?.sampleId ?? null, selectedSegmentId: payload.segmentId },
      ),
    );
    scopeEditorOpen.value = false;
  } catch (requestError) {
    scopeEditorError.value =
      requestError instanceof Error ? requestError.message : 'Failed to save scope.';
  } finally {
    pendingOpName.value = null;
  }
}

function handleChipUndo({ chipId, segmentId, opId }) {
  const snapshot = popUndoSnapshot();
  if (!snapshot || !sample.value) {
    operationFeedback.value = 'Nothing to undo.';
    return;
  }
  sample.value = { ...sample.value, values: snapshot.values, segments: snapshot.segments };
  bumpSeriesVersion();
  auditEvents.value = appendAuditEvent(
    auditEvents.value,
    createOperationAuditEvent(
      { type: 'chip-undo', chipId, segmentId, opId },
      {
        ok: true,
        constraintStatus: SOFT_CONSTRAINT_STATUS.PASS,
        warnings: [],
        operationResult: { affectedSegmentIds: [segmentId].filter(Boolean) },
        message: 'Reverted last operation.',
        selectedSegmentId: segmentId ?? selectedSegmentId.value,
      },
      { sampleId: sample.value?.sampleId ?? null, selectedSegmentId: segmentId ?? selectedSegmentId.value },
    ),
  );
}

function applyInvokeResponse({ tier, op_name, params, response }) {
  const alignedSegments = response.extra?.aligned_segments;
  let valuesChanged = false;
  if (Array.isArray(alignedSegments) && alignedSegments.length > 0 && Array.isArray(sample.value?.values)) {
    const segById = new Map((sample.value.segments ?? []).map((s) => [s.id, s]));
    const next = sample.value.values.slice();
    for (const aligned of alignedSegments) {
      const seg = segById.get(aligned.segment_id);
      if (!seg || !Array.isArray(aligned.values)) continue;
      const len = Math.min(aligned.values.length, seg.end - seg.start + 1);
      for (let i = 0; i < len; i += 1) next[seg.start + i] = aligned.values[i];
    }
    sample.value = { ...sample.value, values: next };
    valuesChanged = true;
  } else if (Array.isArray(response.values) && selectedSegment.value && Array.isArray(sample.value?.values)) {
    const seg = selectedSegment.value;
    const next = sample.value.values.slice();
    const len = Math.min(response.values.length, seg.end - seg.start + 1);
    for (let i = 0; i < len; i += 1) next[seg.start + i] = response.values[i];
    sample.value = { ...sample.value, values: next };
    valuesChanged = true;
  }
  if (valuesChanged) bumpSeriesVersion();

  if (response.label_chip) {
    labelChipBus.publish(response.label_chip);
  }

  if (tier === 1 || tier === 2) {
    const residual = response.constraint_residual;
    const converged = residual ? (residual.converged ?? true) : true;
    validationBus.publish('validity_update', {
      rate: converged ? 1.0 : 0.0,
      tipShouldFire: residual ? !converged : false,
      recommendation: converged ? null : 'Constraint residual exceeded tolerance.',
    });
  }

  operationConstraintResult.value = response.constraint_residual ?? null;

  if (response.aggregate_result != null) {
    aggregateResult.value = response.aggregate_result;
    operationFeedback.value = `${op_name}: ${JSON.stringify(response.aggregate_result)}`;
  } else {
    operationFeedback.value = `${op_name}: applied.`;
  }
  editFeedback.value = "";
  editConstraintResult.value = null;

  auditEvents.value = appendAuditEvent(
    auditEvents.value,
    createOperationAuditEvent(
      { type: op_name, tier, op_name, params },
      {
        ok: true,
        constraintStatus: response.constraint_residual ? SOFT_CONSTRAINT_STATUS.WARN : SOFT_CONSTRAINT_STATUS.PASS,
        warnings: [],
        operationResult: { affectedSegmentIds: [selectedSegmentId.value].filter(Boolean) },
        message: `${op_name}: applied.`,
        selectedSegmentId: selectedSegmentId.value,
        chip: response.label_chip ?? null,
        constraintResidual: response.constraint_residual ?? null,
      },
      {
        sampleId: sample.value?.sampleId ?? null,
        selectedSegmentId: selectedSegmentId.value,
      },
    ),
  );
}

function handleUpdateLabeler(labeler) {
  selectedLabeler.value = labeler;
}

async function handleAdaptModel() {
  if (!comparisonState.value.canAdaptModel || !sample.value) {
    return;
  }

  adaptLoading.value = true;
  adaptError.value = "";

  const values = sample.value.values;
  const supportSegments = (sample.value.segments ?? []).map((seg) => ({
    label: seg.label,
    values: values.slice(seg.start, seg.end + 1),
  }));

  try {
    const result = await adaptModel(sessionPanelState.value.sessionId, supportSegments);
    adaptVersionId.value = result.model_version_id;
  } catch (requestError) {
    adaptError.value =
      requestError instanceof Error ? requestError.message : "Failed to adapt model.";
  } finally {
    adaptLoading.value = false;
  }
}

async function loadSemanticPacks() {
  semanticPacksLoading.value = true;
  try {
    const payload = await fetchSemanticPacks();
    semanticPacks.value = payload.packs ?? [];
  } catch (loadError) {
    semanticPacks.value = [];
    semanticCustomError.value = {
      message: loadError instanceof Error ? loadError.message : "Failed to load semantic packs.",
      kind: "schema",
    };
  } finally {
    semanticPacksLoading.value = false;
  }
}

async function refreshSemanticLabels() {
  const requestId = ++semanticRequestId;
  if (
    semanticActivePackKey.value === NONE_OPTION_KEY ||
    !sample.value?.segments?.length ||
    !Array.isArray(sample.value.values)
  ) {
    semanticLabelResults.value = [];
    return;
  }
  const isCustom = semanticActivePackKey.value === CUSTOM_OPTION_KEY;
  const customYaml = isCustom ? semanticCustomYamlText.value : null;
  if (isCustom && !customYaml) {
    semanticLabelResults.value = [];
    return;
  }
  try {
    const segmentsPayload = sample.value.segments.map((seg) => ({
      id: seg.id,
      start: seg.start,
      end: seg.end,
      shape: seg.shape ?? seg.label ?? "noise",
    }));
    const response = await labelSemanticSegments({
      packName: isCustom ? null : semanticActivePackKey.value,
      customYaml,
      values: sample.value.values,
      segments: segmentsPayload,
      context: {},
    });
    if (requestId === semanticRequestId) {
      semanticLabelResults.value = response.results ?? [];
    }
  } catch (requestError) {
    if (requestId === semanticRequestId) {
      semanticLabelResults.value = [];
      semanticCustomError.value = {
        message:
          requestError instanceof Error
            ? requestError.message
            : "Failed to compute semantic labels.",
        kind: "schema",
      };
    }
  }
}

function handleSelectSemanticPack(packKey) {
  semanticActivePackKey.value = packKey;
  semanticCustomError.value = null;
  if (packKey === NONE_OPTION_KEY) {
    semanticActivePack.value = null;
    semanticLabelResults.value = [];
  } else if (packKey === CUSTOM_OPTION_KEY) {
    semanticActivePack.value = null;
    semanticLabelResults.value = [];
  } else {
    const matched = semanticPacks.value.find((pack) => pack.name === packKey) ?? null;
    semanticActivePack.value = matched;
    refreshSemanticLabels();
  }
  saveSemanticLayerSession({
    activePackKey: semanticActivePackKey.value,
    customYamlText: semanticCustomYamlText.value || null,
  });
}

async function handleUploadCustomYaml(yamlText) {
  semanticCustomYamlText.value = yamlText ?? "";
  semanticCustomError.value = null;
  if (!semanticCustomYamlText.value.trim()) {
    return;
  }
  try {
    const result = await validateSemanticPackYaml(semanticCustomYamlText.value);
    if (!result.ok) {
      semanticCustomError.value = result.error ?? { message: "Validation failed", kind: "schema" };
      semanticActivePack.value = null;
      semanticLabelResults.value = [];
      return;
    }
    semanticActivePack.value = result.pack ?? null;
    semanticActivePackKey.value = CUSTOM_OPTION_KEY;
    saveSemanticLayerSession({
      activePackKey: CUSTOM_OPTION_KEY,
      customYamlText: semanticCustomYamlText.value,
    });
    refreshSemanticLabels();
  } catch (requestError) {
    semanticCustomError.value = {
      message:
        requestError instanceof Error ? requestError.message : "Validation request failed.",
      kind: "schema",
    };
  }
}

function handleClearCustomPack() {
  semanticCustomYamlText.value = "";
  semanticActivePack.value = null;
  semanticLabelResults.value = [];
  semanticCustomError.value = null;
  saveSemanticLayerSession({ activePackKey: semanticActivePackKey.value, customYamlText: null });
}

watch(
  () => sample.value?.segments,
  (segments) => {
    selectedSegmentId.value = reconcileSelectedSegmentId(segments ?? [], selectedSegmentId.value);
    if (semanticActivePackKey.value !== NONE_OPTION_KEY) {
      refreshSemanticLabels();
    }
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

watch(seriesVersion, (version) => {
  // Each time a value-changing operation lands, re-score the gauges from
  // the backend. seriesVersion is bumped only at the two real mutation
  // sites (applyInvokeResponse, handleChipUndo), so this watcher fires
  // exactly when proximity / plausibility could change.
  if (version === 0) return;
  refreshPlausibilityGauges();
});

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
  loadSemanticPacks();
  const restored = loadSemanticLayerSession();
  if (restored?.activePackKey) {
    semanticActivePackKey.value = restored.activePackKey;
    if (restored.customYamlText) {
      semanticCustomYamlText.value = restored.customYamlText;
    }
  }
});

watch(
  () => semanticPacks.value,
  () => {
    if (
      semanticActivePackKey.value !== NONE_OPTION_KEY &&
      semanticActivePackKey.value !== CUSTOM_OPTION_KEY
    ) {
      const matched =
        semanticPacks.value.find((pack) => pack.name === semanticActivePackKey.value) ?? null;
      if (matched) {
        semanticActivePack.value = matched;
        refreshSemanticLabels();
      } else {
        semanticActivePackKey.value = NONE_OPTION_KEY;
      }
    } else if (semanticActivePackKey.value === CUSTOM_OPTION_KEY && semanticCustomYamlText.value) {
      handleUploadCustomYaml(semanticCustomYamlText.value);
    }
  },
);
</script>

<template>
  <div class="research-viewport zones-frame">
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

    <!-- Three-zone workspace: INPUT (left) | OUTPUT over EVIDENCE (right) -->
    <div class="workspace">
      <!-- ZONE 1 · INPUT — what I feed the model -->
      <section class="zone-input" aria-label="Input — what I feed the model">
        <div class="zlabel">
          <span class="zi" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.12 2.12 0 013 3L7 19l-4 1 1-4z" />
            </svg>
          </span>
          <span class="zt">Input</span>
          <span class="zsub">what I feed the model</span>
        </div>

        <div class="z1-main">
          <div class="z1-rail" aria-label="Editing controls">
            <SemanticLayerPanel
              :built-in-packs="semanticPacks"
              :active-pack-key="semanticActivePackKey"
              :active-pack="semanticActivePack"
              :label-results="semanticLabelResults"
              :custom-error="semanticCustomError"
              :custom-yaml-text="semanticCustomYamlText"
              :loading="semanticPacksLoading"
              @select-pack="handleSelectSemanticPack"
              @upload-custom-yaml="handleUploadCustomYaml"
              @clear-custom="handleClearCustomPack"
            />

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

            <CompensationModeSelector
              v-if="compensationSelectorVisible"
              :domain-hint="activeDomainHint"
              :op-category="selectedSegmentOpCategory"
              :model-value="selectedCompensationMode"
              :has-explicit-choice="compensationModeTouched"
              :disabled="pendingOpName !== null"
              @update:model-value="handleCompensationModeChange"
            />

            <OperationPalette
              :selected-segment-ids="tieredPaletteSelectedIds"
              :selected-shapes="tieredPaletteSelectedShapes"
              :pending-op="pendingOpName"
              @op-invoked="handleOpInvoked"
            />

            <div v-if="decompositionEditorOpen" class="decomposition-editor-panel">
              <button
                type="button"
                class="decomposition-editor-panel__close"
                aria-label="Close decomposition editor"
                @click="handleDecompositionEditorClose"
              >Close decomposition editor</button>
              <DecompositionEditor
                :blob="decompositionBlob"
                :segment-id="selectedSegmentId"
                @op-invoked="handleDecompositionEditorOp"
              />
            </div>

            <ModelComparisonPanel
              :state="comparisonState"
              @request-suggestion="handleRequestSuggestion"
              @accept-suggestion="handleAcceptSuggestion"
              @override-suggestion="handleOverrideSuggestion"
              @adapt-model="handleAdaptModel"
              @update-labeler="handleUpdateLabeler"
            />
          </div>

          <div class="z1-canvas" aria-label="Timeline and segments">
            <div class="chart-panel">
              <div class="chart-panel-header">
                <span class="section-label">
                  {{ sample?.datasetName ?? (loading ? "Loading…" : "No sample") }}
                  <span v-if="sample"> · Sample {{ sample.sampleId }}</span>
                </span>
                <span class="surface-tag">{{ sample?.seriesLength ?? "--" }} pts</span>
              </div>

              <TimelineViewer
                :sample="enrichedSample"
                :selected-segment-id="selectedSegmentId"
                :segment-uncertainty="uncertaintyPayload?.segmentUncertainty ?? []"
                :boundary-uncertainty="uncertaintyPayload?.boundaryUncertainty ?? []"
                :ghost-values="minFlipGhostValues"
                @select-segment="handleSelectSegment"
                @move-boundary="handleMoveBoundary"
              />

              <PredictedLabelChip
                @accept="handleChipAccept"
                @override="handleChipOverride"
                @undo="handleChipUndo"
              />

              <DonorPicker
                v-if="donorPickerOpen && selectedSegment && sample"
                :segment-values="sample.values.slice(selectedSegment.start, selectedSegment.end + 1)"
                :target-class="donorPickerTargetClass"
                :segment-id="selectedSegment.id"
                :dataset="sample.datasetName ?? null"
                @op-invoked="handleDonorAccepted"
                @close="handleDonorPickerClose"
              />

              <AlignWarpPanel
                v-if="alignWarpPanelOpen && sample"
                :segments="sample.segments ?? []"
                :selected-segment-ids="tieredPaletteSelectedIds"
                :initial-reference-segment-id="selectedSegmentId"
                :series-values="sample.values"
                @op-invoked="handleAlignApplied"
              />

              <GapFillPicker
                v-if="gapFillPickerOpen && selectedSegment"
                :segment-id="selectedSegment.id"
                :missingness-pct="selectedSegmentGapInfo?.missingnessPct ?? 0"
                @op-invoked="handleGapFillApplied"
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
                  @contextmenu="handleSegmentContextMenu($event, segment)"
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
          </div>
        </div>
      </section>

      <!-- ZONE 2 (OUTPUT) over ZONE 3 (EVIDENCE) -->
      <div class="zone-right">
        <!-- ZONE 2 · OUTPUT — what the model says -->
        <section class="zone-output" aria-label="Output — what the model says">
          <div class="zlabel">
            <span class="zi" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </span>
            <span class="zt">Output</span>
            <span class="zsub">what the model says</span>
          </div>
          <div class="zone-output-body">
            <OutputPanel
              :state="outputPanelState"
              :artifact-label="outputPanelArtifactLabel"
              @request-prediction="handleRequestPrediction"
              @rerun-prediction="handleRerunPrediction"
            >
              <template #probe>
                <MinFlipStrip
                  :result="minFlipResult"
                  :searching="probeFlags.minFlipSearching"
                  :error="minFlipError"
                  @apply="handleApplyMinFlip"
                  @clear="handleClearMinFlip"
                />
              </template>
            </OutputPanel>

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
          </div>
        </section>

        <!-- ZONE 3 · EVIDENCE — can I trust it -->
        <section class="zone-evidence" aria-label="Evidence — can I trust it">
          <div class="zlabel">
            <span class="zi" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="7" />
                <path d="M21 21l-4.3-4.3" />
              </svg>
            </span>
            <span class="zt">Evidence</span>
            <span class="zsub">can I trust it</span>
          </div>
          <div class="ev-body">
            <EvidenceZone
              :gauges-state="plausibilityGaugesState"
              :warning="warningDisplay"
              :constraint-law="lastConstraintLaw"
              :constraint-result="operationConstraintResult"
              :audit-events="auditEvents"
              :session-state="sessionPanelState"
              :probe-flags="probeFlags"
              @toggle-saliency="handleToggleSaliency"
              @toggle-delta-sources="handleToggleDeltaSources"
              @probe-min-flip="handleProbeMinFlip"
            >
              <template #fidelity>
                <FidelityStrip
                  :state="fidelityStripState"
                  :raw-values="sample?.values ?? null"
                />
              </template>
            </EvidenceZone>
          </div>
        </section>
      </div>
    </div>

    <GuardrailsSidebar
      :event-bus="validationBus"
      initial-dock="bottom"
      :initial-collapsed="true"
    />

    <ScopeAttributeEditor
      v-if="scopeEditorOpen && scopeEditorSegment"
      :segment="scopeEditorSegment"
      :series-length="sample?.values?.length ?? null"
      :project-domain-hint="activeDomainHint"
      :open="scopeEditorOpen"
      @scope-updated="handleScopeUpdated"
      @close="handleScopeEditorClose"
    />
    <p
      v-if="scopeEditorOpen && scopeEditorError"
      class="scope-editor-inline-error"
      role="alert"
    >{{ scopeEditorError }}</p>

    <ul
      v-if="segmentContextMenu"
      class="segment-context-menu"
      role="menu"
      :style="{ top: `${segmentContextMenu.y}px`, left: `${segmentContextMenu.x}px` }"
      @click.stop
    >
      <li role="none">
        <button
          type="button"
          role="menuitem"
          class="segment-context-menu__item"
          @click="handleContextMenuEditScope"
        >Edit scope…</button>
      </li>
    </ul>
  </div>
</template>
