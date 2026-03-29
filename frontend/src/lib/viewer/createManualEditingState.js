import { AVAILABLE_SEGMENT_LABELS } from "../segments/updateSegmentLabel.js";

function createDisabledState() {
  return {
    hasSelection: false,
    selectedSegmentId: null,
    splitMin: null,
    splitMax: null,
    suggestedSplitIndex: "",
    canSplit: false,
    splitHint: "Select a segment to enable manual editing controls.",
    leftMergeTarget: null,
    rightMergeTarget: null,
    canMergeLeft: false,
    canMergeRight: false,
    relabelOptions: AVAILABLE_SEGMENT_LABELS,
  };
}

export function createManualEditingState(segments, selectedSegment) {
  if (!Array.isArray(segments) || !selectedSegment) {
    return createDisabledState();
  }

  const selectedIndex = segments.findIndex((segment) => segment.id === selectedSegment.id);

  if (selectedIndex === -1) {
    return createDisabledState();
  }

  const leftMergeTarget = selectedIndex > 0 ? segments[selectedIndex - 1] : null;
  const rightMergeTarget = selectedIndex < segments.length - 1 ? segments[selectedIndex + 1] : null;
  const splitMin = selectedSegment.start + 1;
  const splitMax = selectedSegment.end;
  const canSplit = splitMax >= splitMin;
  const suggestedSplitIndex = canSplit
    ? String(Math.min(splitMax, Math.max(splitMin, Math.floor((selectedSegment.start + selectedSegment.end + 1) / 2))))
    : "";

  return {
    hasSelection: true,
    selectedSegmentId: selectedSegment.id,
    splitMin,
    splitMax,
    suggestedSplitIndex,
    canSplit,
    splitHint: canSplit
      ? `Valid split range: ${splitMin}-${splitMax}.`
      : "This segment is too short to split.",
    leftMergeTarget,
    rightMergeTarget,
    canMergeLeft: Boolean(leftMergeTarget),
    canMergeRight: Boolean(rightMergeTarget),
    relabelOptions: AVAILABLE_SEGMENT_LABELS,
  };
}
