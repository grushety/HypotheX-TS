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

  return `interaction-log-${safeSampleId}-${year}${month}${day}T${hours}${minutes}${seconds}Z.json`;
}

export function createInteractionLogExport(events, context = {}, timestamp = new Date()) {
  const payload = {
    schemaVersion: AUDIT_EVENT_SCHEMA_VERSION,
    exportedAt: timestamp.toISOString(),
    sampleId: context.sampleId ?? null,
    datasetName: context.datasetName ?? null,
    eventCount: events.length,
    events,
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
