import { AVAILABLE_SEGMENT_LABELS } from "../segments/updateSegmentLabel.js";
import { validateEditableSegments } from "../segments/validateEditableSegments.js";

export const SEMANTIC_OPERATION_TYPES = ["split", "merge", "reclassify"];

function createFailure(type, code, message, request) {
  return {
    ok: false,
    type,
    code,
    message,
    request,
    event: {
      type,
      status: "rejected",
      code,
      request,
    },
  };
}

export function createSemanticOperationSuccess(type, segments, request, options = {}) {
  return {
    ok: true,
    type,
    segments,
    request,
    affectedSegmentIds: options.affectedSegmentIds ?? [],
    event: {
      type,
      status: "applied",
      affectedSegmentIds: options.affectedSegmentIds ?? [],
      request,
    },
  };
}

export function validateSemanticOperationRequest(segments, request) {
  const segmentValidation = validateEditableSegments(segments);

  if (!segmentValidation.ok) {
    return segmentValidation;
  }

  if (!request || typeof request !== "object") {
    return createFailure("unknown", "INVALID_REQUEST", "Operation request must be an object.", request);
  }

  if (!SEMANTIC_OPERATION_TYPES.includes(request.type)) {
    return createFailure(
      request.type ?? "unknown",
      "UNSUPPORTED_OPERATION",
      "Operation type must be split, merge, or reclassify.",
      request,
    );
  }

  if (request.type === "split") {
    if (!request.segmentId || !Number.isInteger(request.splitIndex)) {
      return createFailure(
        request.type,
        "INVALID_REQUEST",
        "Split operations require a segmentId and integer splitIndex.",
        request,
      );
    }
  }

  if (request.type === "merge") {
    if (!request.leftSegmentId || !request.rightSegmentId) {
      return createFailure(
        request.type,
        "INVALID_REQUEST",
        "Merge operations require leftSegmentId and rightSegmentId.",
        request,
      );
    }
  }

  if (request.type === "reclassify") {
    if (!request.segmentId || !AVAILABLE_SEGMENT_LABELS.includes(request.nextLabel)) {
      return createFailure(
        request.type,
        "INVALID_REQUEST",
        "Reclassify operations require a segmentId and supported nextLabel.",
        request,
      );
    }
  }

  return { ok: true };
}

export function requestSplitOperation(segments, request) {
  const validation = validateSemanticOperationRequest(segments, { ...request, type: "split" });

  if (!validation.ok) {
    return validation;
  }

  return createFailure(
    "split",
    "NOT_IMPLEMENTED",
    "Split operation behavior will be implemented in HTS-010.",
    { ...request, type: "split" },
  );
}

export function requestMergeOperation(segments, request) {
  const validation = validateSemanticOperationRequest(segments, { ...request, type: "merge" });

  if (!validation.ok) {
    return validation;
  }

  return createFailure(
    "merge",
    "NOT_IMPLEMENTED",
    "Merge operation behavior will be implemented in HTS-011.",
    { ...request, type: "merge" },
  );
}

export function requestReclassifyOperation(segments, request) {
  const validation = validateSemanticOperationRequest(segments, { ...request, type: "reclassify" });

  if (!validation.ok) {
    return validation;
  }

  return createFailure(
    "reclassify",
    "NOT_IMPLEMENTED",
    "Reclassify operation behavior will be implemented in HTS-012.",
    { ...request, type: "reclassify" },
  );
}

export function applySemanticOperation(segments, request) {
  switch (request?.type) {
    case "split":
      return requestSplitOperation(segments, request);
    case "merge":
      return requestMergeOperation(segments, request);
    case "reclassify":
      return requestReclassifyOperation(segments, request);
    default:
      return validateSemanticOperationRequest(segments, request);
  }
}
