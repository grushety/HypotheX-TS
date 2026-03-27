import { AVAILABLE_SEGMENT_LABELS } from "./updateSegmentLabel.js";

function createError(code, message) {
  return {
    ok: false,
    code,
    message,
  };
}

export function validateEditableSegments(segments, options = {}) {
  const seriesLength = options.seriesLength ?? null;

  if (!Array.isArray(segments) || segments.length === 0) {
    return createError("INVALID_SEGMENTS", "A non-empty ordered segment list is required.");
  }

  for (let index = 0; index < segments.length; index += 1) {
    const segment = segments[index];

    if (
      !segment ||
      !segment.id ||
      !Number.isInteger(segment.start) ||
      !Number.isInteger(segment.end) ||
      segment.start > segment.end
    ) {
      return createError("INVALID_SEGMENT_SHAPE", "Each segment must include an id and valid integer bounds.");
    }

    if (!AVAILABLE_SEGMENT_LABELS.includes(segment.label)) {
      return createError("INVALID_LABEL", "Segment label must be one of the supported semantic labels.");
    }

    if (index > 0) {
      const previous = segments[index - 1];

      if (segment.start !== previous.end + 1) {
        return createError(
          "NON_CONTIGUOUS_SEGMENTS",
          "Segments must remain ordered, contiguous, and non-overlapping.",
        );
      }
    }
  }

  if (segments[0].start !== 0) {
    return createError("INVALID_START", "Editable segments must start at index 0.");
  }

  if (seriesLength !== null && segments.at(-1).end !== seriesLength - 1) {
    return createError("INVALID_END", "Editable segments must cover the full series length.");
  }

  return {
    ok: true,
  };
}
