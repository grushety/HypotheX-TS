function clampSampleIndex(sampleIndex, selectedDataset, selectedSplit) {
  if (!selectedDataset) {
    return 0;
  }

  const splitShape = selectedSplit === "test" ? selectedDataset.test_shape : selectedDataset.train_shape;
  const maxIndex = Math.max(0, Number(splitShape?.[0] ?? 1) - 1);
  const numericValue = Number.isFinite(sampleIndex) ? sampleIndex : 0;
  return Math.min(Math.max(0, Math.trunc(numericValue)), maxIndex);
}

export function reconcileBenchmarkSelection({
  datasets,
  artifacts,
  selectedDatasetName,
  selectedArtifactId,
  selectedSplit,
  sampleIndex,
}) {
  const normalizedDatasets = Array.isArray(datasets) ? datasets : [];
  const normalizedArtifacts = Array.isArray(artifacts) ? artifacts : [];

  const datasetNames = normalizedDatasets.map((dataset) => dataset.name);
  const nextDatasetName = datasetNames.includes(selectedDatasetName)
    ? selectedDatasetName
    : (datasetNames[0] ?? "");
  const selectedDataset =
    normalizedDatasets.find((dataset) => dataset.name === nextDatasetName) ?? null;

  const nextSplit = selectedSplit === "test" ? "test" : "train";
  const compatibleArtifacts = normalizedArtifacts.filter((artifact) => artifact.dataset === nextDatasetName);
  const compatibleArtifactIds = compatibleArtifacts.map((artifact) => artifact.artifact_id);
  const nextArtifactId = compatibleArtifactIds.includes(selectedArtifactId)
    ? selectedArtifactId
    : (compatibleArtifactIds[0] ?? normalizedArtifacts[0]?.artifact_id ?? "");

  return {
    selectedDatasetName: nextDatasetName,
    selectedArtifactId: nextArtifactId,
    selectedSplit: nextSplit,
    sampleIndex: clampSampleIndex(sampleIndex, selectedDataset, nextSplit),
  };
}
