export function reconcileSelectedSegmentId(segments, selectedSegmentId) {
  if (!Array.isArray(segments) || segments.length === 0) {
    return null;
  }

  if (selectedSegmentId && segments.some((segment) => segment.id === selectedSegmentId)) {
    return selectedSegmentId;
  }

  return segments[0].id;
}

export function getSelectedSegment(segments, selectedSegmentId) {
  if (!Array.isArray(segments) || !selectedSegmentId) {
    return null;
  }

  return segments.find((segment) => segment.id === selectedSegmentId) ?? null;
}
