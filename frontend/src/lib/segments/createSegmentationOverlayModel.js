export const SEGMENT_LABEL_STYLES = [
  { label: "event" },
  { label: "trend" },
  { label: "anomaly" },
  { label: "other" },
];

function toPercent(value) {
  return `${value.toFixed(2)}%`;
}

export function createSegmentationOverlayModel(segments, seriesLength) {
  if (!Array.isArray(segments) || segments.length === 0 || !seriesLength) {
    return {
      spans: [],
      boundaries: [],
    };
  }

  const denominator = seriesLength;
  const spans = segments.map((segment) => {
    const spanStart = (segment.start / denominator) * 100;
    const spanWidth = ((segment.end - segment.start + 1) / denominator) * 100;

    return {
      ...segment,
      left: toPercent(spanStart),
      width: toPercent(spanWidth),
    };
  });

  const boundaries = segments.slice(0, -1).map((segment) => ({
    id: `${segment.id}-boundary`,
    left: toPercent((((segment.end + 1) / denominator) * 100)),
  }));

  return {
    spans,
    boundaries,
  };
}
