import { createManualEditingState } from "../viewer/createManualEditingState.js";

const SUPPORTED_OPERATION_KEYS = ["split", "merge"];

function formatOperationLabel(operation) {
  return operation
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function createOperationPaletteState({ segments, selectedSegment, operationRegistry, feedback = "" }) {
  const editingState = createManualEditingState(segments, selectedSegment);
  const operationsByChunk = operationRegistry?.operationsByChunk ?? {};
  const legalOperations = selectedSegment ? operationsByChunk[selectedSegment.label] ?? [] : [];
  const supportedOperations = legalOperations.filter((operation) => SUPPORTED_OPERATION_KEYS.includes(operation));
  const futureOperations = legalOperations.filter((operation) => !SUPPORTED_OPERATION_KEYS.includes(operation));

  return {
    selectedSegmentId: selectedSegment?.id ?? null,
    feedback,
    helperText: !selectedSegment
      ? "Select a segment to inspect legal semantic operations."
      : legalOperations.length
        ? `${selectedSegment.label} allows ${legalOperations.length} semantic operation${legalOperations.length === 1 ? "" : "s"} in the active ontology.`
        : `No legal semantic operations are available for '${selectedSegment.label}' in the current registry.`,
    legalOperations: legalOperations.map((operation) => ({
      key: operation,
      label: formatOperationLabel(operation),
      supported: SUPPORTED_OPERATION_KEYS.includes(operation),
    })),
    supportedOperations,
    futureOperations,
    showSplit: supportedOperations.includes("split"),
    showMerge: supportedOperations.includes("merge"),
    mergeLeftLabel: editingState.leftMergeTarget
      ? `Merge ${editingState.leftMergeTarget.id}`
      : "Merge Left",
    mergeRightLabel: editingState.rightMergeTarget
      ? `Merge ${editingState.rightMergeTarget.id}`
      : "Merge Right",
    canSplit: editingState.canSplit && supportedOperations.includes("split"),
    splitMin: editingState.splitMin,
    splitMax: editingState.splitMax,
    suggestedSplitIndex: editingState.suggestedSplitIndex,
    canMergeLeft: editingState.canMergeLeft && supportedOperations.includes("merge"),
    canMergeRight: editingState.canMergeRight && supportedOperations.includes("merge"),
  };
}
