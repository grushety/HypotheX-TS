export const AUDIT_EVENT_SCHEMA_VERSION = 1;

function summarizeWarnings(warnings = []) {
  return warnings.map((warning) => ({
    code: warning.code,
    actionType: warning.actionType ?? null,
    segmentIds: warning.segmentIds ?? [],
  }));
}

function createAuditEvent(kind, actionType, request, options = {}) {
  return {
    schemaVersion: AUDIT_EVENT_SCHEMA_VERSION,
    kind,
    actionType,
    actionStatus: options.actionStatus,
    constraintStatus: options.constraintStatus ?? null,
    warningCount: options.warnings?.length ?? 0,
    warnings: summarizeWarnings(options.warnings),
    affectedSegmentIds: options.affectedSegmentIds ?? [],
    rejectionCode: options.rejectionCode ?? null,
    message: options.message ?? "",
    sampleId: options.sampleId ?? null,
    selectedSegmentId: options.selectedSegmentId ?? null,
    request,
    timestamp: options.timestamp ?? null,
    sequence: options.sequence ?? null,
  };
}

export function createEditAuditEvent(request, result, context = {}) {
  if (result.ok) {
    const affectedSegmentIds =
      result.editResult.updatedSegmentIds ??
      (result.editResult.updatedSegmentId ? [result.editResult.updatedSegmentId] : []);

    return createAuditEvent("edit", request.type, request, {
      actionStatus: "applied",
      constraintStatus: result.constraintStatus,
      warnings: result.warnings,
      affectedSegmentIds,
      message: result.message,
      sampleId: context.sampleId ?? null,
      selectedSegmentId: context.selectedSegmentId ?? null,
    });
  }

  return createAuditEvent("edit", request.type, request, {
    actionStatus: "rejected",
    rejectionCode: result.editResult?.code ?? null,
    message: result.message,
    sampleId: context.sampleId ?? null,
    selectedSegmentId: context.selectedSegmentId ?? null,
  });
}

export function createOperationAuditEvent(request, result, context = {}) {
  if (result.ok) {
    return createAuditEvent("operation", request.type, request, {
      actionStatus: "applied",
      constraintStatus: result.constraintStatus,
      warnings: result.warnings,
      affectedSegmentIds: result.operationResult?.affectedSegmentIds ?? [],
      message: result.message,
      sampleId: context.sampleId ?? null,
      selectedSegmentId: result.selectedSegmentId ?? context.selectedSegmentId ?? null,
    });
  }

  return createAuditEvent("operation", request.type, request, {
    actionStatus: "rejected",
    rejectionCode: result.operationResult?.code ?? null,
    message: result.message,
    sampleId: context.sampleId ?? null,
    selectedSegmentId: context.selectedSegmentId ?? null,
  });
}

export function appendAuditEvent(events, event, options = {}) {
  const sequence = options.sequence ?? events.length + 1;
  const timestamp = options.timestamp ?? new Date().toISOString();

  return [
    ...events,
    {
      ...event,
      sequence,
      timestamp,
    },
  ];
}
