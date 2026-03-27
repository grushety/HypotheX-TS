const DEFAULT_MIN_SEGMENT_LENGTH = 1;

function cloneSegments(segments) {
  return segments.map((segment) => ({ ...segment }));
}

function createError(code, message) {
  return {
    ok: false,
    code,
    message,
  };
}

export function moveSegmentBoundary(segments, boundaryIndex, nextBoundaryStart, options = {}) {
  if (!Array.isArray(segments) || segments.length < 2) {
    return createError("INVALID_SEGMENTS", "At least two ordered segments are required.");
  }

  if (!Number.isInteger(boundaryIndex) || boundaryIndex < 0 || boundaryIndex >= segments.length - 1) {
    return createError("INVALID_BOUNDARY_INDEX", "Boundary index must reference adjacent segments.");
  }

  if (!Number.isInteger(nextBoundaryStart)) {
    return createError("INVALID_BOUNDARY_POSITION", "Boundary position must be an integer.");
  }

  const minSegmentLength = options.minSegmentLength ?? DEFAULT_MIN_SEGMENT_LENGTH;
  const updatedSegments = cloneSegments(segments);
  const leftSegment = updatedSegments[boundaryIndex];
  const rightSegment = updatedSegments[boundaryIndex + 1];

  const minimumBoundaryStart = leftSegment.start + minSegmentLength;
  const maximumBoundaryStart = rightSegment.end - minSegmentLength + 1;

  if (nextBoundaryStart < minimumBoundaryStart || nextBoundaryStart > maximumBoundaryStart) {
    return createError(
      "BOUNDARY_OUT_OF_RANGE",
      "Boundary move would violate segment length or ordering constraints.",
    );
  }

  leftSegment.end = nextBoundaryStart - 1;
  rightSegment.start = nextBoundaryStart;

  return {
    ok: true,
    boundaryIndex,
    segments: updatedSegments,
    updatedSegmentIds: [leftSegment.id, rightSegment.id],
  };
}
