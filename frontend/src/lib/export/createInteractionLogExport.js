import { AUDIT_EVENT_SCHEMA_VERSION } from "../audit/auditEvents.js";

function padNumber(value) {
  return String(value).padStart(2, "0");
}

export function createInteractionLogFilename(sampleId, timestamp = new Date()) {
  const year = timestamp.getUTCFullYear();
  const month = padNumber(timestamp.getUTCMonth() + 1);
  const day = padNumber(timestamp.getUTCDate());
  const hours = padNumber(timestamp.getUTCHours());
  const minutes = padNumber(timestamp.getUTCMinutes());
  const seconds = padNumber(timestamp.getUTCSeconds());
  const safeSampleId = (sampleId ?? "sample").replace(/[^a-zA-Z0-9_-]+/g, "-");

  return `session-log-${safeSampleId}-${year}${month}${day}T${hours}${minutes}${seconds}Z.json`;
}

function mapAuditEventToSessionEvent(event, sessionId) {
  return {
    eventId: `${sessionId}-event-${event.sequence ?? "pending"}`,
    timestamp: event.timestamp ?? null,
    eventType: getEventType(event),
    suggestion:
      event.kind === "suggestion"
        ? {
            suggestionId: event.suggestionId ?? null,
            decision: event.decision ?? null,
            targetSegmentIds: event.affectedSegmentIds ?? [],
            source: "model",
          }
        : undefined,
    metadata: {
      kind: event.kind ?? null,
      actionType: event.actionType ?? null,
      actionStatus: event.actionStatus ?? null,
      constraintStatus: event.constraintStatus ?? null,
      warningCount: event.warningCount ?? 0,
      affectedSegmentIds: event.affectedSegmentIds ?? [],
      rejectionCode: event.rejectionCode ?? null,
      message: event.message ?? "",
      request: event.request ?? null,
      selectedSegmentId: event.selectedSegmentId ?? null,
      sampleId: event.sampleId ?? null,
    },
  };
}

function getEventType(event) {
  if (event.kind === "suggestion") {
    return event.decision === "accepted" ? "suggestion_accepted" : "suggestion_overridden";
  }

  return event.actionStatus === "rejected" ? "operation_rejected" : "operation_applied";
}

export function createInteractionLogExport(events, context = {}, timestamp = new Date()) {
  const sessionId = context.sessionId ?? `session-${context.sampleId ?? "sample"}`;
  const startedAt = context.startedAt ?? events[0]?.timestamp ?? timestamp.toISOString();
  const endedAt = context.endedAt ?? events.at(-1)?.timestamp ?? timestamp.toISOString();
  const payload = {
    schemaVersion: "1.0.0",
    sessionId,
    seriesId: context.seriesId ?? context.sampleId ?? "sample",
    segmentationId: context.segmentationId ?? `segmentation-${context.sampleId ?? "sample"}`,
    startedAt,
    endedAt,
    datasetName: context.datasetName ?? null,
    eventCount: events.length,
    exportedAt: timestamp.toISOString(),
    events: events.map((event) => mapAuditEventToSessionEvent(event, sessionId)),
  };

  return {
    filename: createInteractionLogFilename(context.sampleId, timestamp),
    mimeType: "application/json",
    content: JSON.stringify(payload, null, 2),
    payload,
  };
}

export function downloadInteractionLogExport(exportArtifact) {
  const blob = new Blob([exportArtifact.content], { type: exportArtifact.mimeType });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = objectUrl;
  link.download = exportArtifact.filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
