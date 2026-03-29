function createSessionId(sampleId) {
  return `session-${sampleId ?? "unloaded"}`;
}

function createSegmentationId(sampleId) {
  return `segmentation-${sampleId ?? "unloaded"}`;
}

export function createSessionPanelState(events = [], sample = null) {
  const sortedEvents = [...events].sort((left, right) => (left.sequence ?? 0) - (right.sequence ?? 0));
  const firstTimestamp = sortedEvents[0]?.timestamp ?? null;
  const lastTimestamp = sortedEvents.at(-1)?.timestamp ?? null;
  const sampleId = sample?.sampleId ?? null;

  return {
    sessionId: createSessionId(sampleId),
    seriesId: sampleId ?? "unloaded-series",
    segmentationId: createSegmentationId(sampleId),
    startedAt: firstTimestamp,
    endedAt: lastTimestamp,
    eventCount: events.length,
    datasetName: sample?.datasetName ?? null,
    sampleId,
  };
}
