const LABEL_MAP = {
  trend: "trend",
  plateau: "other",
  spike: "anomaly",
  event: "event",
  transition: "other",
  periodic: "other",
};

function mapLabel(label) {
  return LABEL_MAP[label] ?? "other";
}

export function createProposalSegments(proposalPayload) {
  const segments = Array.isArray(proposalPayload?.provisionalSegments)
    ? proposalPayload.provisionalSegments
    : Array.isArray(proposalPayload)
      ? proposalPayload
      : [];

  return segments.map((segment, index) => ({
    id: segment.segmentId ?? segment.id ?? `proposal-${index + 1}`,
    start: Number(segment.startIndex ?? segment.start ?? 0),
    end: Number(segment.endIndex ?? segment.end ?? 0),
    label: mapLabel(segment.label),
    sourceLabel: segment.label ?? null,
    confidence: typeof segment.confidence === "number" ? Number(segment.confidence) : null,
    labelScores:
      segment.labelScores && typeof segment.labelScores === "object"
        ? Object.fromEntries(
            Object.entries(segment.labelScores).map(([label, probability]) => [
              label,
              Number(probability),
            ]),
          )
        : null,
  }));
}
