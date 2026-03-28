function createDefaultSegments(seriesLength) {
  if (!Number.isFinite(seriesLength) || seriesLength <= 0) {
    return [];
  }

  const labels = ["event", "trend", "anomaly", "other"];
  const segmentCount = Math.min(labels.length, seriesLength);
  const segments = [];
  let start = 0;

  for (let index = 0; index < segmentCount; index += 1) {
    const remainingLength = seriesLength - start;
    const remainingSegments = segmentCount - index;
    const baseSize = Math.max(1, Math.floor(remainingLength / remainingSegments));
    const end = index === segmentCount - 1 ? seriesLength - 1 : start + baseSize - 1;
    segments.push({
      id: `seg-${String(index + 1).padStart(3, "0")}`,
      start,
      end,
      label: labels[index],
    });
    start = end + 1;
  }

  return segments;
}

function getPrimaryChannelValues(values) {
  if (!Array.isArray(values) || !values.length) {
    return [];
  }

  if (Array.isArray(values[0])) {
    return values[0].map((value) => Number(value));
  }

  return values.map((value) => Number(value));
}

export function createViewerSampleFromApi(payload) {
  const values = Array.isArray(payload.values) ? payload.values : [];
  const channelValues = Array.isArray(values[0]) ? values.map((channel) => channel.map(Number)) : [values.map(Number)];
  const primaryValues = getPrimaryChannelValues(values);
  const seriesLength = Number(payload.series_length ?? primaryValues.length);
  const sampleIndex = Number(payload.sample_index ?? 0);

  return {
    datasetId: payload.dataset_id ?? payload.dataset_name ?? "unknown",
    datasetName: payload.dataset_name ?? payload.dataset_id ?? "Unknown dataset",
    sampleId: `${payload.split ?? "train"}-${sampleIndex}`,
    taskType: payload.task_type ?? "classification",
    channelCount: Number(payload.channel_count ?? channelValues.length),
    seriesLength,
    label: payload.label ?? "--",
    sourceSplit: payload.split ?? "train",
    sourceSampleIndex: sampleIndex,
    seriesType: payload.series_type ?? (channelValues.length > 1 ? "multivariate" : "univariate"),
    channelValues,
    values: primaryValues,
    segments: createDefaultSegments(seriesLength),
  };
}
