import { applySemanticOperation } from "./semanticOperations.js";

function createError(message) {
  return {
    ok: false,
    message,
  };
}

export function executeOperationAction(sample, selectedSegmentId, request) {
  if (!sample?.segments?.length) {
    return createError("A loaded sample is required before running operations.");
  }

  const result = applySemanticOperation(sample.segments, request);

  if (!result.ok) {
    return {
      ok: false,
      message: result.message,
      operationResult: result,
    };
  }

  let nextSelectedSegmentId = selectedSegmentId;

  if (result.type === "split") {
    nextSelectedSegmentId = result.affectedSegmentIds[0] ?? selectedSegmentId;
  }

  if (result.type === "merge") {
    nextSelectedSegmentId = result.affectedSegmentIds[0] ?? selectedSegmentId;
  }

  if (result.type === "reclassify") {
    nextSelectedSegmentId = result.affectedSegmentIds[0] ?? selectedSegmentId;
  }

  return {
    ok: true,
    sample: {
      ...sample,
      segments: result.segments,
    },
    selectedSegmentId: nextSelectedSegmentId,
    message: `${result.type} applied successfully.`,
    operationResult: result,
  };
}
