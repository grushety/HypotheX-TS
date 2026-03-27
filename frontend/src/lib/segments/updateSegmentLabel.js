import { validateEditableSegments } from "./validateEditableSegments.js";

export const AVAILABLE_SEGMENT_LABELS = ["event", "trend", "anomaly", "other"];

function createError(code, message) {
  return {
    ok: false,
    code,
    message,
  };
}

export function updateSegmentLabel(segments, segmentId, nextLabel) {
  const validation = validateEditableSegments(segments);

  if (!validation.ok) {
    return validation;
  }

  if (!segmentId) {
    return createError("INVALID_SEGMENT_ID", "A selected segment is required.");
  }

  if (!AVAILABLE_SEGMENT_LABELS.includes(nextLabel)) {
    return createError("INVALID_LABEL", "Segment label must be one of the supported semantic labels.");
  }

  const index = segments.findIndex((segment) => segment.id === segmentId);

  if (index === -1) {
    return createError("SEGMENT_NOT_FOUND", "Selected segment was not found.");
  }

  const updatedSegments = segments.map((segment, currentIndex) =>
    currentIndex === index ? { ...segment, label: nextLabel } : { ...segment },
  );

  const updatedValidation = validateEditableSegments(updatedSegments);

  if (!updatedValidation.ok) {
    return updatedValidation;
  }

  return {
    ok: true,
    segments: updatedSegments,
    updatedSegmentId: segmentId,
  };
}
