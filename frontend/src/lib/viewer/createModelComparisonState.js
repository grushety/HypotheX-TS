function formatRange(segment) {
  return `${segment.start}-${segment.end}`;
}

function createComparisonRows(currentSegments, proposalSegments) {
  const maxLength = Math.max(currentSegments.length, proposalSegments.length);
  const rows = [];

  for (let index = 0; index < maxLength; index += 1) {
    const currentSegment = currentSegments[index] ?? null;
    const proposalSegment = proposalSegments[index] ?? null;
    const boundaryChanged =
      Boolean(currentSegment && proposalSegment) &&
      (currentSegment.start !== proposalSegment.start || currentSegment.end !== proposalSegment.end);
    const labelChanged =
      Boolean(currentSegment && proposalSegment) && currentSegment.label !== proposalSegment.label;

    rows.push({
      id: `row-${index}`,
      currentSegment,
      proposalSegment,
      boundaryChanged,
      labelChanged,
      hasDisagreement: boundaryChanged || labelChanged || !currentSegment || !proposalSegment,
      currentRange: currentSegment ? formatRange(currentSegment) : "--",
      proposalRange: proposalSegment ? formatRange(proposalSegment) : "--",
    });
  }

  return rows;
}

export function createModelComparisonState({
  currentSegments,
  proposalSegments,
  selectedArtifact,
  suggestionStatus = "idle",
  suggestionLoading = false,
  suggestionError = "",
  auditEvents = [],
  adaptLoading = false,
  adaptError = "",
  adaptVersionId = null,
  selectedLabeler = "prototype",
  suggestionLabeler = null,
}) {
  const safeCurrentSegments = Array.isArray(currentSegments) ? currentSegments : [];
  const safeProposalSegments = Array.isArray(proposalSegments) ? proposalSegments : [];
  const rows = createComparisonRows(safeCurrentSegments, safeProposalSegments);
  const disagreementCount = rows.filter((row) => row.hasDisagreement).length;
  const hasProposal = safeProposalSegments.length > 0;
  const editOpCount = Array.isArray(auditEvents)
    ? auditEvents.filter((e) => e.kind === "edit" || e.kind === "operation").length
    : 0;

  return {
    heading: selectedArtifact?.display_name
      ? `${selectedArtifact.display_name} comparison`
      : "Model comparison",
    artifactLabel: selectedArtifact?.artifact_id ?? "No model selected",
    rows,
    disagreementCount,
    hasProposal,
    suggestionStatus,
    suggestionLoading,
    suggestionError,
    canRequestSuggestion: Boolean(selectedArtifact) && !suggestionLoading,
    canAcceptSuggestion: hasProposal && suggestionStatus === "pending" && !suggestionLoading,
    canOverrideSuggestion: hasProposal && suggestionStatus === "pending" && !suggestionLoading,
    canAdaptModel: editOpCount >= 3 && !adaptLoading,
    adaptLoading,
    adaptError,
    adaptVersionId,
    selectedLabeler,
    suggestionLabeler,
    message: suggestionError
      ? suggestionError
      : !hasProposal
        ? "Load a model suggestion to compare it with the current segmentation."
        : disagreementCount
          ? `${disagreementCount} disagreement row${disagreementCount === 1 ? "" : "s"} highlighted against the loaded proposal baseline.`
          : "Current segmentation matches the loaded proposal baseline.",
  };
}
