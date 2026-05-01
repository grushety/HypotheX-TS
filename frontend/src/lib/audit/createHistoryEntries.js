function formatActionLabel(event) {
  const actionLabels = {
    "move-boundary": "Boundary edit",
    "update-label": "Label edit",
    split: "Split operation",
    merge: "Merge operation",
    reclassify: "Reclassify operation",
    "accept-suggestion": "Suggestion accepted",
    "override-suggestion": "Suggestion overridden",
  };

  return actionLabels[event.actionType] ?? "Action";
}

function formatStatusLabel(event) {
  if (event.actionStatus === "rejected") {
    return "Rejected";
  }

  if (event.constraintStatus === "WARN") {
    return "Warned";
  }

  return "Applied";
}

function formatSummary(event) {
  if (event.message) {
    return event.message;
  }

  if (event.kind === "suggestion" && event.decision) {
    return `Model suggestion ${event.decision}.`;
  }

  return `${formatActionLabel(event)} ${event.actionStatus}.`;
}

function formatTimestampLabel(timestamp) {
  if (!timestamp) {
    return "Pending";
  }

  return timestamp.replace("T", " ").replace(".000Z", "Z");
}

export function createHistoryEntries(events = []) {
  return [...events]
    .sort((left, right) => (right.sequence ?? 0) - (left.sequence ?? 0))
    .map((event) => ({
      id: `${event.sequence ?? "pending"}-${event.kind}-${event.actionType}`,
      title: formatActionLabel(event),
      statusLabel: formatStatusLabel(event),
      summary: formatSummary(event),
      sequence: event.sequence ?? null,
      timestamp: event.timestamp ?? null,
      timestampLabel: formatTimestampLabel(event.timestamp ?? null),
      warningCount: event.warningCount ?? 0,
      affectedSegmentIds: event.affectedSegmentIds ?? [],
      constraintResidual: event.constraintResidual ?? null,
      plausibilityRange: event.plausibilityRange ?? null,
      plausibilityManifold: event.plausibilityManifold ?? null,
    }));
}
