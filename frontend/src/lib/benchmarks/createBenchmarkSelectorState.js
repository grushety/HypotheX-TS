export function createBenchmarkSelectorState({
  datasets,
  artifacts,
  selectedDatasetName,
  selectedArtifactId,
  selectedSplit,
  sampleIndex,
  loading,
  error,
  compatibility,
  compatibilityLoading,
  compatibilityError,
}) {
  const normalizedDatasets = Array.isArray(datasets) ? datasets : [];
  const normalizedArtifacts = Array.isArray(artifacts) ? artifacts : [];
  const selectedDataset =
    normalizedDatasets.find((dataset) => dataset.name === selectedDatasetName) ?? null;
  const selectedArtifact =
    normalizedArtifacts.find((artifact) => artifact.artifact_id === selectedArtifactId) ?? null;

  const datasetOptions = normalizedDatasets.map((dataset) => ({
    value: dataset.name,
    label: dataset.name,
  }));
  const modelOptions = normalizedArtifacts.map((artifact) => ({
    value: artifact.artifact_id,
    label: `${artifact.display_name} · ${artifact.dataset}`,
    disabled: Boolean(selectedDatasetName) && artifact.dataset !== selectedDatasetName,
  }));

  const splitShape = selectedSplit === "test" ? selectedDataset?.test_shape : selectedDataset?.train_shape;
  const sampleCount = Number(splitShape?.[0] ?? 0);
  const maxSampleIndex = sampleCount > 0 ? sampleCount - 1 : 0;

  let compatibilityTone = "neutral";
  let compatibilityMessage = "Select a dataset and model to check compatibility.";
  if (compatibilityLoading) {
    compatibilityTone = "loading";
    compatibilityMessage = "Checking compatibility...";
  } else if (compatibilityError) {
    compatibilityTone = "error";
    compatibilityMessage = compatibilityError;
  } else if (compatibility) {
    compatibilityTone = compatibility.is_compatible ? "ok" : "warn";
    compatibilityMessage = compatibility.is_compatible
      ? "Selected dataset and model are compatible."
      : compatibility.messages.join(" ");
  }

  return {
    loading: Boolean(loading),
    error: error || "",
    datasetOptions,
    modelOptions,
    selectedDataset,
    selectedArtifact,
    selectedSplit,
    sampleIndex,
    sampleCount,
    maxSampleIndex,
    compatibilityTone,
    compatibilityMessage,
  };
}
