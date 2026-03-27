import { AVAILABLE_SEGMENT_LABELS } from "../segments/updateSegmentLabel.js";
import { validateEditableSegments } from "../segments/validateEditableSegments.js";

export const SEMANTIC_OPERATION_TYPES = ["split", "merge", "reclassify"];
const DEFAULT_MIN_SEGMENT_LENGTH = 1;

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

  const operationRequest = { ...request, type: "split" };
  const segmentIndex = segments.findIndex((segment) => segment.id === operationRequest.segmentId);

  if (segmentIndex === -1) {
    return createFailure(
      "split",
      "SEGMENT_NOT_FOUND",
      "Split target segment was not found.",
      operationRequest,
    );
  }

  const targetSegment = segments[segmentIndex];
  const minSegmentLength = operationRequest.minSegmentLength ?? DEFAULT_MIN_SEGMENT_LENGTH;
  const minimumSplitIndex = targetSegment.start + minSegmentLength;
  const maximumSplitIndex = targetSegment.end - minSegmentLength + 1;

  if (
    operationRequest.splitIndex < minimumSplitIndex ||
    operationRequest.splitIndex > maximumSplitIndex
  ) {
    return createFailure(
      "split",
      "INVALID_SPLIT_INDEX",
      "Split index must leave at least one valid point on both sides of the segment.",
      operationRequest,
    );
  }

  const leftSegment = {
    ...targetSegment,
    id: `${targetSegment.id}-a`,
    end: operationRequest.splitIndex - 1,
  };
  const rightSegment = {
    ...targetSegment,
    id: `${targetSegment.id}-b`,
    start: operationRequest.splitIndex,
  };

  const updatedSegments = [
    ...segments.slice(0, segmentIndex),
    leftSegment,
    rightSegment,
    ...segments.slice(segmentIndex + 1),
  ];
  const updatedValidation = validateEditableSegments(updatedSegments);

  if (!updatedValidation.ok) {
    return createFailure("split", updatedValidation.code, updatedValidation.message, operationRequest);
  }

  return createSemanticOperationSuccess("split", updatedSegments, operationRequest, {
    affectedSegmentIds: [leftSegment.id, rightSegment.id],
  });
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
