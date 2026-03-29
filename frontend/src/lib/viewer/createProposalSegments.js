function cloneSegment(segment) {
  return {
    id: segment.id,
    start: segment.start,
    end: segment.end,
    label: segment.label,
  };
}

export function createProposalSegments(segments) {
  if (!Array.isArray(segments)) {
    return [];
  }

  return segments.map(cloneSegment);
}
