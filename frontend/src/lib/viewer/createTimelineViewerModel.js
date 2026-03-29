function formatRange(start, end) {
  return `${start}-${end}`;
}

function toPercent(value) {
  return `${value.toFixed(2)}%`;
}

function createOverviewWindow(segment, seriesLength) {
  if (!segment || !Number.isFinite(seriesLength) || seriesLength <= 0) {
    return {
      left: "0.00%",
      width: "100.00%",
    };
  }

  const segmentLength = segment.end - segment.start + 1;
  const contextPadding = Math.max(segmentLength, Math.round(seriesLength * 0.08));
  const windowStart = Math.max(0, segment.start - contextPadding);
  const windowEnd = Math.min(seriesLength - 1, segment.end + contextPadding);

  return {
    left: toPercent((windowStart / seriesLength) * 100),
    width: toPercent((((windowEnd - windowStart + 1) / seriesLength) * 100)),
  };
}

export function createTimelineViewerModel(sample, selectedSegmentId = null) {
  const values = Array.isArray(sample?.values) ? sample.values : [];
  const segments = Array.isArray(sample?.segments) ? sample.segments : [];
  const seriesLength = Number(sample?.seriesLength ?? values.length ?? 0);
  const selectedSegment = segments.find((segment) => segment.id === selectedSegmentId) ?? null;

  if (!sample || !values.length || !seriesLength) {
    return {
      title: "Time-series timeline",
      pointCountLabel: "-- points",
      segmentCountLabel: "0 segments",
      overviewLabel: "Awaiting sample",
      selectedSummary: "No segment selected",
      selectedRangeLabel: "--",
      overviewWindow: {
        left: "0.00%",
        width: "100.00%",
      },
      minimapSpans: [],
    };
  }

  return {
    title: `${sample.datasetName} sample ${sample.sampleId}`,
    pointCountLabel: `${seriesLength} points`,
    segmentCountLabel: `${segments.length} segments`,
    overviewLabel: seriesLength > 240 ? "Overview enabled for longer series" : "Single-view timeline",
    selectedSummary: selectedSegment ? `Selected ${selectedSegment.label}` : "No segment selected",
    selectedRangeLabel: selectedSegment ? formatRange(selectedSegment.start, selectedSegment.end) : "--",
    overviewWindow: createOverviewWindow(selectedSegment, seriesLength),
    minimapSpans: segments.map((segment) => ({
      id: segment.id,
      label: segment.label,
      isSelected: segment.id === selectedSegmentId,
      left: toPercent((segment.start / seriesLength) * 100),
      width: toPercent((((segment.end - segment.start + 1) / seriesLength) * 100)),
      rangeLabel: formatRange(segment.start, segment.end),
    })),
  };
}
